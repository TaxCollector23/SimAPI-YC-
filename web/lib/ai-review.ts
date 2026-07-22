/**
 * Server-side AI check of a validation result via OpenRouter.
 *
 * [SIMAPI-AI-REVIEW v2.2 — diagnosis-wired + fallback chain]
 *
 * The physics engine is the source of truth. This layer does NOT generate an
 * independent verdict — it receives the engine's concrete violations and
 * explains them in engineer-readable language.
 *
 * A single free-tier model can hit its daily OpenRouter quota (429) or return
 * blank content unrelated to anything wrong here. MODEL_CHAIN tries several
 * independent providers before giving up, so that degrades to a slower answer
 * instead of "AI layer unavailable."
 *
 * Timeout budget: Vercel maxDuration is 60s and physics validation runs first,
 * so the AI call gets ~45s across however many models it takes.
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

// Domain-specific expertise cues — steers the model toward the right causal
// vocabulary for each field instead of generic "the data looks off" answers.
const DOMAIN_EXPERTISE: Record<string, string> = {
  aerodynamics: "CFD post-processing: unit slips (Pa/kPa, deg/rad), Mach/Reynolds consistency, " +
    "stall-region CL behavior, mesh y+ sensitivity, solver residual convergence.",
  fluid_dynamics: "CFD/FVM solvers: courant number instability, turbulence model mismatch, " +
    "boundary-layer resolution, pressure-velocity coupling divergence.",
  structural: "FEA: stress-strain consistency (Hooke's law), mesh refinement artifacts, " +
    "boundary condition under-constraint, unit mismatches (MPa vs Pa), element locking.",
  thermodynamics: "Heat transfer: energy balance violations, unit errors (K vs °C), " +
    "material property lookup errors, steady-state vs transient solver settings.",
  robotics: "Control/kinematics: joint-limit violations, actuator saturation, sensor noise vs " +
    "drift, coordinate-frame mismatches, timestep-dependent integration error.",
  combustion: "Reacting flow: species conservation, flame-speed unit errors, ignition-delay " +
    "outliers, chemistry-mechanism solver stiffness.",
  electromagnetics: "EM solvers: mesh discretization at skin depth, unit errors (permittivity/" +
    "permeability), boundary condition (PML) reflection artifacts.",
};

// Fallback chain of (key, model) pairs across up to two OpenRouter accounts.
// A bad/expired/rate-limited key on one combination falls through to the next
// key+model, not just the next model on the same key. Verified against GET
// https://openrouter.ai/api/v1/models — OpenRouter's free catalog changes
// over time and stale slugs 404 rather than falling through, so this list
// must be checked periodically, not assumed.
interface KeyModel { key: string; model: string }

function buildKeyModelChain(): KeyModel[] {
  const key1 = process.env.OPENROUTER_API_KEY;
  const key2 = process.env.OPENROUTER_API_KEY_2;
  const chain: KeyModel[] = [];
  if (key1) {
    chain.push(
      { key: key1, model: process.env.OPENROUTER_MODEL || "nvidia/nemotron-nano-9b-v2:free" },
      { key: key1, model: "google/gemma-4-31b-it:free" },
      { key: key1, model: "nvidia/nemotron-3-nano-30b-a3b:free" },
    );
  }
  if (key2) {
    chain.push(
      { key: key2, model: "openai/gpt-oss-20b:free" },
      { key: key2, model: "google/gemma-4-26b-a4b-it:free" },
      { key: key2, model: "nvidia/nemotron-3-super-120b-a12b:free" },
    );
  }
  return chain;
}

// Only these models accept/benefit from the `reasoning` param. Sending it to
// a non-reasoning model makes it return blank content instead of an answer.
const REASONING_MODEL_PATTERNS = [/nemotron/i, /gpt-oss/i];
function usesReasoningParam(model: string): boolean {
  return REASONING_MODEL_PATTERNS.some((p) => p.test(model));
}

const TOKENS_SHORT = 700;
const TIMEOUT_MS = 10_000;
// Vercel maxDuration is 60s and physics validation (which can include a
// Render cold-start, up to 35s) runs first; stop trying more (key, model)
// pairs once this wall-clock budget for the AI call is spent, rather than
// assuming a fixed number of pairs × timeouts always fits what's left.
const TOTAL_BUDGET_MS = 20_000;
const REVIEW_VERSION = "2.4-domain-expert-prompts";

class AbortedError extends Error {}
/** Thrown for 429/5xx/empty/unparseable responses — safe to try the next model. */
class RetryableError extends Error {}

async function callModel(
  prompt: string, model: string, maxTokens: number, key: string, timeoutMs: number,
): Promise<string> {
  const controller = new AbortController();
  let aborted = false;
  const timer = setTimeout(() => { aborted = true; controller.abort(); }, timeoutMs);
  try {
    const body: Record<string, unknown> = {
      model,
      max_tokens: maxTokens,
      temperature: 0.1,
      messages: [{ role: "user", content: prompt }],
    };
    if (usesReasoningParam(model)) {
      body.reasoning = { exclude: true, max_tokens: Math.min(250, Math.floor(maxTokens / 2)) };
    }
    const res = await fetch(OPENROUTER_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sim-api.vercel.app",
        "X-Title": "SimAPI",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (res.status === 401 || res.status === 404 || res.status === 429 || res.status >= 500) {
      // 401 = this specific key is invalid/revoked (try the other key);
      // 404 = model slug deprecated/renamed on OpenRouter's end (try the next model).
      throw new RetryableError(`OpenRouter ${res.status} from ${model}`);
    }
    if (!res.ok) throw new Error(`OpenRouter ${res.status}`);
    const data = await res.json();
    const content: string | undefined = data?.choices?.[0]?.message?.content;
    if (!content) throw new RetryableError(`${model} returned no content`);
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
  throw new RetryableError("Model returned unparseable output");
}

/**
 * Try each (key, model) pair, widening the token budget once per pair, but
 * never past the shared wall-clock budget — a hung or slow pair can't eat
 * into every other pair's chance to answer.
 */
async function callWithFallback(
  prompt: string, chain: KeyModel[],
): Promise<{ content: string; parsed: Record<string, unknown>; model: string }> {
  const deadline = Date.now() + TOTAL_BUDGET_MS;
  let lastErr: unknown;
  for (const maxTokens of [TOKENS_SHORT, TOKENS_SHORT * 2]) {
    for (const { key, model } of chain) {
      const remaining = deadline - Date.now();
      if (remaining <= 500) throw lastErr instanceof Error ? lastErr : new Error("AI fallback chain: time budget exhausted");
      try {
        const content = await callModel(prompt, model, maxTokens, key, Math.min(TIMEOUT_MS, remaining));
        const parsed = parseLoose(content);
        return { content, parsed, model };
      } catch (e) {
        if (e instanceof AbortedError) { lastErr = e; continue; }
        lastErr = e;
        continue;
      }
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error("AI fallback chain exhausted");
}

export async function aiReview(
  report: Pick<ValidationReport, "status" | "score" | "violations" | "recommendations" | "simulationType" | "checks">,
  conditions: Record<string, unknown>,
  profile?: DataProfile,
): Promise<AiReview> {
  const chain = buildKeyModelChain();
  if (chain.length === 0) return { enabled: false, reviewVersion: REVIEW_VERSION };

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
      model: chain[0].model,
      reviewVersion: REVIEW_VERSION,
    };
  }

  const expertise = DOMAIN_EXPERTISE[report.simulationType] ?? "engineering simulation post-processing";

  const prompt = `You are a senior ${report.simulationType} simulation engineer with deep expertise in: ${expertise}

A deterministic physics engine has ALREADY analyzed this dataset and found the specific violations listed below. These findings are confirmed and correct — your job is to explain them precisely, not invent new findings or restate generic statistics language.

CONFIRMED VIOLATIONS:
${violationLines.join("\n") || "(none)"}

FAILED CHECKS:
${checkLines.join("\n") || "(none)"}

ENGINE RECOMMENDATIONS:
${engineRecs.join("\n") || "(none)"}

Conditions: ${JSON.stringify(conditions)}

Write 3-4 sentences: (1) what specifically went wrong, naming the exact field/value above, (2) the most likely root-cause mechanism given your domain expertise (a specific unit conversion, a specific solver setting, a specific sensor failure mode — not "data quality issue"), (3) one concrete first thing to check.

Respond ONLY with this JSON, no other text:
{"verdict":"not normal","reason":"3-4 specific sentences per the instructions above","recommendation":"one concrete actionable step, naming a specific file/parameter/column to check"}`;

  try {
    const { parsed, model } = await callWithFallback(prompt, chain);
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
      model,
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
      model: chain[0].model,
      reviewVersion: REVIEW_VERSION,
      error: e instanceof AbortedError
        ? `Model timed out after ${TIMEOUT_MS / 1000}s`
        : e instanceof Error ? e.message : "AI review failed",
    };
  }
}
