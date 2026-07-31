"""
Layer 0 -- units resolution.

Maps column names (real solver output: `Cd`, `p_static`, `U_mag`, `rho_inf`,
`nut`, `yPlus`, `tau_wall`, `Re_c` -- not idealised names) to SI dimension
vectors, with a confidence score and, where the column is in non-SI units,
the conversion applied.

Resolution is dictionary/regex-driven by default (fast, deterministic, no
network dependency -- required for the <10s/80-column budget and for tests
to run without an API key). An LLM callable can be injected for columns the
dictionary can't classify; its output is still subject to Layer 2/3 numeric
verification ("the LLM proposes; linear algebra disposes"), so a wrong LLM
guess degrades to a units_conflict finding rather than corrupting the run.

Low confidence propagates: anything below CONFIDENCE_FLOOR is excluded from
Layers 1-3 and handled only by Layer 5 (response surface) and Layer 8
(structural). Unknown columns are not errors -- they pass through.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from .dimensions import BASE_DIMENSIONS, DIMENSIONLESS, UNIT_CONVERSIONS, Dim

CONFIDENCE_FLOOR = 0.5


@dataclass
class ColumnUnits:
    column: str
    dimension: Dim | None
    confidence: float
    source: str  # "dictionary" | "llm" | "unresolved"
    unit_label: str = ""
    si_scale: float = 1.0
    si_offset: float = 0.0
    notes: str = ""

    @property
    def usable(self) -> bool:
        return self.dimension is not None and self.confidence >= CONFIDENCE_FLOOR


@dataclass
class UnitsResolution:
    columns: dict[str, ColumnUnits] = field(default_factory=dict)

    def usable_columns(self) -> list[str]:
        return [c for c, u in self.columns.items() if u.usable]


# (regex, dimension key, confidence, unit-suffix hint or None)
# Ordered most-specific first; first match wins. Patterns are case-insensitive
# and tolerant of the underscores/prefixes real solvers actually emit.
_PATTERNS: list[tuple[str, str, float]] = [
    # Dimensionless coefficients -- extremely common in CFD/FEA exports.
    (r"^(cd|cl|cp|cm|c[fdlmnpst]_?\w*|cx|cy|cz)$", "dimensionless", 0.95),
    (r"coeff?icient|_coef|_ratio|^ratio$|_factor|^factor$|_fraction|"
     r"^fraction$|efficiency|^eta$|utilization|porosity|void_fraction|"
     r"^conversion$|conversion_rate|_conversion",
     "dimensionless", 0.85),
    (r"^(mach|ma|m_inf)$", "dimensionless", 0.95),
    (r"mach_?number", "dimensionless", 0.95),
    (r"^re(_c|_x|_l|_d|_theta)?$", "dimensionless", 0.9),
    (r"^reynolds(_number)?$", "dimensionless", 0.9),
    (r"nusselt|prandtl|grashof|rayleigh|weber|froude|strouhal|"
     r"schmidt|sherwood|biot|womersley|knudsen|damkohler|lewis",
     "dimensionless", 0.9),
    (r"y_?plus", "dimensionless", 0.9),
    (r"^nut$|nu_t|eddy_visc.*ratio", "dimensionless", 0.6),
    (r"^(angle|aoa|beta|alpha|attack)(_\w+)?$|_(angle|aoa)$", "angle", 0.75),
    # Kinematics -- angular velocity MUST be checked before the generic
    # "velocity" pattern (which otherwise substring-matches it).
    (r"^omega$|^angular_velocity$|^ang_vel$", "angular_velocity", 0.8),
    (r"^(velocity|speed)(_\w+)?$|^(u|v|w)_?(mag|inf|infty)$|^vel_\w+$",
     "velocity", 0.9),
    (r"^(u|v|w)$", "velocity", 0.6),
    (r"^(acceleration|accel)(_\w+)?$", "acceleration", 0.85),
    (r"^(frequency|freq)(_\w+)?$", "frequency", 0.85),
    # Thermo / fluid -- pressure/temperature/density as whole snake_case
    # tokens or well-known solver aliases (p_static, rho_inf, T_wall, ...),
    # never a bare trailing letter of an unrelated word.
    (r"^p(_(static|total|stag|inf|infty|abs|gauge))?$|^pressure(_\w+)?$",
     "pressure", 0.85),
    (r"^dynamic_pressure$|^q_?inf$", "pressure", 0.85),
    (r"^t(_(static|total|stag|inf|infty|wall))?$|^temp(erature)?(_\w+)?$",
     "temperature", 0.75),
    (r"^rho(_(inf|infty|static))?$|^density(_\w+)?$", "density", 0.85),
    (r"^(dynamic_)?viscosity(_\w+)?$", "dynamic_viscosity", 0.8),
    (r"^nu$", "kinematic_viscosity", 0.55),
    (r"^mu$", "dynamic_viscosity", 0.55),
    (r"^(enthalpy|energy)(_\w+)?$", "energy", 0.75),
    (r"^power(_\w+)?$", "power", 0.8),
    (r"^heat_?flux$|^q_?wall$|^tau_?wall$", "heat_flux", 0.8),
    (r"heat_?(load|duty|input|output|generation|dissipation)", "power", 0.6),
    (r"(yield|tensile|compressive|shear|ultimate|flexural)_?strength", "pressure", 0.7),
    (r"^entropy(_\w+)?$", "entropy", 0.8),
    (r"^spec(ific)?_?heat(_\w+)?$|^c_?p$|^c_?v$", "specific_heat", 0.7),
    (r"^thermal_conductivity(_\w+)?$", "thermal_conductivity", 0.6),
    (r"^surf(ace)?_?tension(_\w+)?$|^surftens(_\w+)?$", "surface_tension", 0.75),
    # Mechanics
    (r"^(force|thrust|drag|lift|load)(_\w+)?$", "force", 0.75),
    (r"^(torque|moment)(_\w+)?$", "torque", 0.75),
    (r"^stress(_\w+)?$|^tau_?wall$|^shear_?stress$", "pressure", 0.8),
    (r"^strain(_\w+)?$", "dimensionless", 0.75),
    (r"^mass(_\w+)?$", "mass", 0.75),
    (r"^momentum(_\w+)?$", "momentum", 0.75),
    (r"^area(_\w+)?$", "area", 0.75),
    (r"^volume(_\w+)?$", "volume", 0.7),
    (r"^(length|chord|span|diameter|radius|height|depth|thickness|"
     r"distance|displacement)(_\w+)?$", "length", 0.6),
    (r"^(x|y|z)$", "length", 0.5),
    (r"^time(_\w+)?$|^t_s$", "time", 0.8),
    # EM
    (r"^voltage(_\w+)?$|^volt$", "voltage", 0.8),
    (r"^current(_\w+)?$", "current", 0.55),
    (r"^resistance(_\w+)?$", "resistance", 0.8),
    (r"^capacitance(_\w+)?$", "capacitance", 0.8),
    (r"^inductance(_\w+)?$", "inductance", 0.8),
    (r"^charge(_\w+)?$", "charge", 0.7),
]

# Angle isn't a base dimension in the strict SI sense (radians are
# dimensionless), but treating it as a distinct pseudo-dimension avoids
# nonsense pi-groups pairing an angle with an unrelated dimensionless ratio.
BASE_DIMENSIONS.setdefault("angle", DIMENSIONLESS)

# Unit-suffix detection: column names routinely carry the unit as a suffix
# or bracket, e.g. "pressure_psi", "temp_degF", "altitude_ft".
_UNIT_SUFFIX_RE = re.compile(
    r"[_\[\(]\s*("
    r"psi|bar|atm|mmhg|torr|kpa|mpa|degf|degc|rankine|ft|feet|inch|in|"
    r"yard|mile|nmi|slug_ft3|lbm_ft3|lbf|lbm|slug|rpm|deg|gpm|hp|btu|cal|"
    r"knot|kts|mph"
    r")\s*[\]\)]?$",
    re.IGNORECASE,
)

_SUFFIX_ALIASES = {"feet": "ft", "in": "inch", "kts": "knot"}


# Single-token fallback: the primary _PATTERNS above are precise and
# ordered (e.g. angular velocity must be checked before generic velocity),
# but nearly all of them anchor the keyword at the START of the name
# (^velocity(_\w+)?$), so they cannot match the extremely common
# "descriptive-prefix + quantity" naming style real engineers actually use:
# launch_velocity, flight_time_s, max_height_m, peak_pressure, inlet_temp.
# This is a genuine, high-impact gap (found via adversarial testing: an
# entire test domain had 0% of its columns resolve at all, because every
# column used this naming style) -- not a hypothetical one.
#
# Rather than rewrite every existing anchored pattern (risking regressions
# in already-tested behavior), this is a separate, lower-confidence
# fallback: split the name into underscore/camelCase tokens and check each
# token against this keyword->dimension map. Only used when the primary
# ordered patterns find nothing, so it never overrides a precise match.
_TOKEN_DIMENSION_MAP: dict[str, tuple[str, float]] = {
    "velocity": ("velocity", 0.65), "speed": ("velocity", 0.65),
    "acceleration": ("acceleration", 0.65), "accel": ("acceleration", 0.65),
    "pressure": ("pressure", 0.65), "temperature": ("temperature", 0.6), "temp": ("temperature", 0.55),
    "density": ("density", 0.65), "viscosity": ("dynamic_viscosity", 0.6),
    "force": ("force", 0.55), "thrust": ("force", 0.55), "drag": ("force", 0.5), "lift": ("force", 0.5),
    "torque": ("torque", 0.6), "moment": ("torque", 0.5),
    "stress": ("pressure", 0.6), "strain": ("dimensionless", 0.6),
    "modulus": ("pressure", 0.55), "humidity": ("dimensionless", 0.55),
    "mass": ("mass", 0.6), "momentum": ("momentum", 0.6),
    "area": ("area", 0.6), "volume": ("volume", 0.55),
    "length": ("length", 0.5), "height": ("length", 0.55), "width": ("length", 0.55),
    "depth": ("length", 0.55), "distance": ("length", 0.55), "displacement": ("length", 0.5),
    "range": ("length", 0.5), "radius": ("length", 0.55), "diameter": ("length", 0.55),
    "chord": ("length", 0.55), "span": ("length", 0.55), "altitude": ("length", 0.6), "elevation": ("length", 0.55),
    "time": ("time", 0.6), "duration": ("time", 0.55), "period": ("time", 0.55),
    "energy": ("energy", 0.55), "enthalpy": ("energy", 0.55), "power": ("power", 0.6),
    "frequency": ("frequency", 0.6), "freq": ("frequency", 0.55),
    "angle": ("angle", 0.55), "voltage": ("voltage", 0.6), "current": ("current", 0.45),
    "resistance": ("resistance", 0.6), "capacitance": ("capacitance", 0.6), "inductance": ("inductance", 0.6),
    "charge": ("charge", 0.5), "entropy": ("entropy", 0.55),
    "wavelength": ("length", 0.65), "magnetic": ("magnetic_field", 0.5), "electric": ("electric_field", 0.45),
    "concentration": ("concentration", 0.6),
}


def _match_dictionary(col: str) -> tuple[str, float] | None:
    for pattern, dim_key, conf in _PATTERNS:
        if re.search(pattern, col, re.IGNORECASE):
            return dim_key, conf
    # Fallback: token search for "descriptive_prefix_keyword" names the
    # anchored patterns above can't reach.
    tokens = re.split(r"[_\s]+|(?<=[a-z0-9])(?=[A-Z])", col)
    for tok in tokens:
        hit = _TOKEN_DIMENSION_MAP.get(tok.lower())
        if hit:
            return hit
    return None


def _detect_unit_suffix(col: str) -> str | None:
    m = _UNIT_SUFFIX_RE.search(col)
    if not m:
        return None
    token = m.group(1).lower()
    return _SUFFIX_ALIASES.get(token, token)


def resolve_units(
    columns: list[str],
    llm_resolver: Callable[[list[str]], dict[str, dict]] | None = None,
    unit_overrides: dict[str, str] | None = None,
) -> UnitsResolution:
    """Resolve every column to an SI dimension + confidence.

    `llm_resolver`, if provided, is called ONCE with the columns the
    dictionary couldn't classify and must return
    ``{col: {"dimension_key": str, "confidence": float, "unit": str|None}}``.
    Its output is not trusted blindly -- Layer 2/3 verification can still
    override it with a units_conflict finding.

    `unit_overrides`, if provided, is ``{col: dimension_key}`` -- a human
    correction (e.g. "you mapped 'v' to velocity, but it's volume"). Applied
    last, after dictionary and LLM resolution, so it always wins, at maximal
    confidence (1.0) and source="user_override". Every downstream layer
    (laws, anchors, response surface) sees the corrected mapping, not the
    original guess.
    """
    result = UnitsResolution()
    unresolved: list[str] = []

    for col in columns:
        base_name = re.sub(_UNIT_SUFFIX_RE, "", col)
        unit_suffix = _detect_unit_suffix(col)
        match = _match_dictionary(base_name) or _match_dictionary(col)

        if match is None:
            unresolved.append(col)
            result.columns[col] = ColumnUnits(
                column=col, dimension=None, confidence=0.0, source="unresolved",
                notes="no dictionary match",
            )
            continue

        dim_key, conf = match
        dimension = BASE_DIMENSIONS.get(dim_key, DIMENSIONLESS)
        scale, offset = 1.0, 0.0
        unit_label = "SI"
        if unit_suffix and unit_suffix in UNIT_CONVERSIONS:
            scale, offset = UNIT_CONVERSIONS[unit_suffix]
            unit_label = unit_suffix
            conf = min(1.0, conf + 0.05)  # explicit unit suffix raises confidence

        result.columns[col] = ColumnUnits(
            column=col, dimension=dimension, confidence=conf, source="dictionary",
            unit_label=unit_label, si_scale=scale, si_offset=offset,
        )

    if unresolved and llm_resolver is not None:
        try:
            llm_out = llm_resolver(unresolved)
        except Exception as e:
            llm_out = {}
            for col in unresolved:
                result.columns[col].notes = f"llm_resolver failed: {e}"
        for col, info in (llm_out or {}).items():
            if col not in result.columns:
                continue
            dim_key = info.get("dimension_key")
            dimension = BASE_DIMENSIONS.get(dim_key) if dim_key else None
            conf = float(info.get("confidence", 0.0))
            unit = info.get("unit")
            scale, offset = UNIT_CONVERSIONS.get(unit, (1.0, 0.0)) if unit else (1.0, 0.0)
            result.columns[col] = ColumnUnits(
                column=col, dimension=dimension, confidence=conf, source="llm",
                unit_label=unit or "SI", si_scale=scale, si_offset=offset,
            )

    if unit_overrides:
        for col, dim_key in unit_overrides.items():
            if col not in columns:
                continue
            dimension = BASE_DIMENSIONS.get(dim_key)
            if dimension is None and dim_key != "dimensionless":
                continue  # unknown dimension key -- ignore rather than silently corrupt
            result.columns[col] = ColumnUnits(
                column=col, dimension=dimension if dim_key != "dimensionless" else DIMENSIONLESS,
                confidence=1.0, source="user_override", unit_label="SI",
                si_scale=1.0, si_offset=0.0,
                notes=f"user-corrected from {result.columns[col].source if col in result.columns else 'unresolved'}",
            )

    return result
