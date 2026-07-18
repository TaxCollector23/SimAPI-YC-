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
// Free OpenRouter models on a zero-balance account share a low daily quota
// ("free-models-per-day" -- OpenRouter's own error message points at adding
// $10 credit to unlock 1000/day). One model hitting that wall doesn't mean
// they all are -- fall back across models from DIFFERENT upstream providers,
// since quota/availability isn't perfectly correlated across them.
const MODEL_CHAIN = [
  process.env.OPENROUTER_MODEL || "nvidia/nemotron-3-ultra-550b-a55b:free",
  "qwen/qwen3-next-80b-a3b-instruct:free",
  "meta-llama/llama-3.3-70b-instruct:free",
  "nvidia/nemotron-nano-9b-v2:free",
  "tencent/hy3:free", // different infra provider (Novita); NOT a reasoning model -- see REASONING_MODELS below
].filter((m, i, arr) => arr.indexOf(m) === i); // dedupe if OPENROUTER_MODEL overrides to one of the fallbacks

// Only send the `reasoning` param to models that actually use it. Sending it
// to a non-reasoning model (confirmed with tencent/hy3:free) can break its
// response entirely -- it returned pages of blank whitespace instead of
// content when this param was included, and worked perfectly without it.
const REASONING_MODELS = [/nemotron/i, /qwen3/i, /gpt-oss/i];
function usesReasoningParam(model: string): boolean {
  return REASONING_MODELS.some((re) => re.test(model));
}

const TOKENS_LONG = 2500;
// This route is synchronous (no polling) and shares the Vercel function's
// maxDuration with physics validation — see route.ts's maxDuration export,
// which was raised alongside this. Leave headroom for physics + JSON parse
// and multiple fallback attempts.
const TIMEOUT_MS = 20_000;

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

// Thrown for failures worth trying the next model over -- rate limits, empty
// content (a model exhausting its reasoning budget), and malformed JSON are
// all "this model didn't give us a usable answer," not "the request itself
// is broken." Genuine errors (bad request, auth failure) are NOT retryable.
class RetryableError extends Error {}

/** Some free models wrap JSON in prose or a code fence despite explicit
 * "respond ONLY with JSON" instructions -- pull out the first balanced
 * {...} object instead of requiring the whole response to parse cleanly. */
function extractJson(text: string): string | null {
  const stripped = text.trim().replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
  try {
    JSON.parse(stripped);
    return stripped;
  } catch {
    /* fall through to brace-matching extraction below */
  }
  const start = stripped.indexOf("{");
  if (start === -1) return null;
  let depth = 0;
  for (let i = start; i < stripped.length; i++) {
    if (stripped[i] === "{") depth++;
    else if (stripped[i] === "}") {
      depth--;
      if (depth === 0) {
        const candidate = stripped.slice(start, i + 1);
        try {
          JSON.parse(candidate);
          return candidate;
        } catch {
          return null;
        }
      }
    }
  }
  return null;
}

async function callModel(prompt: string, model: string, key: string, timeoutMs: number): Promise<string> {
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
        model,
        max_tokens: TOKENS_LONG,
        temperature: 0.15,
        messages: [{ role: "user", content: prompt }],
        // Cap hidden reasoning tokens explicitly — some free reasoning models
        // burn their whole budget on hidden chain-of-thought even with
        // exclude=true, leaving nothing for visible content. Only send this
        // to models that actually use it -- sending it to a non-reasoning
        // model can break its response format entirely.
        ...(usesReasoningParam(model) ? { reasoning: { exclude: true, max_tokens: 900 } } : {}),
      }),
      signal: controller.signal,
    });
    if (res.status === 429) throw new RetryableError(`${model} rate-limited (429)`);
    if (res.status >= 500) throw new RetryableError(`${model} upstream error (${res.status})`);
    if (!res.ok) throw new Error(`OpenRouter ${res.status} (${model})`);
    const data = await res.json();
    if (data?.error) {
      const msg = String(data.error?.message ?? "");
      if (data.error?.code === 429 || /rate.?limit/i.test(msg)) throw new RetryableError(`${model} rate-limited: ${msg}`);
      throw new RetryableError(`${model}: ${msg || "unknown error"}`);
    }
    const content: string | undefined = data?.choices?.[0]?.message?.content;
    if (!content) throw new RetryableError(`${model} returned no content (likely exhausted its token budget on hidden reasoning)`);
    const extracted = extractJson(content);
    if (extracted === null) throw new RetryableError(`${model} returned unparseable content`);
    return extracted;
  } finally {
    clearTimeout(timer);
  }
}

/** Try each model in MODEL_CHAIN in order; only fall through on retryable
 * failures (rate limits, empty/unparseable content, 5xx), not on genuine
 * request errors, which would just repeat across every model. Returns which
 * model actually answered. */
async function callWithFallback(prompt: string, key: string, timeoutMs: number): Promise<{ content: string; model: string }> {
  let lastErr: unknown;
  for (const model of MODEL_CHAIN) {
    try {
      const content = await callModel(prompt, model, key, timeoutMs);
      return { content, model };
    } catch (e) {
      lastErr = e;
      if (!(e instanceof RetryableError)) throw e;
      // retryable -- try the next model in the chain
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error("All models rate-limited");
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
    const { content, model } = await callWithFallback(prompt, key, TIMEOUT_MS);
    const parsed = JSON.parse(content);
    return {
      enabled: true,
      status: parsed.status,
      verdict: parsed.status === "agree" ? "Normal" : "Not Normal",
      assessment: parsed.assessment,
      concerns: Array.isArray(parsed.concerns) ? parsed.concerns : [],
      model,
    };
  } catch (e) {
    return { enabled: true, error: e instanceof Error ? e.message : "AI review failed" };
  }
}
