"use client";

export default function UseCases() {
  const cases = [
    {
      domain: "Aerospace & Defense",
      workflow: "Pre-Flight Mesh Validation",
      problem: "Mesh generation bugs lead to invalid CFD results. Manual inspection of mesh quality can take hours per simulation.",
      solution: "Use SimAPI's preflight checks to catch mesh errors (watertight, BC coverage, solver config) before expensive solver runs.",
      benefits: [
        "Automated detection of 30+ mesh quality issues",
        "Solver restarts avoided when mesh is validated first",
        "Confidence score tracked for regulatory audit trails",
        "Integration via 2 API calls, no code changes required",
      ],
    },
    {
      domain: "Automotive & Energy",
      workflow: "Thermal/Chemical Simulation QA",
      problem: "Batch simulation jobs occasionally produce NaN, divergence, or unit-error results that must be manually identified.",
      solution: "Deploy SimAPI post-solver to automatically flag corrupted trials and explain why each was excluded.",
      benefits: [
        "Detects 11+ corruption types (NaN, solver divergence, physics law violations)",
        "99% precision (< 1% false-positive rate)",
        "Reduces manual review time significantly vs. per-dataset inspection",
        "AI layer explains findings in plain language",
      ],
    },
    {
      domain: "Semiconductors & Photonics",
      workflow: "Design Iteration Regression Testing",
      problem: "Optical/EM simulations for chip design have no automated QA. Bad results can slip into tape-out decisions.",
      solution: "Integrate SimAPI into CI/CD: validate every simulation on each design iteration, flag regressions.",
      benefits: [
        "Catch corrupted datasets that would pass visual inspection",
        "Regression testing on solver/library upgrades",
        "Confidence scores added to design decisions",
        "Validation history dashboard for design reviews",
      ],
    },
    {
      domain: "Civil & Structural",
      workflow: "Cross-Team Validation Standards",
      problem: "Multiple teams run FEA independently with different assumptions, assumptions drift over time, inconsistent results.",
      solution: "Centralized SimAPI validation policy: all models must pass before delivery. Unify methodology across disciplines.",
      benefits: [
        "Catch methodology errors (unit mismatches, BC inconsistencies)",
        "Single source of truth for data quality standards",
        "Training and best-practice guidance via dashboard UI",
        "Audit trail for client submissions",
      ],
    },
    {
      domain: "Research & Academia",
      workflow: "Publication-Ready Validation",
      problem: "MD, computational chemistry simulations have high outlier rates. Hard to distinguish simulation bugs from rare physics.",
      solution: "Use SimAPI's AI layer to classify anomalies: divergence vs. physically plausible rare events. Archive validation log with paper.",
      benefits: [
        "Automated detection of clear simulation failures",
        "AI provides interpretable feedback (e.g., 'This looks like energy drift, not a crash')",
        "Validation methodology documented for peer review",
        "Reproducibility: validation logs archived alongside paper",
      ],
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 text-white">
      <div className="max-w-6xl mx-auto px-6 py-16">
        {/* Hero */}
        <div className="mb-16 text-center">
          <h1 className="text-5xl font-bold mb-4">Use Cases & Impact</h1>
          <p className="text-xl text-slate-300 max-w-2xl mx-auto">
            How enterprises and research teams use SimAPI to eliminate invalid results, catch silent failures, and build confidence in simulation data.
          </p>
        </div>

        {/* Use Cases Grid */}
        <div className="space-y-12">
          {cases.map((c, i) => (
            <div
              key={i}
              className="bg-gradient-to-br from-slate-800/60 to-slate-900/60 rounded-lg p-8 border border-slate-700 hover:border-blue-500/50 transition-colors"
            >
              <div className="mb-4">
                <div className="text-sm font-mono text-blue-400 mb-1">{c.domain}</div>
                <h2 className="text-2xl font-bold">{c.workflow}</h2>
              </div>

              <div className="space-y-4">
                {/* Problem */}
                <div>
                  <h3 className="font-semibold text-slate-300 text-sm uppercase tracking-wide mb-2">
                    Challenge
                  </h3>
                  <p className="text-slate-300">{c.problem}</p>
                </div>

                {/* Solution */}
                <div>
                  <h3 className="font-semibold text-slate-300 text-sm uppercase tracking-wide mb-2">
                    Approach
                  </h3>
                  <p className="text-slate-300">{c.solution}</p>
                </div>

                {/* Benefits */}
                <div>
                  <h3 className="font-semibold text-slate-300 text-sm uppercase tracking-wide mb-2">
                    Benefits
                  </h3>
                  <ul className="space-y-2">
                    {c.benefits.map((b, j) => (
                      <li key={j} className="flex items-start gap-3 text-slate-300">
                        <span className="text-blue-400 font-bold mt-1">→</span>
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Key Metrics */}
        <div className="mt-20 bg-gradient-to-r from-purple-900/30 to-blue-900/30 rounded-lg p-12 border border-purple-500/20">
          <h2 className="text-3xl font-bold mb-8 text-center">Why Teams Choose SimAPI</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              { label: "99% Precision", desc: "False-positive rate < 1%" },
              { label: "7 Domains", desc: "CFD, FEA, MD, EM, and more" },
              { label: "730+ Checks", desc: "Physics laws + anomalies" },
              { label: "5 min Integration", desc: "API call or CLI" },
            ].map((m, i) => (
              <div key={i} className="text-center">
                <div className="text-3xl font-bold text-blue-400 mb-2">{m.label}</div>
                <div className="text-sm text-slate-400">{m.desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="mt-16 text-center">
          <h2 className="text-2xl font-bold mb-4">Ready to validate your simulations?</h2>
          <div className="flex gap-4 justify-center flex-wrap">
            <a
              href="/play"
              className="px-8 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold transition-colors"
            >
              Try the Playground
            </a>
            <a
              href="/docs"
              className="px-8 py-3 bg-slate-700 hover:bg-slate-600 rounded-lg font-semibold transition-colors"
            >
              Read the Docs
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
