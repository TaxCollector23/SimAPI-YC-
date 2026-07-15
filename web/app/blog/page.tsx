import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";

export const metadata: Metadata = {
  title: "The SimAPI Journal",
  description:
    "Practical notes on validating simulations: what SimAPI is for, who should use it, the ideal workflow, and install tips.",
};

interface Note {
  tag: string;
  title: string;
  body: React.ReactNode;
}

const notes: Note[] = [
  {
    tag: "Overview",
    title: "What SimAPI is for",
    body: (
      <>
        <p>
          SimAPI checks simulation output against physical laws before anyone trusts it.
          You send the results of a run — drag coefficients, stresses, temperatures,
          joint torques — and it returns a verdict: <strong>passed</strong>,{" "}
          <strong>warning</strong>, or <strong>failed</strong>, with the specific values
          and bounds that were violated.
        </p>
        <p>
          It is not a solver and it does not replace engineering judgment. It is the
          automated gate that catches the obvious-in-hindsight failures — a diverged run,
          a unit-conversion slip, a saturated sensor, an efficiency above 1.0 — that
          otherwise slip into a design review or an ML dataset.
        </p>
      </>
    ),
  },
  {
    tag: "Who",
    title: "Who should use it",
    body: (
      <ul>
        <li>
          <strong>Simulation engineers</strong> who run sweeps and want a fast sanity gate
          before sharing results.
        </li>
        <li>
          <strong>ML teams</strong> building surrogate models on simulation data, who need
          to exclude physically invalid trials from training sets.
        </li>
        <li>
          <strong>Platform / infra teams</strong> adding a validation step to a CI pipeline
          so bad runs fail the build instead of reaching production.
        </li>
        <li>
          <strong>Reviewers</strong> who want an auditable, reproducible second opinion
          rather than eyeballing spreadsheets.
        </li>
      </ul>
    ),
  },
  {
    tag: "Workflow",
    title: "The ideal workflow",
    body: (
      <ol>
        <li>Run your solver as usual and export results (CSV, JSON, VTK, NumPy, OpenFOAM).</li>
        <li>
          Call <code>POST /v1/validate</code> — from a CI step, a data job, the CLI, or the
          in-browser validator on the dashboard.
        </li>
        <li>
          Branch on the verdict: block the merge or exclude trials when the status is{" "}
          <code>failed</code>; surface warnings for review.
        </li>
        <li>
          Feed only the <code>training_ready</code> trials into downstream design decisions
          or ML pipelines.
        </li>
      </ol>
    ),
  },
  {
    tag: "Where it fits",
    title: "Domains and use cases",
    body: (
      <ul>
        <li><strong>Aerospace:</strong> validate CFD drag/lift sweeps against physical envelopes before they enter design review or a surrogate model.</li>
        <li><strong>Robotics:</strong> gate controller simulations on joint-torque, tracking-error, and stability checks before hardware deployment.</li>
        <li><strong>Automotive:</strong> screen aero and thermal runs nightly; block regressions from reaching the vehicle program.</li>
        <li><strong>Energy:</strong> verify combustion, heat-exchanger, and structural results against conservation laws.</li>
        <li><strong>Scientific computing:</strong> catch solver divergence and unit-conversion errors before results are published or reused.</li>
        <li><strong>Digital twins:</strong> continuously validate live simulation streams so the twin never drifts from physical plausibility.</li>
      </ul>
    ),
  },
  {
    tag: "Install tips",
    title: "Getting set up",
    body: (
      <>
        <ul>
          <li>Try it with zero setup: run a validation in the browser from the dashboard.</li>
          <li>
            Python: <code>pip install simapi</code>, then{" "}
            <code>from simapi import SimAPI</code>.
          </li>
          <li>
            Node/CLI: <code>npm install -g simapi-cli</code>, then <code>simapi login</code> and{" "}
            <code>simapi validate run.json</code>.
          </li>
          <li>
            Keep your key in the <code>SIMAPI_API_KEY</code> environment variable — never
            commit it. In CI, set it as a secret.
          </li>
          <li>
            Column names are normalized automatically (<code>Cd</code>, <code>cd</code>, and{" "}
            <code>drag_coefficient</code> all map to the same quantity), so you rarely need
            to rename anything.
          </li>
        </ul>
      </>
    ),
  },
];

export default function BlogPage() {
  return (
    <>
      <PageHero
        eyebrow="Blog"
        title={<>The SimAPI Journal</>}
        lede="Practical, no-nonsense notes for people using SimAPI — what it's for, who it's for, and how to get the most out of it."
      />
      <section className="container-tight space-y-6 pb-24">
        {notes.map((n, i) => (
          <Reveal key={n.title} delay={i * 0.04}>
            <article className="rounded-2xl border border-white/[0.07] bg-ink-900/50 p-7">
              <span className="rounded-full border border-white/10 px-2.5 py-0.5 text-[11px] text-white/50">
                {n.tag}
              </span>
              <h2 className="mt-3 text-xl font-semibold text-white">{n.title}</h2>
              <div className="prose-journal mt-3 space-y-3 text-sm leading-relaxed text-white/55 [&_code]:rounded [&_code]:bg-white/[0.06] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12px] [&_code]:text-white/80 [&_li]:ml-4 [&_li]:list-disc [&_ol_li]:list-decimal [&_strong]:text-white/80 [&_ul]:space-y-1.5 [&_ol]:space-y-1.5">
                {n.body}
              </div>
            </article>
          </Reveal>
        ))}
      </section>
    </>
  );
}
