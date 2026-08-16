import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/ui/page-hero";
import { ArrowUpRight } from "lucide-react";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Documentation",
  description:
    "SimAPI documentation — quickstart, endpoint reference, the verdict model, the error contract, and the CLI.",
};

const DOCS = "https://simapidocs.github.io";

function Code({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto border border-white/10 bg-ink-900/60 p-4 text-[13px] leading-relaxed text-white/80">
      <code className="font-mono">{children}</code>
    </pre>
  );
}

function Anchor({ id }: { id: string }) {
  return <span id={id} className="block -translate-y-28" />;
}

const endpoints: { method: string; path: string; desc: string }[] = [
  { method: "GET", path: "/v1/health", desc: "Liveness and service facts. Unauthenticated." },
  { method: "GET", path: "/v1/metrics", desc: "Prometheus metrics (plain text)." },
  { method: "POST", path: "/v1/validate", desc: "Validate a JSON batch of trials. Runs both engines, optionally the AI layer." },
  { method: "POST", path: "/v1/validate/upload", desc: "Validate an uploaded CSV / JSON / VTK / NumPy / OpenFOAM file." },
  { method: "POST", path: "/v1/validate/physics-only", desc: "Both engines, AI layer disabled (run_ai=false)." },
  { method: "POST", path: "/v1/validate/dimensional", desc: "Dimensional engine only — raw per-layer report (discovered laws, units resolution, condition assertions, training suitability)." },
  { method: "POST", path: "/v1/validate/setup", desc: "Pre-flight mesh + solver + physics setup validation with predicted output-corruption risk." },
  { method: "POST", path: "/v1/repair", desc: "Structural repair. Previews proposals by default; apply=true returns the repaired dataset." },
  { method: "POST", path: "/v1/demo", desc: "Validate seeded, physically coupled synthetic aerodynamics data." },
  { method: "GET", path: "/v1/job/{id}", desc: "Fetch a job's physics result." },
  { method: "GET", path: "/v1/job/{id}/ai", desc: "Poll for the async AI result." },
  { method: "GET", path: "/v1/jobs", desc: "List recent jobs, newest first (limit / offset pagination)." },
];

const errorCodes: { code: string; status: string; when: string }[] = [
  { code: "invalid_request", status: "400", when: "Malformed payload or unknown simulation type." },
  { code: "unauthorized", status: "401", when: "Auth is required and the X-API-Key is missing or wrong." },
  { code: "payload_too_large", status: "413", when: "Rows exceed SIMAPI_MAX_ROWS or upload exceeds SIMAPI_MAX_UPLOAD_BYTES." },
  { code: "rate_limited", status: "429", when: "Token-bucket rate limit exceeded. Slow down and retry." },
  { code: "internal_error", status: "500", when: "Unexpected server fault. The request_id correlates to server logs." },
];

export default function DocsPage() {
  return (
    <>
      <PageHero
        title={<>Build on SimAPI</>}
        lede="Install the CLI, POST a batch of trials, and read a structured verdict. This page is the short reference; the full API docs and SDK guides live on the docs site."
      >
        <div className="mt-2 flex flex-wrap gap-4">
          <a href={DOCS} className="btn-accent">
            Full docs <ArrowUpRight className="h-4 w-4" />
          </a>
          <a href={site.github} className="btn-ghost">
            View source <ArrowUpRight className="h-4 w-4" />
          </a>
        </div>
      </PageHero>

      <div className="container-tight pb-24">
        <div className="grid gap-12 lg:grid-cols-[180px_1fr]">
          {/* on-page nav */}
          <nav className="hidden lg:block">
            <div className="sticky top-28 space-y-2 text-sm">
              {[
                ["Quickstart", "quickstart"],
                ["Validate a run", "validate"],
                ["Endpoints", "endpoints"],
                ["Verdict model", "verdict"],
                ["Error contract", "errors"],
                ["CLI", "cli"],
              ].map(([label, id]) => (
                <a key={id} href={`#${id}`} className="block text-white/45 transition-colors hover:text-white">
                  {label}
                </a>
              ))}
            </div>
          </nav>

          <div className="min-w-0 space-y-16">
            {/* Quickstart */}
            <section>
              <Anchor id="quickstart" />
              <h2 className="text-xl font-semibold text-white">Quickstart</h2>
              <p className="mt-3 text-sm leading-relaxed text-white/60">
                The CLI is the fastest way in. It talks to the hosted API, which is currently open —
                no key required to evaluate.
              </p>
              <div className="mt-4">
                <Code>{`# Install the CLI (Node 18+)
npm install -g simapi-cli

# Validate a simulation output file
simapi validate cfd_output.csv --type aerodynamics

# Run the dimensional-analysis engine directly on a CSV
simapi dimensional cfd_output.csv --conditions velocity=15,altitude=120`}</Code>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-white/60">
                Prefer HTTP? Every endpoint is a plain JSON POST. Prefer a library? The{" "}
                <a href={DOCS} className="text-accent-blue underline underline-offset-2">
                  Python and Node SDKs
                </a>{" "}
                wrap the same API. To point any of them at a self-hosted deployment, set{" "}
                <code className="font-mono text-white/80">SIMAPI_BASE_URL</code> (and{" "}
                <code className="font-mono text-white/80">SIMAPI_API_KEY</code> if that deployment
                enforces auth).
              </p>
            </section>

            {/* Validate a run */}
            <section>
              <Anchor id="validate" />
              <h2 className="text-xl font-semibold text-white">Validate a run over HTTP</h2>
              <p className="mt-3 text-sm leading-relaxed text-white/60">
                POST a batch of trials to <code className="font-mono text-white/80">/v1/validate</code>.
                Declare the simulation type, and optionally the known operating conditions of the run
                so they become testable assertions.
              </p>
              <div className="mt-4">
                <Code>{`curl -X POST https://sim-api.vercel.app/api/v1/validate \\
  -H "Content-Type: application/json" \\
  -d '{
    "simulation_type": "aerodynamics",
    "conditions": { "velocity": 15.0, "altitude": 120.0 },
    "data": [
      { "reynolds_number": 2.1e6, "mach_number": 0.44, "drag_coefficient": 0.031 },
      { "reynolds_number": 2.2e6, "mach_number": 0.45, "drag_coefficient": 0.032 }
    ]
  }'`}</Code>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-white/60">
                The default path runs entirely deterministic Python — nothing leaves the machine.
                The AI layer is off unless you set <code className="font-mono text-white/80">run_ai=true</code>{" "}
                and the server has an OpenRouter key configured; without one it reports{" "}
                <code className="font-mono text-white/80">disabled</code> and physics validation is
                unaffected.
              </p>
            </section>

            {/* Endpoints */}
            <section>
              <Anchor id="endpoints" />
              <h2 className="text-xl font-semibold text-white">Endpoints</h2>
              <p className="mt-3 text-sm leading-relaxed text-white/60">
                Interactive docs are served at <code className="font-mono text-white/80">/docs</code>{" "}
                (Swagger) and <code className="font-mono text-white/80">/redoc</code>; the raw schema
                is at <code className="font-mono text-white/80">/openapi.json</code>.
              </p>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[560px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-white/10 text-left text-white/40">
                      <th className="py-2 pr-4 font-medium">Method</th>
                      <th className="py-2 pr-4 font-medium">Path</th>
                      <th className="py-2 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {endpoints.map((e) => (
                      <tr key={e.path + e.method} className="border-b border-white/[0.06] align-top">
                        <td className="py-2.5 pr-4">
                          <span className="font-mono text-xs text-accent-blue">{e.method}</span>
                        </td>
                        <td className="py-2.5 pr-4">
                          <code className="font-mono text-xs text-white/80">{e.path}</code>
                        </td>
                        <td className="py-2.5 text-white/55">{e.desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Verdict model */}
            <section>
              <Anchor id="verdict" />
              <h2 className="text-xl font-semibold text-white">The verdict model</h2>
              <p className="mt-3 text-sm leading-relaxed text-white/60">
                Every validation returns one top-level status plus per-row classification.
              </p>
              <div className="mt-4">
                <Code>{`status           passed | warning | failed
confidence       high | medium | low
training_ready   bool  — false if any row is impossible

# Per-row classes (dimensional engine)
impossible                  violates a definition or a hard physical bound
inconsistent                contradicts a discovered law, an anchored constant,
                            or a declared condition
unsuitable_for_training     structurally fine, but unfit as training data`}</Code>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-white/60">
                The report also carries{" "}
                <code className="font-mono text-white/80">trials_submitted / valid / excluded</code>,
                an <code className="font-mono text-white/80">exclusion_rate</code>, per-column{" "}
                <code className="font-mono text-white/80">statistics</code> (mean, std, median,
                p5/p95, skewness, kurtosis, CV), the <code className="font-mono text-white/80">exclusions</code>{" "}
                with reasons, and <code className="font-mono text-white/80">provenance</code> (which
                ingestion aliases were applied, which checks ran). Non-finite statistics serialize as{" "}
                <code className="font-mono text-white/80">null</code> rather than crashing.
              </p>
              <div className="mt-4 border-l-2 border-white/15 pl-4 text-sm leading-relaxed text-white/50">
                A clean report means <em>consistent with itself, with physical constants, and with the
                declared conditions</em>. It does not mean <em>physically correct</em> — a run that
                used the wrong model can be dimensionally perfect and still wrong. That boundary is
                stated in every report (<code className="font-mono text-white/70">known_impossible</code>).
              </div>
            </section>

            {/* Error contract */}
            <section>
              <Anchor id="errors" />
              <h2 className="text-xl font-semibold text-white">Error contract</h2>
              <p className="mt-3 text-sm leading-relaxed text-white/60">
                Every error returns the same envelope with a stable{" "}
                <code className="font-mono text-white/80">code</code>, a message, and a{" "}
                <code className="font-mono text-white/80">request_id</code> that correlates to the
                server logs.
              </p>
              <div className="mt-4">
                <Code>{`{
  "error": {
    "code": "rate_limited",
    "message": "Rate limit exceeded. Slow down and retry.",
    "request_id": "3f9c…"
  }
}`}</Code>
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[520px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-white/10 text-left text-white/40">
                      <th className="py-2 pr-4 font-medium">Code</th>
                      <th className="py-2 pr-4 font-medium">HTTP</th>
                      <th className="py-2 font-medium">When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {errorCodes.map((e) => (
                      <tr key={e.code} className="border-b border-white/[0.06] align-top">
                        <td className="py-2.5 pr-4">
                          <code className="font-mono text-xs text-white/80">{e.code}</code>
                        </td>
                        <td className="py-2.5 pr-4 font-mono text-xs text-white/60">{e.status}</td>
                        <td className="py-2.5 text-white/55">{e.when}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* CLI */}
            <section>
              <Anchor id="cli" />
              <h2 className="text-xl font-semibold text-white">CLI reference</h2>
              <p className="mt-3 text-sm leading-relaxed text-white/60">
                The <code className="font-mono text-white/80">simapi-cli</code> package installs a{" "}
                <code className="font-mono text-white/80">simapi</code> binary. Both{" "}
                <code className="font-mono text-white/80">validate</code> and{" "}
                <code className="font-mono text-white/80">dimensional</code> accept{" "}
                <code className="font-mono text-white/80">--fail-on</code>, which drives the exit
                code — this is what the{" "}
                <Link href="/enterprise-workflows" className="text-accent-blue underline underline-offset-2">
                  CI gate
                </Link>{" "}
                is built on.
              </p>
              <div className="mt-4">
                <Code>{`simapi validate <file>            # validate JSON/CSV/TXT, print a report
simapi dimensional <file>        # dimensional engine on a CSV/JSON
simapi repair <file> [--apply]   # preview or apply structural repairs
simapi watch <file>              # re-validate on change
simapi usage                     # requests, quota, average time
simapi doctor [--fix]            # diagnose config and connectivity

# Exit-code gate for CI
simapi validate out.csv --type aerodynamics --fail-on failed
#   exit 0  verdict passed (or only warnings)
#   exit 1  verdict failed  — physics violations present`}</Code>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-white/60">
                <code className="font-mono text-white/80">--fail-on warning</code> is stricter: it
                exits non-zero on any impossible <em>or</em> inconsistent row. A ready-to-copy GitHub
                Action wrapping this lives in{" "}
                <code className="font-mono text-white/80">integrations/github-action/</code>.
              </p>
            </section>
          </div>
        </div>
      </div>
    </>
  );
}
