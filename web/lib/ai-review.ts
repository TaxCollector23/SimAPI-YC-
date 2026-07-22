/**
 * Server-side AI check of a validation result via OpenRouter.
 *
 * [SIMAPI-AI-REVIEW v2.1 — diagnosis-wired]
 *
 * The physics engine is the source of truth. This layer does NOT generate an
 * independent verdict — it receives the engine's concrete violations and
 * explains them in engineer-readable language.
 *
 * Timeout budget: Vercel maxDuration is 30s and physics validation runs first,
 * so the AI call gets 20s and only retries when the first attempt failed for a
 * reason OTHER than timeout (retrying after an abort would blow the budget).
 */
import type { ValidationReport } from "./validation-engine";

export interface AiReview {
  enabled: boolean;
  status?: "agree" | "concern" | "disagree";
  verdict?: "Normal" | "Not Normal";
  assessment?: string;
  concerns?: string[];
  recommendation?: string;
  model?: string;
  error?: string;
  reviewVersion?: string;
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
const TOKENS_SHORT = 500;
const TIMEOUT_MS = 20_000;
const REVIEW_VERSION = "2.1-diag-wired";

class AbortedError extends Error {}

async function callQuick(prompt: string, maxTokens: number, key: string): Promise<string> {
  const controller = new AbortController();
  let aborted = false;
  const timer = setTimeout(() => { aborted = true; controller.abort(); }, TIMEOUT_MS);
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
        reasoning: { exclude: true, max_tokens: Math.min(250, Math.floor(maxTokens / 2)) },
        temperature: 0.1,
        messages: [{ role: "user", content: prompt }],
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`OpenRouter ${res.status}`);
    const data = await res.json();
    const content: string | undefined = data?.choices?.[0]?.message?.content;
    if (!content) throw new Error("Model returned no content");
    return content.trim().replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
  } catch (e) {
    if (aborted) throw new AbortedError("timeout");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/** Extract JSON even when the model wraps it in prose. */
function parseLoose(raw: string): Record<string, unknown> {
  try { return JSON.parse(raw); } catch { /* fall through */ }
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start !== -1 && end > start) {
    try { return JSON.parse(raw.slice(start, end + 1)); } catch { /* fall through */ }
  }
  throw new Error("Model returned unparseable output");
}

export async function aiReview(
  report: Pick<ValidationReport, "status" | "score" | "violations" | "recommendations" | "simulationType" | "checks">,
  conditions: Record<string, unknown>,
  profile?: DataProfile,
): Promise<AiReview> {
  const key = process.env.OPENROUTER_API_KEY;
  if (!key) return { enabled: false, reviewVersion: REVIEW_VERSION };

  const violations = report.violations ?? [];
  const failedChecks = (report.checks ?? []).filter((c) => c.status === "failed");

  // Concrete, specific violation lines — this is what makes the output specific
  // instead of generic. Each line names the field, its actual value, and why it failed.
  const violationLines = violations.slice(0, 8).map(
    (v) => `- ${v.field} = ${v.value} — ${v.reason} (${v.severity})`,
  );
  const checkLines = failedChecks.slice(0, 8).map(
    (c) => `- ${c.name}: ${c.detail ?? "failed"}`,
  );
  const engineRecs = (report.recommendations ?? []).slice(0, 4);

  const nothingWrong = violationLines.length === 0 && checkLines.length === 0;

  // If the engine found nothing, don't ask the model to invent a problem.
  if (nothingWrong) {
    return {
      enabled: true,
      status: "agree",
      verdict: "Normal",
      assessment: "Physics engine found no violations. Dataset is within physical bounds and internally consistent.",
      concerns: [],
      model: QUICK_MODEL,
      reviewVersion: REVIEW_VERSION,
    };
  }

  const prompt = `You are an expert simulation pipeline engineer. A deterministic physics engine has ALREADY analyzed a ${report.simulationType} dataset and found the specific violations listed below. These findings are confirmed and correct.

Your job: explain what went wrong, why it happened, and what to check first. Do NOT invent new findings. Do NOT mention statistical variance. Reference the exact fields and values below.

CONFIRMED VIOLATIONS:
${violationLines.join("\n") || "(none)"}

FAILED CHECKS:
${checkLines.join("\n") || "(none)"}

ENGINE RECOMMENDATIONS:
${engineRecs.join("\n") || "(none)"}

Conditions: ${JSON.stringify(conditions)}

Write 2-3 sentences naming the actual fields and values above, the likely root cause in the simulation pipeline (unit conversion, solver divergence, post-processing formula error, sensor drift), and the first thing the engineer should check.

Respond ONLY with this JSON, no other text:
{"verdict":"not normal","reason":"2-3 specific sentences naming actual fields and values","recommendation":"one specific actionable step"}`;

  try {
    let content: string;
    try {
      content = await callQuick(prompt, TOKENS_SHORT, key);
    } catch (e) {
      // Only retry when the first attempt failed for a NON-timeout reason.
      // Retrying after an abort would exceed the Vercel function budget.
      if (e instanceof AbortedError) throw e;
      content = await callQuick(prompt, TOKENS_SHORT * 2, key);
    }
    const parsed = parseLoose(content);
    const isNormal = String(parsed.verdict ?? "").trim().toLowerCase() === "normal";
    const reason = String(parsed.reason ?? "");
    const rec = String(parsed.recommendation ?? "");
    return {
      enabled: true,
      status: isNormal ? "agree" : "concern",
      verdict: isNormal ? "Normal" : "Not Normal",
      assessment: reason,
      concerns: isNormal ? [] : [reason],
      recommendation: rec || undefined,
      model: QUICK_MODEL,
      reviewVersion: REVIEW_VERSION,
    };
  } catch (e) {
    // Graceful degradation: the physics result above is complete and standalone.
    // Surface the engine's own finding so the panel is never empty.
    const fallback = violations[0]
      ? `${violations[0].field} = ${violations[0].value} — ${violations[0].reason}`
      : failedChecks[0]?.detail ?? "";
    return {
      enabled: true,
      status: "concern",
      verdict: "Not Normal",
      assessment: fallback,
      concerns: fallback ? [fallback] : [],
      model: QUICK_MODEL,
      reviewVersion: REVIEW_VERSION,
      error: e instanceof AbortedError
        ? `Model timed out after ${TIMEOUT_MS / 1000}s`
        : e instanceof Error ? e.message : "AI review failed",
    };
  }
}
