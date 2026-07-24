"""
SI base-dimension vectors, physical constants, and unit conversions.

Dimension vectors are 7-tuples of exponents over (M, L, T, Theta, I, N, J) --
mass, length, time, temperature, current, amount, luminous intensity. This is
the shared vocabulary every layer of the dimensional engine operates on.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

DIM_NAMES = ("M", "L", "T", "Theta", "I", "N", "J")
Dim = tuple[Fraction, Fraction, Fraction, Fraction, Fraction, Fraction, Fraction]


def dim(m=0, l=0, t=0, theta=0, i=0, n=0, j=0) -> Dim:
    return (Fraction(m), Fraction(l), Fraction(t), Fraction(theta),
            Fraction(i), Fraction(n), Fraction(j))


DIMENSIONLESS: Dim = dim()


def dim_add(a: Dim, b: Dim) -> Dim:
    return tuple(x + y for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def dim_sub(a: Dim, b: Dim) -> Dim:
    return tuple(x - y for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def dim_scale(a: Dim, k) -> Dim:
    k = Fraction(k)
    return tuple(x * k for x in a)  # type: ignore[return-value]


def dim_is_zero(a: Dim) -> bool:
    return all(x == 0 for x in a)


def dim_repr(a: Dim) -> str:
    parts = []
    for name, exp in zip(DIM_NAMES, a, strict=True):
        if exp == 0:
            continue
        parts.append(name if exp == 1 else f"{name}^{exp}")
    return "·".join(parts) if parts else "1 (dimensionless)"


# Common physical-quantity base dimensions, keyed by canonical name.
BASE_DIMENSIONS: dict[str, Dim] = {
    "mass": dim(m=1),
    "length": dim(l=1),
    "time": dim(t=1),
    "temperature": dim(theta=1),
    "current": dim(i=1),
    "amount": dim(n=1),
    "luminous_intensity": dim(j=1),
    "dimensionless": DIMENSIONLESS,
    "velocity": dim(l=1, t=-1),
    "acceleration": dim(l=1, t=-2),
    "force": dim(m=1, l=1, t=-2),
    "pressure": dim(m=1, l=-1, t=-2),
    "energy": dim(m=1, l=2, t=-2),
    "power": dim(m=1, l=2, t=-3),
    "density": dim(m=1, l=-3),
    "dynamic_viscosity": dim(m=1, l=-1, t=-1),
    "kinematic_viscosity": dim(l=2, t=-1),
    "frequency": dim(t=-1),
    "angular_velocity": dim(t=-1),
    "momentum": dim(m=1, l=1, t=-1),
    "torque": dim(m=1, l=2, t=-2),
    "area": dim(l=2),
    "volume": dim(l=3),
    "surface_tension": dim(m=1, t=-2),
    "specific_heat": dim(l=2, t=-2, theta=-1),
    "thermal_conductivity": dim(m=1, l=1, t=-3, theta=-1),
    "gas_constant_specific": dim(l=2, t=-2, theta=-1),
    "gas_constant_molar": dim(m=1, l=2, t=-2, theta=-1, n=-1),
    "entropy": dim(m=1, l=2, t=-2, theta=-1),
    "heat_flux": dim(m=1, t=-3),
    "voltage": dim(m=1, l=2, t=-3, i=-1),
    "resistance": dim(m=1, l=2, t=-3, i=-2),
    "capacitance": dim(m=-1, l=-2, t=4, i=2),
    "inductance": dim(m=1, l=2, t=-2, i=-2),
    "charge": dim(t=1, i=1),
    "magnetic_field": dim(m=1, t=-2, i=-1),
    "permittivity": dim(m=-1, l=-3, t=4, i=2),
    "permeability": dim(m=1, l=1, t=-2, i=-2),
    "molar_mass": dim(m=1, n=-1),
    "stefan_boltzmann": dim(m=1, t=-3, theta=-4),
    "gravitational_constant": dim(l=3, m=-1, t=-2),
    "planck": dim(m=1, l=2, t=-1),
}


@dataclass(frozen=True)
class PhysicalConstant:
    name: str
    value: float
    dimension: Dim
    description: str = ""


# Ship tens, not five. Every constant here closes a real detection hole for
# Layer 3 (anchored constant groups) -- this list is the primary defence
# against majority corruption inverting the engine's sense of "truth".
CONSTANTS: list[PhysicalConstant] = [
    PhysicalConstant("R_air", 287.05, BASE_DIMENSIONS["gas_constant_specific"], "Specific gas constant, dry air"),
    PhysicalConstant("R_molar", 8.31446, BASE_DIMENSIONS["gas_constant_molar"], "Universal gas constant"),
    PhysicalConstant("g", 9.80665, BASE_DIMENSIONS["acceleration"], "Standard gravity"),
    PhysicalConstant("c", 2.99792458e8, BASE_DIMENSIONS["velocity"], "Speed of light"),
    PhysicalConstant("sigma_sb", 5.670374e-8, BASE_DIMENSIONS["stefan_boltzmann"], "Stefan-Boltzmann"),
    PhysicalConstant("k_B", 1.380649e-23, dim(m=1, l=2, t=-2, theta=-1), "Boltzmann constant"),
    PhysicalConstant("N_A", 6.02214076e23, dim(n=-1), "Avogadro constant"),
    PhysicalConstant("sigma_water", 0.0728, BASE_DIMENSIONS["surface_tension"], "Surface tension, water @20C"),
    PhysicalConstant("rho_water", 998.2, BASE_DIMENSIONS["density"], "Density, water @20C"),
    PhysicalConstant("mu_water", 1.002e-3, BASE_DIMENSIONS["dynamic_viscosity"], "Dynamic viscosity, water @20C"),
    PhysicalConstant("rho_air", 1.225, BASE_DIMENSIONS["density"], "Density, air @ sea level ISA"),
    PhysicalConstant("mu_air", 1.81e-5, BASE_DIMENSIONS["dynamic_viscosity"], "Dynamic viscosity, air @15C"),
    PhysicalConstant("gamma_air", 1.4, DIMENSIONLESS, "Specific heat ratio, air"),
    PhysicalConstant("c_p_air", 1005.0, BASE_DIMENSIONS["specific_heat"], "Specific heat @ const P, air"),
    PhysicalConstant("c_v_air", 718.0, BASE_DIMENSIONS["specific_heat"], "Specific heat @ const V, air"),
    PhysicalConstant("atm", 101325.0, BASE_DIMENSIONS["pressure"], "Standard atmosphere"),
    PhysicalConstant("eps0", 8.8541878128e-12, BASE_DIMENSIONS["permittivity"], "Vacuum permittivity"),
    PhysicalConstant("mu0", 1.25663706212e-6, BASE_DIMENSIONS["permeability"], "Vacuum permeability"),
    PhysicalConstant("e_charge", 1.602176634e-19, BASE_DIMENSIONS["charge"], "Elementary charge"),
    PhysicalConstant("m_e", 9.1093837015e-31, BASE_DIMENSIONS["mass"], "Electron mass"),
    PhysicalConstant("m_p", 1.67262192369e-27, BASE_DIMENSIONS["mass"], "Proton mass"),
    PhysicalConstant("G_grav", 6.67430e-11, BASE_DIMENSIONS["gravitational_constant"], "Gravitational constant"),
    PhysicalConstant("h_planck", 6.62607015e-34, BASE_DIMENSIONS["planck"], "Planck constant"),
    PhysicalConstant("R_earth", 6.371e6, BASE_DIMENSIONS["length"], "Mean radius of Earth"),
    PhysicalConstant("M_sun", 1.989e30, BASE_DIMENSIONS["mass"], "Solar mass"),
    PhysicalConstant("c_sound_air", 343.0, BASE_DIMENSIONS["velocity"], "Speed of sound, air @20C"),
    PhysicalConstant("wien_b", 2.897771955e-3, dim(l=1, theta=1), "Wien displacement constant"),
    PhysicalConstant("faraday", 96485.33212, dim(t=1, i=1, n=-1), "Faraday constant"),
    PhysicalConstant("torr", 133.322, BASE_DIMENSIONS["pressure"], "Torr / mmHg"),
    PhysicalConstant("year_s", 3.15576e7, BASE_DIMENSIONS["time"], "Julian year in seconds"),
]

CONSTANTS_BY_DIM: dict[Dim, list[PhysicalConstant]] = {}
for _c in CONSTANTS:
    CONSTANTS_BY_DIM.setdefault(_c.dimension, []).append(_c)


# Non-SI -> SI multiplicative (and where needed, affine) conversions. Value is
# (scale, offset) such that si_value = raw_value * scale + offset.
UNIT_CONVERSIONS: dict[str, tuple[float, float]] = {
    "psi": (6894.757293168, 0.0),
    "bar": (1e5, 0.0),
    "atm": (101325.0, 0.0),
    "mmhg": (133.322, 0.0),
    "torr": (133.322, 0.0),
    "kpa": (1e3, 0.0),
    "mpa": (1e6, 0.0),
    "degf": (5.0 / 9.0, 459.67 * 5.0 / 9.0),  # F -> K
    "degc": (1.0, 273.15),                     # C -> K
    "rankine": (5.0 / 9.0, 0.0),
    "ft": (0.3048, 0.0),
    "inch": (0.0254, 0.0),
    "yard": (0.9144, 0.0),
    "mile": (1609.344, 0.0),
    "nmi": (1852.0, 0.0),
    "slug_ft3": (515.379, 0.0),
    "lbm_ft3": (16.0185, 0.0),
    "lbf": (4.4482216153, 0.0),
    "lbm": (0.45359237, 0.0),
    "slug": (14.5939029, 0.0),
    "rpm": (2 * 3.14159265358979 / 60.0, 0.0),
    "deg": (3.14159265358979 / 180.0, 0.0),
    "gpm": (6.30902e-5, 0.0),  # gal/min -> m3/s
    "hp": (745.699872, 0.0),
    "btu": (1055.05585, 0.0),
    "cal": (4.184, 0.0),
    "knot": (0.514444, 0.0),
    "mph": (0.44704, 0.0),
}

# Bimodal-split factor dictionary (Layer 4): recognisable unit-convention
# ratios that explain a two-cluster split without needing an anchor.
SPLIT_FACTORS: dict[float, str] = {
    1e3: "×1e3 = kilo",
    1e6: "×1e6 = mega",
    1e-3: "×1e-3 = milli",
    1e-6: "×1e-6 = micro",
    60.0: "×60 = min/s",
    3600.0: "×3600 = hr/s",
    0.3048: "×0.3048 = ft/m",
    6894.76: "×6894.76 = psi/Pa",
    1.8: "×1.8 = °F scale",
    4.44822: "×4.44822 = lbf/N",
    0.45359237: "×0.45359237 = lb/kg",
    1852.0: "×1852 = nmi/m",
    101325.0: "×101325 = atm/Pa",
    1e5: "×1e5 = bar/Pa",
}
