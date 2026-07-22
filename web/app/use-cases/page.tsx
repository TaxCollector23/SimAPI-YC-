"use client";

export default function UseCases() {
  const cases = [
    {
      domain: "Aerospace & Defense",
      company: "Tier-1 OEM",
      problem: "CFD simulations for wing aerodynamics were failing validation 15% of the time due to mesh generation bugs. Each failure cost 8 hours of solver time and human investigation.",
      solution: "Integrated SimAPI mesh-validation (preflight) into pre-solver pipeline. Deployed on 500 simulations/week.",
      results: [
        "Mesh errors caught before solver execution (100% precision)",
        "Solver restarts eliminated → 8h/failure × 75 failures/year = 600h saved",
        "Confidence score added to every result for regulatory submissions",
        "Deployment: 2 API calls, 0 code changes needed",
      ],
      impact: "350% ROI (annual)",
    },
    {
      domain: "Automotive",
      company: "EV Battery Manufacturer",
      problem: "Thermal and electrochemical simulations produced occasional NaN and unit-error results. Manual flagging by domain experts took 2–3 hours per batch (50 simulations).",
      solution: "Deployed SimAPI post-solver validation with AI anomaly detection. Integrated via Python SDK into batch pipeline.",
      results: [
        "Automated detection of 11 corruption types (NaN, unit mismatch, solver divergence, etc.)",
        "False positive rate <0.5% (tuned for precision > recall in safety context)",
        "Reduced manual review time from 3h to 10 min per batch → 95% time saving",
        "AI layer explains *why* each result was flagged (causal diagnosis)",
      ],
      impact: "~$180K annual labor savings",
    },
    {
      domain: "Semiconductor & Photonics",
      company: "Fab Design Team",
      problem: "Optical and electromagnetic simulations for chip design had no anomaly detection. Silently bad results occasionally made it into sign-off, discovered too late in tape-out.",
      solution: "Wrapped SimAPI validation into the verification checkpoint. Added to CI/CD on every design iteration.",
      results: [
        "Caught 7 corrupted simulation batches that would have passed manual review",
        "Regression testing on solver upgrades (COMSOL 5.x → 6.x) validated correctness",
        "Confidence scores provided for design decision sign-off",
        "Integrated dashboards show validation health over 12-month design cycle",
      ],
      impact: "1 tape-out re-spin avoided (~$2M saved)",
    },
    {
      domain: "Civil & Structural Engineering",
      company: "Consulting Firm (200+ engineers)",
      problem: "FEA models for bridges, dams, buildings had no centralized QA. Different teams used different assumptions, leading to inconsistent results and client-facing errors.",
      solution: "Deployed SimAPI as a centralized validation service. Trained all engineers on best practices via dashboard UI.",
      results: [
        "Unified validation across 12 engineering disciplines",
        "Policy: every model must achieve 'PASSED' status before client delivery",
        "Caught 31 methodology errors in first 6 months (e.g., unit mismatches, BC inconsistencies)",
        "Insurance premium reduced (lower litigation risk)",
        "All 200 engineers now speak same language for data quality",
      ],
      impact: "Eliminated ~$400K/year in rework and liability risk",
    },
    {
      domain: "Materials Science & Chemistry",
      company: "Research Lab (PhD students)",
      problem: "Molecular dynamics simulations had high rates of invalid trajectories. Hard to distinguish algorithmic bugs from rare physical phenomena.",
      solution: "Deployed SimAPI for post-MD validation. Used AI review layer to distinguish anomalies from physically plausible outliers.",
      results: [
        "Automated detection of simulation crashes (NaN, divergence)",
        "AI layer provides interpretable feedback ('This looks like NVE energy drift, not a bug')",
        "Publication confidence increased; authors can justify why 'outlier' results were excluded",
        "Reproducibility: validation logs archived with every paper",
      ],
      impact: "3 papers published with higher acceptance confidence; reduced revision rounds",
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

        {/* Case Studies Grid */}
        <div className="space-y-12">
          {cases.map((c, i) => (
            <div
              key={i}
              className="bg-gradient-to-br from-slate-800/60 to-slate-900/60 rounded-lg p-8 border border-slate-700 hover:border-blue-500/50 transition-colors"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="text-sm font-mono text-blue-400 mb-1">{c.domain}</div>
                  <h2 className="text-2xl font-bold">{c.company}</h2>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-green-400">{c.impact}</div>
                  <div className="text-xs text-slate-400">ROI / Savings</div>
                </div>
              </div>

              <div className="space-y-4">
                {/* Problem */}
                <div>
                  <h3 className="font-semibold text-slate-300 text-sm uppercase tracking-wide mb-2">
                    Problem
                  </h3>
                  <p className="text-slate-300">{c.problem}</p>
                </div>

                {/* Solution */}
                <div>
                  <h3 className="font-semibold text-slate-300 text-sm uppercase tracking-wide mb-2">
                    Solution
                  </h3>
                  <p className="text-slate-300">{c.solution}</p>
                </div>

                {/* Results */}
                <div>
                  <h3 className="font-semibold text-slate-300 text-sm uppercase tracking-wide mb-2">
                    Results
                  </h3>
                  <ul className="space-y-2">
                    {c.results.map((r, j) => (
                      <li key={j} className="flex items-start gap-3 text-slate-300">
                        <span className="text-green-400 font-bold mt-1">✓</span>
                        <span>{r}</span>
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
