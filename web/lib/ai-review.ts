/**
 * Server-side AI review of a validation result via OpenRouter.
 *
 * Runs only when OPENROUTER_API_KEY is set (server env). The model is given the
 * deterministic verdict AND the actual data characteristics — per-column
 * statistics, the strongest correlations, and sample rows (including violating
 * ones) — so it can reason like an engineer-in-charge rather than rubber-stamp a
 * score. The key never reaches the browser (imported only by route handlers).
 */
import type { ValidationReport } from "./validation-engine";

export interface AiReview {
  enabled: boolean;
  status?: "agree" | "concern" | "disagree";
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

function statsTable(stats: DataProfile["statistics"]): string {
  if (!stats || !Object.keys(stats).length) return "(none)";
  const rows = Object.entries(stats).slice(0, 20).map(([k, s]) =>
    `  ${k}: mean=${fmt(s.mean)} std=${fmt(s.std)} min=${fmt(s.min)} max=${fmt(s.max)} cv=${fmt(s.cv)}${s.skewness !== undefined ? ` skew=${fmt(s.skewness)}` : ""}`);
  return rows.join("\n");
}
function fmt(n: number): string {
  if (!Number.isFinite(n)) return String(n);
  if (Math.abs(n) >= 1e5 || (Math.abs(n) < 1e-3 && n !== 0)) return n.toExponential(2);
  return Number.isInteger(n) ? String(n) : n.toFixed(4);
}

export async function aiReview(
  report: Pick<ValidationReport, "status" | "score" | "violations" | "recommendations" | "simulationType" | "checks">,
  conditions: Record<string, unknown>,
  profile?: DataProfile,
): Promise<AiReview> {
  const key = process.env.OPENROUTER_API_KEY;
  if (!key) return { enabled: false };

  const model = process.env.OPENROUTER_MODEL || "nvidia/nemotron-3-ultra-550b-a55b:free";
  const corr = profile?.correlations?.length
    ? profile.correlations.slice(0, 6).map((c) => `  ${c.pair}: r=${c.r.toFixed(2)}`).join("\n")
    : "(not computed)";

  const prompt = `You are a senior CFD/simulation engineer reviewing a ${report.simulationType} dataset that a deterministic physics engine has already screened. Verdict: "${report.status}" (score ${report.score}/100)${profile?.trials_submitted ? `, ${profile.trials_excluded ?? 0}/${profile.trials_submitted} trials excluded` : ""}.

You are given the ACTUAL DATA — use it. Look for problems the rule engine may have missed: implausible magnitudes, distribution shape (skew/heavy tails via cv & skew), suspicious correlations or their absence, values clustered at unit-conversion boundaries, and rows that violate physics.

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
  "assessment": "2-4 sentence expert judgement that references specific numbers from the data",
  "concerns": ["specific, data-grounded issues the rules may have missed"]
}`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 22_000);
    const res = await fetch(OPENROUTER_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sim-api.vercel.app",
        "X-Title": "SimAPI",
      },
      body: JSON.stringify({
        model,
        // The default free model is a reasoning model — hidden chain-of-thought
        // tokens count against max_tokens, so a low budget can exhaust the whole
        // response before any visible JSON is emitted. Exclude reasoning from
        // the response and give enough headroom for both.
        max_tokens: 2500,
        reasoning: { exclude: true },
        temperature: 0.1,
        messages: [{ role: "user", content: prompt }],
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return { enabled: true, error: `OpenRouter ${res.status}` };
    const data = await res.json();
    let content: string = data?.choices?.[0]?.message?.content ?? "";
    content = content.trim().replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
    const parsed = JSON.parse(content);
    return {
      enabled: true,
      status: parsed.status,
      assessment: parsed.assessment,
      concerns: Array.isArray(parsed.concerns) ? parsed.concerns : [],
      model,
    };
  } catch (e) {
    return { enabled: true, error: e instanceof Error ? e.message : "AI review failed" };
  }
}
