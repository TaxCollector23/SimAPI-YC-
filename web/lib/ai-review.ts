/**
 * Server-side AI review of a validation result via OpenRouter.
 *
 * Runs only when OPENROUTER_API_KEY is set (server env). Given the deterministic
 * result and the conditions, it asks an LLM whether the outcome is physically and
 * logically consistent, returning a compact, structured assessment. The key never
 * reaches the browser — this module is imported only by route handlers.
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

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

export async function aiReview(
  report: Pick<ValidationReport, "status" | "score" | "violations" | "recommendations" | "simulationType" | "checks">,
  conditions: Record<string, unknown>,
): Promise<AiReview> {
  const key = process.env.OPENROUTER_API_KEY;
  if (!key) return { enabled: false };

  const model = process.env.OPENROUTER_MODEL || "anthropic/claude-3.5-haiku";
  const prompt = `You are a physics simulation reviewer. A deterministic engine validated a ${report.simulationType} simulation and returned status "${report.status}" (score ${report.score}/100).

Conditions submitted:
${JSON.stringify(conditions, null, 2)}

Checks that were not passed:
${JSON.stringify(report.violations, null, 2)}

Decide whether the deterministic verdict is physically and logically correct, and whether anything important was missed. Respond ONLY with JSON:
{
  "status": "agree" | "concern" | "disagree",
  "assessment": "2-3 sentence plain-English judgement",
  "concerns": ["specific issues the rules may have missed, if any"]
}`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20_000);
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
        max_tokens: 700,
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
