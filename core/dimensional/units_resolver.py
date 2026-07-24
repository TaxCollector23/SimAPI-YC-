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
     r"^fraction$|efficiency|^eta$|utilization|porosity|void_fraction",
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
    (r"^(dynamic_)?viscosity$", "dynamic_viscosity", 0.8),
    (r"^nu$", "kinematic_viscosity", 0.55),
    (r"^mu$", "dynamic_viscosity", 0.55),
    (r"^(enthalpy|energy)(_\w+)?$", "energy", 0.75),
    (r"^power(_\w+)?$", "power", 0.8),
    (r"^heat_?flux$|^q_?wall$|^tau_?wall$", "heat_flux", 0.8),
    (r"^entropy(_\w+)?$", "entropy", 0.8),
    (r"^specific_heat$|^c_?p$|^c_?v$", "specific_heat", 0.7),
    (r"^thermal_conductivity$", "thermal_conductivity", 0.6),
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
    (r"^time(_s)?$|^t_s$", "time", 0.8),
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


def _match_dictionary(col: str) -> tuple[str, float] | None:
    for pattern, dim_key, conf in _PATTERNS:
        if re.search(pattern, col, re.IGNORECASE):
            return dim_key, conf
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
) -> UnitsResolution:
    """Resolve every column to an SI dimension + confidence.

    `llm_resolver`, if provided, is called ONCE with the columns the
    dictionary couldn't classify and must return
    ``{col: {"dimension_key": str, "confidence": float, "unit": str|None}}``.
    Its output is not trusted blindly -- Layer 2/3 verification can still
    override it with a units_conflict finding.
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

    return result
