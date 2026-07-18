/**
 * Server-side AI review of a validation result via OpenRouter.
 *
 * This is a genuine second-pass analysis, not a fast sanity check — the
 * model is given real data characteristics (statistics, correlations,
 * sample/violating rows) and asked to reason about what a rule engine might
 * miss, not just answer yes/no. It's allowed to take its time (up to the
 * route's maxDuration); a thoughtful answer matters more than shaving
 * seconds off latency here. Runs only when OPENROUTER_API_KEY is set (server
 * env). The key never reaches the browser (imported only by route handlers).
 */
import type { ValidationReport } from "./validation-engine";

export interface AiReview {
  enabled: boolean;
  status?: "agree" | "concern" | "disagree";
  verdict?: "Normal" | "Not Normal";
  assessment?: string;
  concerns?: string[];
  model?: string;
  error?: string;
}

export interface DataProfile {
  trials_submitted?: number;
  trials_excluded?: number;
  statistics?: Record<string, { mean: number; std: number; min: number; max: number; cv: number; skewness?: number; n?: number }>;
  correlations?: { pair: string; r: number }[];
  sample_rows?: Record<string, unknown>[];
  violating_rows?: Record<string, unknown>[];
}

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";
// The larger "thinking" model — genuinely reasons through the data rather
// than pattern-matching a one-line verdict. Slower (typically 10-30s for
// this prompt, measured), which is the deliberate tradeoff here.
const DEEP_MODEL = process.env.OPENROUTER_MODEL || "nvidia/nemotron-3-ultra-550b-a55b:free";
const TOKENS_LONG = 2500;
// This route is synchronous (no polling) and shares the Vercel function's
// maxDuration with physics validation — see route.ts's maxDuration export,
// which was raised alongside this. Leave headroom for physics + JSON parse.
const TIMEOUT_MS = 50_000;

function statsTable(stats: DataProfile["statistics"]): string {
  if (!stats || !Object.keys(stats).length) return "(none)";
  return Object.entries(stats).slice(0, 20).map(([k, s]) =>
    `  ${k}: mean=${fmt(s.mean)} std=${fmt(s.std)} min=${fmt(s.min)} max=${fmt(s.max)} cv=${fmt(s.cv)}${s.skewness !== undefined ? ` skew=${fmt(s.skewness)}` : ""}`,
  ).join("\n");
}
function fmt(n: number): string {
  if (!Number.isFinite(n)) return String(n);
  if (Math.abs(n) >= 1e5 || (Math.abs(n) < 1e-3 && n !== 0)) return n.toExponential(2);
  return Number.isInteger(n) ? String(n) : n.toFixed(4);
}

async function callDeep(prompt: string, key: string, timeoutMs: number): Promise<string> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(OPENROUTER_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sim-api.vercel.app",
        "X-Title": "SimAPI",
      },
      body: JSON.stringify({
        model: DEEP_MODEL,
        max_tokens: TOKENS_LONG,
        // Cap hidden reasoning tokens explicitly — some free models reason even
        // with exclude=true, and an uncapped budget can eat the whole response
        // before any visible content is emitted.
        reasoning: { exclude: true, max_tokens: 900 },
        temperature: 0.15,
        messages: [{ role: "user", content: prompt }],
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`OpenRouter ${res.status}`);
    const data = await res.json();
    const content: string | undefined = data?.choices?.[0]?.message?.content;
    if (!content) throw new Error("Model returned no content (likely exhausted its token budget on hidden reasoning)");
    return content.trim().replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
  } finally {
    clearTimeout(timer);
  }
}

export async function aiReview(
  report: Pick<ValidationReport, "status" | "score" | "violations" | "recommendations" | "simulationType" | "checks">,
  conditions: Record<string, unknown>,
  profile?: DataProfile,
): Promise<AiReview> {
  const key = process.env.OPENROUTER_API_KEY;
  if (!key) return { enabled: false };

  const corr = profile?.correlations?.length
    ? profile.correlations.slice(0, 6).map((c) => `  ${c.pair}: r=${c.r.toFixed(2)}`).join("\n")
    : "(not computed)";

  const prompt = `You are a senior CFD/simulation engineer reviewing a ${report.simulationType} dataset that a deterministic physics engine has already screened. Verdict: "${report.status}" (score ${report.score}/100)${profile?.trials_submitted ? `, ${profile.trials_excluded ?? 0}/${profile.trials_submitted} trials excluded` : ""}.

You are given the ACTUAL DATA — use it. Take your time and reason carefully. Look for problems the rule engine may have missed: implausible magnitudes, distribution shape (skew/heavy tails via cv & skew), suspicious correlations or their absence, values clustered at unit-conversion boundaries, and rows that violate physics.

Boundary conditions:
${JSON.stringify(conditions, null, 2)}

Per-column statistics:
${statsTable(profile?.statistics)}

Strongest correlations:
${corr}

Sample rows:
${JSON.stringify((profile?.sample_rows ?? []).slice(0, 4), null, 0)}

Rows that failed a rule (if any):
${JSON.stringify((profile?.violating_rows ?? []).slice(0, 4), null, 0)}

Checks the engine already flagged:
${JSON.stringify((report.violations ?? []).slice(0, 12), null, 0)}

Respond ONLY with JSON:
{
  "status": "agree" | "concern" | "disagree",
  "assessment": "3-5 sentence expert judgement that references specific numbers from the data",
  "concerns": ["specific, data-grounded issues the rules may have missed — as many as are genuinely warranted"]
}`;

  try {
    const content = await callDeep(prompt, key, TIMEOUT_MS);
    const parsed = JSON.parse(content);
    return {
      enabled: true,
      status: parsed.status,
      verdict: parsed.status === "agree" ? "Normal" : "Not Normal",
      assessment: parsed.assessment,
      concerns: Array.isArray(parsed.concerns) ? parsed.concerns : [],
      model: DEEP_MODEL,
    };
  } catch (e) {
    return { enabled: true, error: e instanceof Error ? e.message : "AI review failed" };
  }
}
