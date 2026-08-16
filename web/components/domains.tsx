/*
 * The 21 simulation domains the engine ships bounds and relations for. This
 * list is the real SimulationType enum from core/physics_validator.py — kept in
 * sync by hand; adding a domain there is what earns a row here. Flat, no cards,
 * no icons: a dense typographic index of coverage.
 */

const DOMAINS: string[] = [
  "Aerodynamics",
  "Fluid dynamics / CFD",
  "Structural / FEA",
  "Thermodynamics",
  "Robotics / control",
  "Combustion",
  "Acoustics",
  "Electromagnetics",
  "Geomechanics",
  "Biomechanics",
  "Nuclear",
  "Plasma",
  "Chemical reactor",
  "Hydrodynamics",
  "Meteorology",
  "Astrophysics",
  "Materials",
  "Tribology",
  "Aeroelasticity",
  "Cryogenics",
  "Multiphysics",
];

export function Domains() {
  return (
    <section className="relative border-t border-white/[0.06] py-24 sm:py-32">
      <div className="container-tight">
        <h2 className="max-w-2xl text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          21 simulation domains, one contract
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-white/55">
          Each domain carries its own plausibility envelope, conservation relations, and unit
          conventions. The dimensional engine resolves column names to SI units and discovers the
          governing dimensionless groups from the data itself — so a new domain is added as data
          (column-name patterns and constants), not new code.
        </p>

        <ul className="mt-10 grid grid-cols-2 gap-x-8 border-t border-white/[0.06] sm:grid-cols-3 lg:grid-cols-4">
          {DOMAINS.map((d, i) => (
            <li
              key={d}
              className="flex items-baseline gap-3 border-b border-white/[0.06] py-3 text-sm text-white/75"
            >
              <span className="font-mono text-xs tabular-nums text-white/30">
                {String(i + 1).padStart(2, "0")}
              </span>
              {d}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
