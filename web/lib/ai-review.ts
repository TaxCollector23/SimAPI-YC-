/**
 * Server-side AI check of a validation result via OpenRouter.
 *
 * This is a FAST sanity pass ("is this normal or not"), not a deep
 * investigation — the physics engine is the source of truth, the AI layer is
 * a second opinion. Runs only when OPENROUTER_API_KEY is set (server env).
 * The key never reaches the browser (imported only by route handlers).
 *
 * Token budgets are deliberately small: this answers a yes/no question, not a
 * report, so a few hundred tokens is enough and keeps latency under ~18s.
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
const QUICK_MODEL = "nvidia/nemotron-nano-9b-v2:free";
const TOKENS_SHORT = 400;
// This route is synchronous (no polling) and shares the Vercel function's
// 30s maxDuration with physics validation. One retry means worst case is
// 2x this budget, so keep it well under half of 30s.
const TIMEOUT_MS = 12_000;

/** High-cv columns are the cheapest signal that something might be off — no
 * need to send the model a full statistics table for a yes/no check. */
function highVarianceColumns(stats: DataProfile["statistics"]): string[] {
  if (!stats) return [];
  return Object.entries(stats)
    .filter(([, s]) => Number.isFinite(s.cv) && Math.abs(s.cv) > 0.5)
    .slice(0, 5)
    .map(([k, s]) => `${k} (cv=${s.cv.toFixed(2)})`);
}

async function callQuick(prompt: string, maxTokens: number, key: string): Promise<string> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
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
        model: QUICK_MODEL,
        max_tokens: maxTokens,
        // Cap hidden reasoning tokens explicitly — some free models reason even
        // with exclude=true, and an uncapped budget can eat the whole response.
        reasoning: { exclude: true, max_tokens: Math.min(250, Math.floor(maxTokens / 2)) },
        temperature: 0.1,
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

  const highCv = highVarianceColumns(profile?.statistics);
  const failedChecks = (report.violations ?? []).slice(0, 8).map((v) => v.field ?? v.reason).filter(Boolean);

  const prompt = `You are sanity-checking a ${report.simulationType} simulation dataset that a deterministic physics engine already validated (verdict: "${report.status}", score ${report.score}/100${profile?.trials_submitted ? `, ${profile.trials_excluded ?? 0}/${profile.trials_submitted} trials excluded` : ""}).

Failed/flagged checks: ${failedChecks.length ? JSON.stringify(failedChecks) : "none"}
High-variance columns (cv>0.5): ${highCv.length ? highCv.join(", ") : "none"}
Conditions: ${JSON.stringify(conditions)}

Is this dataset normal (safe to use as-is) or not normal (has a real problem)? Be terse.

Respond ONLY with this JSON, no other text:
{"verdict": "normal" | "not normal", "reason": "one short sentence"}`;

  try {
    let content: string;
    try {
      content = await callQuick(prompt, TOKENS_SHORT, key);
    } catch {
      // One retry with a larger budget — free-tier reasoning models occasionally
      // burn their whole budget on hidden chain-of-thought.
      content = await callQuick(prompt, TOKENS_SHORT * 2, key);
    }
    const parsed = JSON.parse(content);
    const isNormal = String(parsed.verdict ?? "").trim().toLowerCase() === "normal";
    return {
      enabled: true,
      status: isNormal ? "agree" : "concern",
      verdict: isNormal ? "Normal" : "Not Normal",
      assessment: String(parsed.reason ?? ""),
      concerns: isNormal ? [] : [String(parsed.reason ?? "")],
      model: QUICK_MODEL,
    };
  } catch (e) {
    return { enabled: true, error: e instanceof Error ? e.message : "AI review failed" };
  }
}
