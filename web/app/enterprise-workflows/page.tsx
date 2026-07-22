"use client";

export default function EnterpriseWorkflows() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 text-white">
      <div className="max-w-5xl mx-auto px-6 py-16">
        {/* Hero */}
        <div className="mb-16">
          <h1 className="text-5xl font-bold mb-4">Enterprise Workflows</h1>
          <p className="text-xl text-slate-300">
            Best practices for integrating SimAPI into production simulation pipelines.
          </p>
        </div>

        {/* Workflow 1 */}
        <div className="mb-12 bg-slate-800/50 rounded-lg p-8 border border-slate-700">
          <h2 className="text-3xl font-bold mb-4 text-blue-400">1. Pre-Simulation Validation (Mesh Prep)</h2>
          <div className="space-y-4 text-slate-300">
            <p>
              <strong>Phase:</strong> Before solver execution
            </p>
            <p>
              <strong>Goal:</strong> Catch geometry and boundary condition errors early, avoiding expensive solver runs.
            </p>
            <div className="bg-slate-900/50 rounded p-4 font-mono text-sm">
              <div>1. Upload CAD/mesh (STL, STEP, CGNS)</div>
              <div>2. POST /v1/validate/setup → mesh quality checks</div>
              <div>3. Inspect preflight results (watertight, BC coverage, solver config)</div>
              <div>4. Fix issues or proceed to solver</div>
            </div>
            <p>
              <strong>Benefit:</strong> Reduce solver restarts by 40–60%; catch setup errors before 8-hour runs.
            </p>
          </div>
        </div>

        {/* Workflow 2 */}
        <div className="mb-12 bg-slate-800/50 rounded-lg p-8 border border-slate-700">
          <h2 className="text-3xl font-bold mb-4 text-blue-400">2. Post-Simulation QA (Result Validation)</h2>
          <div className="space-y-4 text-slate-300">
            <p>
              <strong>Phase:</strong> After solver convergence
            </p>
            <p>
              <strong>Goal:</strong> Automatically flag anomalous results before they propagate to downstream analysis or reports.
            </p>
            <div className="bg-slate-900/50 rounded p-4 font-mono text-sm">
              <div>1. Extract results (csv/netCDF from solver output)</div>
              <div>2. POST /v1/validate → physics validation + AI review</div>
              <div>3. Inspect exclusion list (flagged trials)</div>
              <div>4. Route clean results to post-processing; flag corruptions for review</div>
            </div>
            <p>
              <strong>Benefit:</strong> Achieve 99% detection of mesh corruption, solver NaNs, and unit errors. Training-ready flagging.
            </p>
          </div>
        </div>

        {/* Workflow 3 */}
        <div className="mb-12 bg-slate-800/50 rounded-lg p-8 border border-slate-700">
          <h2 className="text-3xl font-bold mb-4 text-blue-400">3. Continuous Integration (Regression Detection)</h2>
          <div className="space-y-4 text-slate-300">
            <p>
              <strong>Phase:</strong> On each code commit or parameter change
            </p>
            <p>
              <strong>Goal:</strong> Detect unintended changes in simulation behavior (solver upgrade, config drift, etc.).
            </p>
            <div className="bg-slate-900/50 rounded p-4 font-mono text-sm">
              <div>1. Wire SimAPI into GitHub Actions / GitLab CI pipeline</div>
              <div>2. Run benchmark suite with frozen config</div>
              <div>3. Compare MAPE, precision, recall against baseline</div>
              <div>4. Block merge if metrics regress >5%</div>
            </div>
            <p>
              <strong>Benefit:</strong> Catch solver bugs, config creep, and mesh quality drift before production release.
            </p>
          </div>
        </div>

        {/* Workflow 4 */}
        <div className="mb-12 bg-slate-800/50 rounded-lg p-8 border border-slate-700">
          <h2 className="text-3xl font-bold mb-4 text-blue-400">4. Regulatory Compliance (Audit Trail)</h2>
          <div className="space-y-4 text-slate-300">
            <p>
              <strong>Phase:</strong> For safety-critical domains (automotive, aerospace, medical devices)
            </p>
            <p>
              <strong>Goal:</strong> Generate evidence of data quality and anomaly detection for regulatory submissions.
            </p>
            <div className="bg-slate-900/50 rounded p-4 font-mono text-sm">
              <div>1. Validate all simulation datasets with SimAPI</div>
              <div>2. Export signed validation report (SHA-256 fingerprint)</div>
              <div>3. Archive as permanent compliance artifact</div>
              <div>4. Include in submission package (FDA 21 CFR Part 11, ISO 26262)</div>
            </div>
            <p>
              <strong>Benefit:</strong> Regulatory auditors see exact exclusion logic and detection confidence.
            </p>
          </div>
        </div>

        {/* Integration Patterns */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold mb-6">Integration Patterns</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[
              {
                title: "Synchronous (Real-Time Feedback)",
                desc: "POST request → validation → immediate response. Best for interactive UIs and human-in-the-loop review.",
                tech: "HTTP POST, WebSocket (long-poll support)",
              },
              {
                title: "Asynchronous (Batch Processing)",
                desc: "Queue validation jobs, poll for results. Ideal for high-volume batch runs or resource-constrained systems.",
                tech: "Job queue, webhooks, polling API",
              },
              {
                title: "Embedded (Python/Node SDK)",
                desc: "Import SimAPI directly into your pipeline script. No network latency; full offline capability.",
                tech: "Python pkg, Node.js, CLI tool",
              },
              {
                title: "Plugin (Solver Integration)",
                desc: "Post-processing hook inside solver (OpenFOAM, ANSYS, COMSOL). Inline validation without export.",
                tech: "Native plugin, Docker sidecar",
              },
            ].map((p, i) => (
              <div key={i} className="bg-slate-800/30 rounded-lg p-6 border border-slate-700/50">
                <h3 className="font-bold text-lg mb-2 text-blue-400">{p.title}</h3>
                <p className="text-sm text-slate-400 mb-3">{p.desc}</p>
                <div className="text-xs text-slate-500 font-mono">{p.tech}</div>
              </div>
            ))}
          </div>
        </div>

        {/* SLA & Benchmarks */}
        <div className="bg-gradient-to-r from-blue-900/20 to-purple-900/20 rounded-lg p-8 border border-blue-500/20">
          <h2 className="text-2xl font-bold mb-4">Enterprise SLAs</h2>
          <ul className="space-y-2 text-slate-300">
            <li>✓ <strong>P99 latency:</strong> 2s (synchronous validation on 1K rows)</li>
            <li>✓ <strong>Throughput:</strong> 1M rows/min (batched, offline)</li>
            <li>✓ <strong>Availability:</strong> 99.9% (SLA for managed cloud deployments)</li>
            <li>✓ <strong>Detection precision:</strong> 99% (false-positive rate &lt;1%)</li>
            <li>✓ <strong>Regex audit log:</strong> All validation decisions logged for compliance</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
