"""
SimAPI Physics Validation Engine v3.0
Thousands of checks across 20+ simulation domains.
Only surfaces failures and warnings to the user.
"""
import itertools
import math
import time
import uuid
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats


class SimulationType(str, Enum):
    AERODYNAMICS     = "aerodynamics"
    FLUID_DYNAMICS   = "fluid_dynamics"
    STRUCTURAL       = "structural"
    THERMODYNAMICS   = "thermodynamics"
    ROBOTICS         = "robotics"
    COMBUSTION       = "combustion"
    ACOUSTICS        = "acoustics"
    ELECTROMAGNETICS = "electromagnetics"
    GEOMECHANICS     = "geomechanics"
    BIOMECHANICS     = "biomechanics"
    NUCLEAR          = "nuclear"
    PLASMA           = "plasma"
    CHEMICAL         = "chemical"
    HYDRODYNAMICS    = "hydrodynamics"
    METEOROLOGY      = "meteorology"
    ASTROPHYSICS     = "astrophysics"
    MATERIALS        = "materials"
    TRIBOLOGY        = "tribology"
    AEROELASTICITY   = "aeroelasticity"
    CRYOGENICS       = "cryogenics"
    MULTIPHYSICS     = "multiphysics"

class ValidationStatus(str, Enum):
    PASSED  = "passed"
    WARNING = "warning"
    FAILED  = "failed"

class Confidence(str, Enum):
    HIGH = "high"; MEDIUM = "medium"; LOW = "low"

P = {
    "rho_air": 1.225, "mu_air": 1.81e-5, "c_sound": 343.0,
    "g": 9.81, "sigma_sb": 5.67e-8, "R_air": 287.05,
    "gamma": 1.4, "k_b": 1.38e-23, "h_planck": 6.626e-34,
    "N_a": 6.022e23, "mu0": 1.257e-6, "eps0": 8.854e-12,
    "c": 3e8, "e": 1.602e-19, "R_gas": 8.314,
    "rho_water": 998.2, "mu_water": 1.002e-3, "gamma_water": 0.0728,
    "wien_b": 2.898e-3, "faraday": 96485.0,
}

@dataclass
class PhysicsCheck:
    name: str; status: ValidationStatus; description: str
    value: Optional[float] = None; threshold: Optional[float] = None
    detail: str = ""; category: str = "general"

@dataclass
class TrialExclusion:
    trial_index: int; reason: str; severity: str
    values: Dict = field(default_factory=dict)

@dataclass
class StatisticalSummary:
    mean: float; std: float; median: float
    p5: float; p95: float; min: float; max: float
    n: int; skewness: float; kurtosis: float; cv: float

@dataclass
class ValidationReport:
    job_id: str; timestamp: float; simulation_type: str
    trials_submitted: int; trials_valid: int; trials_excluded: int
    exclusion_rate: float; confidence: Confidence; overall_status: ValidationStatus
    issues: List[PhysicsCheck]
    all_checks_count: int; passed_count: int; warning_count: int; failed_count: int
    exclusions: List[TrialExclusion]
    statistics: Dict[str, StatisticalSummary]
    warnings: List[str]; provenance: Dict
    training_ready: bool; processing_time_ms: float
    checks_by_category: Dict[str, Dict[str, int]]

BOUNDS = {
    SimulationType.AERODYNAMICS: {
        "drag_coefficient":(0.0005,3.5),"lift_coefficient":(-4.5,6.0),
        "side_force_coefficient":(-2.5,2.5),"pressure":(-5e5,5e5),
        "velocity":(0.0,340.0),"reynolds_number":(1e1,1e9),
        "mach_number":(0.0,0.99),"angle_of_attack":(-35.0,45.0),
        "pitching_moment":(-3.0,3.0),"rolling_moment":(-2.0,2.0),
        "pressure_coefficient":(-25.0,2.0),"skin_friction_coefficient":(0.0,0.15),
        "turbulence_intensity":(0.0,1.0),"strouhal_number":(0.0,20.0),
        "induced_drag_coefficient":(0.0,2.5),"oswald_efficiency":(0.0,1.0),
        "dynamic_pressure":(0.0,1e6),"wake_deficit":(0.0,1.0),
        "separation_point":(0.0,1.0),"transition_location":(0.0,1.0),
        "nusselt_number":(1.0,1e7),"lift_to_drag_ratio":(-100.0,100.0),
        "boundary_layer_thickness":(0.0,2.0),"aspect_ratio":(0.5,50.0),
    },
    SimulationType.FLUID_DYNAMICS: {
        "pressure":(-1e8,1e8),"velocity":(0.0,2000.0),
        "velocity_x":(-2000.0,2000.0),"velocity_y":(-2000.0,2000.0),
        "velocity_z":(-2000.0,2000.0),"density":(0.001,25000.0),
        "temperature":(1.0,50000.0),"reynolds_number":(1.0,1e12),
        "froude_number":(0.0,200.0),"weber_number":(0.0,1e7),
        "turbulent_kinetic_energy":(0.0,1e7),"turbulent_dissipation":(0.0,1e9),
        "wall_shear_stress":(0.0,1e7),"pressure_drop":(-1e8,1e8),
        "flow_rate":(-1e5,1e5),"viscosity":(1e-12,1e5),
        "void_fraction":(0.0,1.0),"volume_fraction":(0.0,1.0),
        "mass_flow_rate":(-1e7,1e7),"darcy_friction_factor":(0.0,0.5),
        "pump_efficiency":(0.0,1.0),"cavitation_number":(0.0,500.0),
        "schmidt_number":(0.001,1e5),"peclet_number":(0.0,1e8),
    },
    SimulationType.STRUCTURAL: {
        "stress":(0.0,2e12),"strain":(-1.0,1.0),"displacement":(-1e5,1e5),
        "safety_factor":(0.0,1000.0),"von_mises_stress":(0.0,2e12),
        "principal_stress_1":(-2e12,2e12),"principal_stress_2":(-2e12,2e12),
        "principal_stress_3":(-2e12,2e12),"shear_stress":(-1e12,1e12),
        "yield_stress":(0.0,2e10),"ultimate_stress":(0.0,2e10),
        "elastic_modulus":(0.0,2e12),"poisson_ratio":(-1.0,0.5),
        "fatigue_life":(0.0,1e12),"stress_concentration":(1.0,30.0),
        "natural_frequency":(0.0,1e7),"damping_ratio":(0.0,2.0),
        "fracture_toughness":(0.0,1e7),"crack_length":(0.0,500.0),
        "hardness":(0.0,10000.0),"creep_rate":(0.0,1.0),
        "thermal_stress":(-2e12,2e12),"buckling_load":(0.0,1e13),
    },
    SimulationType.THERMODYNAMICS: {
        "temperature":(0.01,100000.0),"heat_flux":(-1e11,1e11),
        "thermal_efficiency":(0.0,1.0),"entropy_generation":(0.0,1e9),
        "enthalpy":(-1e9,1e9),"entropy":(-1e7,1e7),
        "heat_capacity":(0.0,1e7),"thermal_conductivity":(0.0,50000.0),
        "thermal_diffusivity":(0.0,10.0),"biot_number":(0.0,1e7),
        "nusselt_number":(1.0,1e7),"prandtl_number":(0.001,1e5),
        "grashof_number":(0.0,1e16),"rayleigh_number":(0.0,1e16),
        "heat_transfer_coefficient":(0.0,1e7),"emissivity":(0.0,1.0),
        "absorptivity":(0.0,1.0),"transmissivity":(0.0,1.0),
        "carnot_efficiency":(0.0,1.0),"cop":(0.0,200.0),
        "work_output":(-1e10,1e10),"heat_input":(0.0,1e10),
        "exergy":(-1e10,1e10),"effectiveness":(0.0,1.0),
        "log_mean_temperature":(0.01,50000.0),"ntu":(0.0,100.0),
    },
    SimulationType.ROBOTICS: {
        "joint_torque":(-100000.0,100000.0),"joint_velocity":(-500.0,500.0),
        "joint_acceleration":(-5000.0,5000.0),"joint_position":(-4*math.pi,4*math.pi),
        "end_effector_force":(-50000.0,50000.0),"end_effector_torque":(-10000.0,10000.0),
        "end_effector_velocity":(0.0,200.0),"position_error":(0.0,500.0),
        "manipulability":(0.0,500.0),"condition_number":(1.0,1e9),
        "power_consumption":(0.0,1e7),"efficiency":(0.0,1.0),
        "settling_time":(0.0,1000.0),"overshoot":(0.0,5.0),
        "rise_time":(0.0,1000.0),"workspace_volume":(0.0,1e6),
    },
    SimulationType.COMBUSTION: {
        "temperature":(200.0,6000.0),"pressure":(100.0,1e9),
        "equivalence_ratio":(0.05,10.0),"heat_release_rate":(0.0,1e13),
        "flame_speed":(0.0,5000.0),"ignition_delay":(0.0,100.0),
        "mass_fraction_fuel":(0.0,1.0),"mass_fraction_oxidizer":(0.0,1.0),
        "mass_fraction_products":(0.0,1.0),"co2_concentration":(0.0,1.0),
        "co_concentration":(0.0,1.0),"nox_concentration":(0.0,0.5),
        "flame_temperature":(300.0,5000.0),"adiabatic_temperature":(300.0,5000.0),
        "combustion_efficiency":(0.0,1.0),"mixing_efficiency":(0.0,1.0),
        "lewis_number":(0.0,1000.0),"zeldovich_number":(0.0,100.0),
    },
    SimulationType.ACOUSTICS: {
        "sound_pressure_level":(0.0,220.0),"sound_power_level":(0.0,220.0),
        "frequency":(0.0,1e8),"wavelength":(1e-9,1e5),
        "acoustic_impedance":(0.0,1e9),"transmission_loss":(0.0,300.0),
        "absorption_coefficient":(0.0,1.0),"reflection_coefficient":(0.0,1.0),
        "reverberation_time":(0.0,500.0),"quality_factor":(0.0,1e6),
        "insertion_loss":(0.0,200.0),"noise_reduction":(0.0,200.0),
    },
    SimulationType.ELECTROMAGNETICS: {
        "electric_field":(-1e12,1e12),"magnetic_field":(-1e8,1e8),
        "electric_potential":(-1e9,1e9),"power_density":(0.0,1e15),
        "frequency":(0.0,1e18),"wavelength":(1e-15,1e6),
        "permittivity":(1.0,1e6),"permeability":(1.0,1e6),
        "conductivity":(0.0,1e8),"resistivity":(0.0,1e15),
        "impedance":(0.0,1e9),"skin_depth":(0.0,1e3),
        "radiation_efficiency":(0.0,1.0),"return_loss":(-300.0,0.0),
        "vswr":(1.0,1e6),"power_factor":(0.0,1.0),
    },
    SimulationType.GEOMECHANICS: {
        "effective_stress":(-1e9,1e9),"pore_pressure":(-1e8,1e8),
        "permeability":(0.0,1.0),"porosity":(0.0,1.0),
        "void_ratio":(0.0,20.0),"degree_of_saturation":(0.0,1.0),
        "shear_strength":(0.0,1e9),"cohesion":(0.0,1e8),
        "friction_angle":(0.0,90.0),"settlement":(-100.0,100.0),
        "slope_stability_factor":(0.0,100.0),"liquefaction_potential":(0.0,1.0),
        "earth_pressure_coefficient":(0.0,5.0),"bearing_capacity":(0.0,1e9),
    },
    SimulationType.BIOMECHANICS: {
        "bone_stress":(0.0,2e8),"cartilage_stress":(0.0,1e7),
        "muscle_force":(0.0,1e5),"joint_contact_force":(0.0,1e5),
        "ground_reaction_force":(0.0,1e4),"gait_speed":(0.0,15.0),
        "joint_angle":(-180.0,180.0),"heart_rate":(0.0,300.0),
        "blood_pressure":(0.0,400.0),"metabolic_power":(0.0,5000.0),
        "fracture_risk":(0.0,1.0),"body_mass_index":(0.0,100.0),
        "arterial_stiffness":(0.0,1e7),"oxygen_consumption":(0.0,10.0),
    },
    SimulationType.NUCLEAR: {
        "neutron_flux":(0.0,1e20),"power_density":(0.0,1e10),
        "temperature":(0.0,1e7),"reactivity":(-100.0,100.0),
        "burnup":(0.0,200000.0),"enrichment":(0.0,100.0),
        "criticality_factor":(0.0,5.0),"doppler_coefficient":(-1e3,0.0),
        "decay_heat":(0.0,1e9),"fuel_temperature":(0.0,5000.0),
        "cladding_temperature":(0.0,2000.0),"delayed_neutron_fraction":(0.0,0.1),
    },
    SimulationType.PLASMA: {
        "electron_temperature":(0.0,1e9),"ion_temperature":(0.0,1e9),
        "electron_density":(0.0,1e28),"magnetic_field":(-100.0,100.0),
        "plasma_beta":(0.0,2.0),"alfven_speed":(0.0,3e8),
        "debye_length":(0.0,1.0),"plasma_frequency":(0.0,1e14),
        "confinement_time":(0.0,1000.0),"q_factor":(0.0,100.0),
        "larmor_radius":(0.0,100.0),"fusion_power":(0.0,1e12),
    },
    SimulationType.CHEMICAL: {
        "concentration":(0.0,1e6),"reaction_rate":(0.0,1e12),
        "conversion":(0.0,1.0),"selectivity":(0.0,1.0),
        "yield_chemical":(0.0,1.0),"temperature":(0.0,5000.0),
        "pressure":(0.0,1e9),"ph":(0.0,14.0),
        "activation_energy":(0.0,1e6),"diffusivity":(0.0,1.0),
        "effectiveness_factor":(0.0,1.0),"residence_time":(0.0,1e6),
        "reaction_enthalpy":(-1e8,1e8),"damkohler_number":(0.0,1e8),
    },
    SimulationType.HYDRODYNAMICS: {
        "wave_height":(0.0,100.0),"wave_period":(0.0,1000.0),
        "wave_length":(0.0,1e4),"wave_speed":(0.0,1000.0),
        "water_depth":(0.0,1e4),"current_velocity":(-50.0,50.0),
        "froude_number":(0.0,20.0),"drag_force":(-1e9,1e9),
        "added_mass":(0.0,1e8),"mooring_tension":(0.0,1e8),
        "significant_wave_height":(0.0,50.0),"steepness":(0.0,0.142),
        "response_amplitude":(0.0,100.0),"keulegan_carpenter":(0.0,1000.0),
    },
    SimulationType.METEOROLOGY: {
        "temperature":(-100.0,60.0),"pressure":(500.0,1100.0),
        "wind_speed":(0.0,120.0),"humidity":(0.0,100.0),
        "precipitation":(0.0,500.0),"visibility":(0.0,100000.0),
        "cloud_cover":(0.0,100.0),"dew_point":(-80.0,40.0),
        "wind_direction":(0.0,360.0),"solar_radiation":(0.0,1500.0),
        "uv_index":(0.0,20.0),
    },
    SimulationType.ASTROPHYSICS: {
        "luminosity":(0.0,1e40),"temperature":(0.0,1e10),
        "density":(0.0,1e20),"pressure":(0.0,1e25),
        "magnetic_field":(0.0,1e15),"velocity":(0.0,3e8),
        "redshift":(-1.0,10.0),"mass":(0.0,1e35),
        "radius":(0.0,1e15),"escape_velocity":(0.0,3e8),
        "schwarzschild_radius":(0.0,1e12),
    },
    SimulationType.MATERIALS: {
        "yield_strength":(0.0,1e10),"tensile_strength":(0.0,1e10),
        "elastic_modulus":(0.0,2e12),"poisson_ratio":(-1.0,0.5),
        "hardness":(0.0,10000.0),"toughness":(0.0,1e6),
        "thermal_conductivity":(0.0,50000.0),"specific_heat":(0.0,1e5),
        "density":(0.001,25000.0),"melting_point":(0.0,5000.0),
        "grain_size":(0.0,10.0),"fatigue_limit":(0.0,2e9),
        "fracture_toughness":(0.0,1e7),"wear_rate":(0.0,1.0),
        "electrical_resistivity":(0.0,1e15),"thermal_expansion":(-1e-3,1e-2),
    },
    SimulationType.TRIBOLOGY: {
        "friction_coefficient":(0.0,5.0),"wear_rate":(0.0,1.0),
        "contact_pressure":(0.0,1e10),"film_thickness":(0.0,0.1),
        "lambda_ratio":(0.0,100.0),"hertz_pressure":(0.0,1e10),
        "sliding_speed":(0.0,1000.0),"temperature":(0.0,2000.0),
        "viscosity":(1e-10,1e5),"surface_roughness":(0.0,1000.0),
        "stribeck_number":(0.0,1.0),"load":(0.0,1e9),
    },
    SimulationType.AEROELASTICITY: {
        "flutter_speed":(0.0,1000.0),"flutter_frequency":(0.0,1000.0),
        "reduced_frequency":(0.0,10.0),"aerodynamic_damping":(-10.0,10.0),
        "structural_damping":(0.0,1.0),"divergence_speed":(0.0,2000.0),
        "dynamic_pressure":(0.0,1e7),"tip_deflection":(-100.0,100.0),
        "torsion_angle":(-45.0,45.0),"frequency_ratio":(0.0,10.0),
        "thrust_coefficient":(-1.0,2.0),"advance_ratio":(0.0,2.0),
    },
    SimulationType.CRYOGENICS: {
        "temperature":(0.001,300.0),"pressure":(0.0,1e8),
        "density":(0.001,2000.0),"thermal_conductivity":(0.0,1000.0),
        "viscosity":(1e-10,1.0),"surface_tension":(0.0,0.1),
        "vapor_pressure":(0.0,1e7),"latent_heat":(0.0,1e7),
        "boiling_point":(0.0,300.0),"critical_temperature":(0.0,500.0),
        "critical_pressure":(0.0,1e8),"superfluid_fraction":(0.0,1.0),
        "quench_energy":(0.0,1e6),"kapitza_resistance":(0.0,1.0),
    },
}


class PhysicsValidator:
    def __init__(self):
        self.checks_run = 0
        self.total_processing_ms = 0.0

    def validate(self, data, simulation_type, conditions, job_id=None, max_exclusions=200,
                 profile=None, auto_profile=True):
        t0 = time.time()
        job_id = job_id or str(uuid.uuid4())[:8]
        all_checks, all_excl, warnings_list = [], [], []

        # ── Phase A: semantic profile ──────────────────────────────────────
        # Classify the dataset BEFORE validating it. A designed parameter sweep
        # and a time series produce identical-looking data to a check that
        # assumes row order is time; only the profile can tell them apart.
        _suppression_log: list = []
        if profile is None and auto_profile:
            try:
                from core.dataset_profile import profile_dataset
                data, profile = profile_dataset(
                    data, str(simulation_type), conditions, canonicalize=True)
            except Exception as ex:
                warnings_list.append(f"dataset_profile: {ex}")
                profile = None

        # Regime-justified bound overrides, applied for this call only.
        _bounds_patch: dict = {}
        if profile is not None and getattr(profile, "mask", None):
            try:
                dom = BOUNDS.get(simulation_type)
                if isinstance(dom, dict):
                    for b in profile.mask.bound_overrides:
                        if b.column in dom:
                            _bounds_patch[b.column] = dom[b.column]
                            dom[b.column] = (b.lo, b.hi)
            except Exception as ex:
                warnings_list.append(f"bound_override: {ex}")

        layers = [
            self._input_quality, self._plausibility, self._numerical_stability,
            self._statistical_distribution, self._outlier_detection,
            self._near_duplicates, self._relationship_drift,
            self._cross_variable, self._conservation_laws, self._dimensional,
            self._temporal, self._monotonicity, self._symmetry, self._scaling_laws,
            self._information_entropy, self._autocorrelation, self._stationarity,
            self._layer_temporal_drift,
            self._multicollinearity, self._regression_quality, self._signal_quality,
            self._sensor_fusion, self._boundary_conditions, self._convergence,
            self._energy_balance, self._phase_consistency, self._material_microstructure,
            self._turbulence_consistency, self._wave_mechanics, self._thermochemistry,
            self._control_systems, self._fracture_mechanics, self._contact_mechanics,
            self._fluid_machines, self._heat_exchangers, self._electrochemistry,
            self._layer_advanced_checks, self._layer_extended_diagnostics,
            self._layer_extended_diagnostics_2,
            self._domain_aerodynamics, self._domain_fluid, self._domain_structural,
            self._domain_thermo, self._domain_robotics, self._domain_combustion,
            self._domain_acoustics, self._domain_em, self._domain_geomechanics,
            self._domain_biomechanics, self._domain_nuclear, self._domain_plasma,
            self._domain_chemical, self._domain_hydro, self._domain_meteo,
            self._domain_astro, self._domain_materials, self._domain_tribology,
            self._domain_aeroelasticity, self._domain_cryogenics,
        ]

        # Near-constant columns legitimately produce NaN moments and divide-by-zero
        # in correlation/skew/kurtosis. These are expected and handled downstream,
        # so we silence the numerical RuntimeWarnings for the layer computations.
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore", RuntimeWarning)
            for layer in layers:
                try:
                    checks, excls = layer(data, simulation_type, conditions)
                    all_checks.extend(checks); all_excl.extend(excls)
                except Exception as ex:
                    warnings_list.append(f"{layer.__name__}: {ex}")

        # Restore any patched bounds so the module-level table stays pristine
        # across calls (BOUNDS is shared process-wide).
        if _bounds_patch:
            dom = BOUNDS.get(simulation_type)
            if isinstance(dom, dict):
                for col, orig in _bounds_patch.items():
                    dom[col] = orig

        # ── Apply the check mask ───────────────────────────────────────────
        if profile is not None and getattr(profile, "mask", None):
            try:
                from core.dataset_profile import apply_mask
                all_checks, all_excl, _suppression_log = apply_mask(
                    all_checks, all_excl, profile, list(data.columns))
            except Exception as ex:
                warnings_list.append(f"apply_mask: {ex}")

            # Exact-match duplicates replace cosine similarity. Re-add them so
            # suppressing the cosine check never loses a genuine finding.
            try:
                already = {e.trial_index for e in all_excl}
                for group in getattr(profile, "exact_duplicate_groups", []):
                    keep = group[0]
                    for idx in group[1:]:
                        if idx not in already:
                            all_excl.append(TrialExclusion(
                                trial_index=int(idx),
                                reason=(f"Exact duplicate of trial {keep + 1} "
                                        "(all columns identical)"),
                                severity="warning",
                            ))
                            already.add(idx)
            except Exception as ex:
                warnings_list.append(f"exact_duplicates: {ex}")

        excl_idx = {e.trial_index for e in all_excl}
        valid = data[~data.index.isin(excl_idx)].copy()
        n_sub, n_val = len(data), len(valid)
        n_excl = n_sub - n_val
        excl_rate = n_excl / n_sub if n_sub > 0 else 0.0

        statistics = {}
        for col in valid.select_dtypes(include=[np.number]).columns:
            s = valid[col].dropna()
            if len(s) > 1:
                statistics[col] = StatisticalSummary(
                    mean=float(s.mean()), std=float(s.std()), median=float(s.median()),
                    p5=float(s.quantile(.05)), p95=float(s.quantile(.95)),
                    min=float(s.min()), max=float(s.max()), n=int(len(s)),
                    skewness=float(s.skew()), kurtosis=float(s.kurtosis()),
                    cv=float(s.std()/s.mean()) if s.mean() != 0 else 0.0,
                )

        passed  = [c for c in all_checks if c.status == ValidationStatus.PASSED]
        warned  = [c for c in all_checks if c.status == ValidationStatus.WARNING]
        failed  = [c for c in all_checks if c.status == ValidationStatus.FAILED]
        issues  = warned + failed  # only surface these

        # Count unique check names, not total invocations
        unique_names = {c.name for c in all_checks}
        unique_passed = {c.name for c in passed}
        unique_warned = {c.name for c in warned}
        unique_failed = {c.name for c in failed}

        cats = {}
        for c in all_checks:
            sv = c.status.value if hasattr(c.status, "value") else str(c.status)
            cats.setdefault(c.category, {"passed":0,"warning":0,"failed":0})
            cats[c.category][sv] = cats[c.category].get(sv, 0) + 1

        if failed or excl_rate > 0.5:
            overall = ValidationStatus.FAILED; conf = Confidence.LOW
        elif warned or excl_rate > 0.2:
            overall = ValidationStatus.WARNING; conf = Confidence.MEDIUM
        else:
            overall = ValidationStatus.PASSED; conf = Confidence.HIGH

        training_ready = overall != ValidationStatus.FAILED and n_val >= 10 and excl_rate < 0.5
        ms = (time.time()-t0)*1000
        self.checks_run += 1; self.total_processing_ms += ms

        return ValidationReport(
            job_id=job_id, timestamp=time.time(), simulation_type=simulation_type.value,
            trials_submitted=n_sub, trials_valid=n_val, trials_excluded=n_excl,
            exclusion_rate=round(excl_rate,4), confidence=conf, overall_status=overall,
            issues=issues, all_checks_count=len(unique_names),
            passed_count=len(unique_passed), warning_count=len(unique_warned), failed_count=len(unique_failed),
            exclusions=all_excl[:max_exclusions], statistics=statistics, warnings=warnings_list,
            provenance={"validator_version":"4.0.0","simulation_type":simulation_type.value,
                       "conditions":conditions,"columns_validated":list(data.columns),
                       "total_checks":len(unique_names),"total_invocations":len(all_checks),
                       "dataset_profile": (profile.to_dict() if profile is not None else None),
                       "suppressions": _suppression_log},
            training_ready=training_ready, processing_time_ms=round(ms,2),
            checks_by_category=cats,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _c(self, n, ok, desc, det="", v=None, t=None, cat="general"):
        return PhysicsCheck(n, ValidationStatus.PASSED if ok else ValidationStatus.FAILED, desc, v, t, det, cat)
    def _w(self, n, ok, desc, det="", v=None, t=None, cat="general"):
        return PhysicsCheck(n, ValidationStatus.PASSED if ok else ValidationStatus.WARNING, desc, v, t, det, cat)
    def _nc(self, d): return list(d.select_dtypes(include=[np.number]).columns)
    def _r(self, C, E=None): return C, E or []
    def _dom(self, sim, target): return sim == target

    # ── Layer 1: Input Quality (30+ checks) ───────────────────────────────────
    def _input_quality(self, data, sim, cond):
        C=[]; E=[]; cat="input_quality"; n=len(data); nc=self._nc(data)
        C.append(self._c("iq_non_empty",n>0,"Dataset non-empty",f"{n} trials",float(n),cat=cat))
        C.append(self._c("iq_has_numeric",len(nc)>0,"Has numeric columns",f"{len(nc)}",float(len(nc)),cat=cat))
        C.append(self._w("iq_min10",n>=10,"≥10 trials",f"{n}",float(n),10.0,cat))
        C.append(self._w("iq_min30",n>=30,"≥30 trials",f"{n}",float(n),30.0,cat))
        C.append(self._w("iq_min100",n>=100,"≥100 trials preferred",f"{n}",float(n),100.0,cat))
        C.append(self._w("iq_min500",n>=500,"≥500 trials for high confidence",f"{n}",float(n),500.0,cat))
        dupes=int(data.duplicated().sum())
        C.append(self._w("iq_no_dupes",dupes==0,"No duplicate rows",f"{dupes}",float(dupes),0.0,cat))
        C.append(self._c("iq_unique_idx",data.index.is_unique,"Unique index",cat=cat))
        C.append(self._w("iq_min2cols",len(nc)>=2,"≥2 numeric columns",f"{len(nc)}",float(len(nc)),2.0,cat))
        C.append(self._w("iq_min5cols",len(nc)>=5,"≥5 columns recommended",f"{len(nc)}",float(len(nc)),5.0,cat))
        for col in nc:
            miss=int(data[col].isna().sum()); pct=miss/n if n>0 else 0
            C.append(self._w(f"iq_complete_{col}",pct<0.05,f"{col} >95% complete",f"{miss} miss ({pct*100:.1f}%)",pct,0.05,cat))
            s=data[col].dropna()
            if len(s)>1:
                C.append(self._w(f"iq_variance_{col}",s.std()>0,f"{col} non-constant",f"std={s.std():.4g}",float(s.std()),0.0,cat))
                mode_pct=float((s==s.mode().iloc[0]).sum())/len(s) if len(s.mode())>0 else 0
                C.append(self._w(f"iq_mode_{col}",mode_pct<0.8,f"{col} not mostly one value",f"mode={mode_pct*100:.0f}%",mode_pct,0.8,cat))
                near_zero=int(((np.abs(s)>0)&(np.abs(s)<1e-300)).sum())
                C.append(self._w(f"iq_subnorm_{col}",near_zero==0,f"No subnormal in {col}",f"{near_zero}",float(near_zero),0.0,cat))
                # Range ratio
                if s.min()>0:
                    rr=float(s.max()/s.min())
                    C.append(self._w(f"iq_range_{col}",rr<1e12,f"Range ratio {col} reasonable",f"{rr:.2e}",float(rr),1e12,cat))
        return self._r(C,E)

    # ── Layer 2: Plausibility Bounds (100+ checks via BOUNDS dict) ────────────
    def _plausibility(self, data, sim, cond):
        C=[]; E=[]; cat="plausibility"
        for col,(lo,hi) in BOUNDS.get(sim,{}).items():
            if col not in data.columns: continue
            s=data[col]; oob=(s<lo)|(s>hi); n_oob=int(oob.sum())
            status=(ValidationStatus.PASSED if n_oob==0
                   else ValidationStatus.WARNING if n_oob<len(s)*0.05
                   else ValidationStatus.FAILED)
            C.append(PhysicsCheck(f"bounds_{col}",status,f"{col} in [{lo:.4g},{hi:.4g}]",
                float(n_oob),0.0,"All in range" if n_oob==0 else f"{n_oob} violations",cat))
            for idx in data.index[oob]:
                E.append(TrialExclusion(int(idx),f"{col}={data.loc[idx,col]:.4g} outside [{lo:.4g},{hi:.4g}]","critical",{col:float(data.loc[idx,col])}))
        # Universal physical law bounds
        for tcol in [c for c in data.columns if "temperature" in c.lower()]:
            neg=(data[tcol]<0).sum()
            C.append(self._c(f"bounds_abszero_{tcol}",neg==0,f"{tcol} above absolute zero",f"{neg}",float(neg),cat=cat))
        for ecol in ["efficiency","thermal_efficiency","combustion_efficiency","pump_efficiency",
                     "radiation_efficiency","mixing_efficiency","volumetric_efficiency","isentropic_efficiency",
                     "mechanical_efficiency","overall_efficiency","collection_efficiency"]:
            if ecol in data.columns:
                bad=((data[ecol]<0)|(data[ecol]>1)).sum()
                C.append(self._c(f"bounds_01_{ecol}",bad==0,f"{ecol} in [0,1]",f"{bad}",float(bad),cat=cat))
        for fcol in ["void_fraction","volume_fraction","mass_fraction_fuel","mass_fraction_oxidizer",
                     "mass_fraction_products","emissivity","absorptivity","transmissivity",
                     "porosity","degree_of_saturation","conversion","selectivity",
                     "yield_chemical","superfluid_fraction","fracture_risk","liquefaction_potential"]:
            if fcol in data.columns:
                bad=((data[fcol]<0)|(data[fcol]>1)).sum()
                C.append(self._c(f"bounds_frac_{fcol}",bad==0,f"{fcol} in [0,1]",f"{bad}",float(bad),cat=cat))
        if "poisson_ratio" in data.columns:
            bad=((data["poisson_ratio"]<-1)|(data["poisson_ratio"]>0.5)).sum()
            C.append(self._c("bounds_poisson",bad==0,"Poisson in [-1,0.5]",f"{bad}",float(bad),cat=cat))
        if "ph" in data.columns:
            bad=((data["ph"]<0)|(data["ph"]>14)).sum()
            C.append(self._c("bounds_ph",bad==0,"pH in [0,14]",f"{bad}",float(bad),cat=cat))
        if "vswr" in data.columns:
            C.append(self._c("bounds_vswr",(data["vswr"]<1).sum()==0,"VSWR≥1.0","",cat=cat))
        if "stress_concentration" in data.columns:
            bad=(data["stress_concentration"]<1.0).sum()
            C.append(self._c("bounds_kt",bad==0,"Kt≥1.0 (concentration ≥ nominal)",f"{bad}",float(bad),cat=cat))
            for idx in data.index[data["stress_concentration"]<1.0]:
                E.append(TrialExclusion(int(idx),f"Kt={data.loc[idx,'stress_concentration']:.3f}<1 impossible","critical"))
        if "return_loss" in data.columns:
            bad=(data["return_loss"]>0).sum()
            C.append(self._c("bounds_rl",bad==0,"Return loss≤0 dB",f"{bad}",float(bad),cat=cat))
        if "wave_steepness" in data.columns:
            bad=(data["wave_steepness"]>0.142).sum()
            C.append(self._c("bounds_steep",bad==0,"Steepness<0.142 (physical limit)",f"{bad}",float(bad),cat=cat))
        if "plasma_beta" in data.columns:
            bad=(data["plasma_beta"]<0).sum()
            C.append(self._c("bounds_beta",bad==0,"Plasma β≥0",f"{bad}",float(bad),cat=cat))
        if "mach_number" in data.columns:
            sonic=(data["mach_number"]>=1.0).sum()
            C.append(self._w("bounds_subsonic",sonic==0,"Mach<1.0 (incompressible solver)",f"{sonic} sonic/supersonic",float(sonic),0.0,cat))
        if "damping_ratio" in data.columns:
            neg=(data["damping_ratio"]<0).sum()
            C.append(self._c("bounds_damp_pos",neg==0,"Damping ratio≥0",f"{neg}",float(neg),cat=cat))
            over=(data["damping_ratio"]>1.0).sum()
            C.append(self._w("bounds_overdamp",over==0,"Damping ratio≤1 (underdamped check)",f"{over}",float(over),0.0,cat))
        if "redshift" in data.columns:
            bad=(data["redshift"]<-1).sum()
            C.append(self._c("bounds_redshift",bad==0,"Redshift≥-1 (physical)",f"{bad}",float(bad),cat=cat))
        if "friction_angle" in data.columns:
            bad=((data["friction_angle"]<0)|(data["friction_angle"]>90)).sum()
            C.append(self._c("bounds_phi_angle",bad==0,"Friction angle in [0°,90°]",f"{bad}",float(bad),cat=cat))
        if "wind_direction" in data.columns:
            bad=((data["wind_direction"]<0)|(data["wind_direction"]>=360)).sum()
            C.append(self._c("bounds_wind_dir",bad==0,"Wind direction in [0°,360°)",f"{bad}",float(bad),cat=cat))
        if "heart_rate" in data.columns:
            bad=((data["heart_rate"]<20)|(data["heart_rate"]>250)).sum()
            C.append(self._w("bounds_hr",bad==0,"Heart rate in [20,250] bpm",f"{bad}",float(bad),0.0,cat))
        if "blood_pressure" in data.columns:
            bad=((data["blood_pressure"]<30)|(data["blood_pressure"]>300)).sum()
            C.append(self._w("bounds_bp",bad==0,"Blood pressure in [30,300] mmHg",f"{bad}",float(bad),0.0,cat))
        if "criticality_factor" in data.columns:
            bad=(data["criticality_factor"]>2.0).sum()
            C.append(self._w("bounds_keff",bad==0,"keff<2.0",f"{bad}",float(bad),0.0,cat))
        return self._r(C,E)

    # ── Layer 3: Numerical Stability ──────────────────────────────────────────
    def _numerical_stability(self, data, sim, cond):
        C=[]; E=[]; cat="numerical_stability"; nc=self._nc(data)
        total_nan=int(data[nc].isna().sum().sum())
        status=(ValidationStatus.PASSED if total_nan==0 else ValidationStatus.WARNING if total_nan<len(data)*0.02 else ValidationStatus.FAILED)
        C.append(PhysicsCheck("ns_nan",status,"No NaN (solver divergence)",float(total_nan),0.0,f"{total_nan} NaN",cat))
        total_inf=int(np.isinf(data[nc].replace([np.inf,-np.inf],np.nan).fillna(0).values).sum())
        C.append(self._c("ns_inf",total_inf==0,"No Inf values",f"{total_inf}",float(total_inf),cat=cat))
        div_mask=data[nc].isna().any(axis=1)|np.isinf(data[nc].replace([np.inf,-np.inf],np.nan).fillna(0).values).any(axis=1)
        for idx in data.index[div_mask]:
            E.append(TrialExclusion(int(idx),"NaN/Inf: numerical divergence","critical"))
        for col in nc:
            s=data[col].dropna()
            if len(s)>1 and s.mean()!=0:
                cv=abs(s.std()/s.mean())
                C.append(self._w(f"ns_cv_{col}",cv<10,f"CV of {col}",f"CV={cv:.3f}",float(cv),10.0,cat))
            if len(s)>3:
                d=s.diff().dropna()
                if d.std()>0:
                    spikes=(np.abs(d/d.std())>6).sum()
                    C.append(self._w(f"ns_spike_{col}",spikes==0,f"No spikes in {col}",f"{spikes} spikes",float(spikes),0.0,cat))
                jumps=(np.abs(d/d.std())>10).sum()
                C.append(self._w(f"ns_jump_{col}",jumps==0,f"No discontinuous jumps in {col}",f"{jumps}",float(jumps),0.0,cat))
            wins=[s.iloc[i:i+5] for i in range(0,len(s)-5,5)]
            flat=sum(1 for w in wins if len(w)>0 and w.std()<1e-10)
            C.append(self._w(f"ns_flat_{col}",flat==0,f"No flatline in {col} (sensor freeze)",f"{flat} flat windows",float(flat),0.0,cat))
        return self._r(C,E)

    # ── Layer 4: Statistical Distribution (80+ checks) ────────────────────────
    def _statistical_distribution(self, data, sim, cond):
        C=[]; cat="statistics"; nc=self._nc(data)
        for col in nc:
            s=data[col].dropna()
            if len(s)<8: continue
            skew=float(s.skew()); kurt=float(s.kurtosis()); n=len(s)
            C.append(self._w(f"dist_skew_{col}",abs(skew)<5,"Skewness reasonable",f"skew={skew:.3f}",float(skew),5.0,cat))
            C.append(self._w(f"dist_kurt_{col}",abs(kurt)<20,"Kurtosis reasonable",f"kurt={kurt:.3f}",float(kurt),20.0,cat))
            # Extreme skewness
            C.append(self._w(f"dist_extreme_skew_{col}",abs(skew)<10,"No extreme skewness",f"skew={skew:.3f}",float(abs(skew)),10.0,cat))
            if n<=50:
                try:
                    _,p=stats.shapiro(s)
                    C.append(self._w(f"dist_shapiro_{col}",p>0.01,"Shapiro-Wilk normality",f"p={p:.4f}",float(p),0.01,cat))
                except: pass
            else:
                try:
                    _,p=stats.normaltest(s)
                    C.append(self._w(f"dist_dagostino_{col}",p>0.001,"D'Agostino normality",f"p={p:.4f}",float(p),0.001,cat))
                except: pass
            if n>5:
                bc=(skew**2+1)/(kurt+3*(n-1)**2/((n-2)*(n-3))) if n>5 else 0
                C.append(self._w(f"dist_bimodal_{col}",bc<0.555,"No bimodality (single population)",f"BC={bc:.3f}",float(bc),0.555,cat))
            q1,q3=float(s.quantile(.25)),float(s.quantile(.75))
            C.append(self._w(f"dist_iqr_{col}",q3>=q1,"IQR non-negative",f"IQR={q3-q1:.4g}",float(q3-q1),0.0,cat))
            if s.std()>0:
                rng=float(s.max()-s.min())
                C.append(self._w(f"dist_rng_std_{col}",rng/s.std()<30,"Range/std reasonable",f"{rng/s.std():.2f}",rng/s.std(),30.0,cat))
            # Coefficient of variation check
            if s.mean()!=0:
                cv=abs(float(s.std()/s.mean()))
                C.append(self._w(f"dist_cv_{col}",cv<2.0,f"CV of {col} reasonable for physics",f"CV={cv:.3f}",float(cv),2.0,cat))
            # Interquartile check
            p10=float(s.quantile(.10)); p90=float(s.quantile(.90))
            C.append(self._w(f"dist_p10p90_{col}",p90>=p10,"P10<P90 ordering",f"P10={p10:.4g} P90={p90:.4g}",cat=cat))
        return self._r(C)

    # ── Layer 5: Outlier Detection (4 methods, all columns) ───────────────────
    def _outlier_detection(self, data, sim, cond):
        C=[]; E=[]; cat="outliers"; nc=self._nc(data)
        for col in nc:
            s=data[col].dropna()
            if len(s)<4: continue
            # Modified Z-score
            med=s.median(); mad=np.median(np.abs(s-med))
            if mad>0:
                mz=0.6745*(s-med)/mad; out=s.index[np.abs(mz)>3.5]
                C.append(self._w(f"out_mz_{col}",len(out)==0,f"No modified Z outliers in {col}",f"{len(out)}",float(len(out)),0.0,cat))
                for idx in out:
                    E.append(TrialExclusion(int(idx),f"Modified Z-score outlier in {col} (|Z|={abs(float(mz.loc[idx])):.2f})","warning",{col:float(s.loc[idx])}))
            # Tukey fences
            q1,q3=s.quantile(.25),s.quantile(.75); iqr=q3-q1
            ext=s.index[(s<q1-3*iqr)|(s>q3+3*iqr)]
            C.append(self._w(f"out_tukey_{col}",len(ext)==0,f"No Tukey extreme outliers in {col}",f"{len(ext)}",float(len(ext)),0.0,cat))
            # 4-sigma rule
            if s.std()>0:
                sig4=(np.abs((s-s.mean())/s.std())>4).sum()
                C.append(self._w(f"out_4sig_{col}",sig4==0,f"No 4σ outliers in {col}",f"{sig4}",float(sig4),0.0,cat))
            # Grubbs test
            if len(s)>=6 and s.std()>0:
                try:
                    z_max=float(np.abs(s-s.mean()).max()/s.std())
                    t_c=stats.t.ppf(1-0.025/(2*len(s)),len(s)-2)
                    g_c=((len(s)-1)/np.sqrt(len(s)))*np.sqrt(t_c**2/(len(s)-2+t_c**2))
                    C.append(self._w(f"out_grubbs_{col}",z_max<g_c,f"Grubbs single outlier {col}",f"G={z_max:.3f} crit={g_c:.3f}",float(z_max),float(g_c),cat))
                except: pass
            # Dixon's Q test (small samples)
            if 3<=len(s)<=30:
                try:
                    sv=s.sort_values()
                    q_stat=float((sv.iloc[-1]-sv.iloc[-2])/(sv.iloc[-1]-sv.iloc[0]))
                    C.append(self._w(f"out_dixon_{col}",q_stat<0.5,f"Dixon Q test {col}",f"Q={q_stat:.3f}",float(q_stat),0.5,cat))
                except: pass
        return self._r(C,E)

    # ── Layer 6: Cross-Variable Consistency (50+ physics relationships) ───────
    def _cross_variable(self, data, sim, cond):
        C=[]; E=[]; cat="cross_variable"; cols=set(data.columns)
        # Mach = v/c_sound
        if {"velocity","mach_number"}.issubset(cols):
            exp=data["velocity"]/P["c_sound"]; err=np.abs(data["mach_number"]-exp)
            bad=err>0.002; nb=int(bad.sum())
            C.append(self._w("cx_mach_vel",nb==0,"Mach=v/343 consistent",f"{nb} inconsistent",float(nb),0.0,cat))
            for idx in data.index[bad]:
                E.append(TrialExclusion(int(idx),f"Mach/velocity mismatch: vel={data.loc[idx,'velocity']:.2f}→Mach={exp.loc[idx]:.4f} got {data.loc[idx,'mach_number']:.4f}","critical"))
        # Ideal gas P=ρRT
        if {"pressure","density","temperature"}.issubset(cols):
            exp_p=data["density"]*P["R_air"]*data["temperature"]
            rel=np.abs(data["pressure"]-exp_p)/exp_p.clip(lower=1e-10)
            bad=rel>0.2; nb=int(bad.sum())
            C.append(self._w("cx_ideal_gas",nb==0,"P=ρRT satisfied",f"{nb}",float(nb),0.0,cat))
            for idx in data.index[bad]:
                E.append(TrialExclusion(int(idx),"Ideal gas violation P≠ρRT","warning"))
            # Gas-constant unit check: even in-bounds P breaks if it is in kPa not Pa.
            # P/(ρT) must equal R_air=287.05; ~0.287 means P is off by 1000×.
            R_calc=data["pressure"]/(data["density"]*data["temperature"]).clip(lower=1e-10)
            ubad=(R_calc<250)|(R_calc>320); nu=int(ubad.sum())
            C.append(self._c("cx_gas_constant_check",nu==0,
                "P/(ρT) = R_air = 287 J/kg·K (unit consistency check)",
                f"{nu} trials where P/(ρT) deviates >10% from 287 — possible unit error",float(nu),cat=cat))
            for idx in data.index[ubad]:
                E.append(TrialExclusion(int(idx),
                    f"Gas constant check: P/(ρT)={float(R_calc.loc[idx]):.1f} (expected 287) — unit error?","critical"))
        # Bernoulli P+0.5ρv²=const
        if {"pressure","velocity"}.issubset(cols):
            rho=cond.get("density",P["rho_air"])
            tot=data["pressure"]+0.5*rho*data["velocity"]**2
            cv=float(tot.std()/tot.mean()) if tot.mean()!=0 else 0
            C.append(self._w("cx_bernoulli",cv<0.05,"Bernoulli conserved",f"CV={cv:.4f}",float(cv),0.05,cat))
        # Dynamic pressure
        if {"dynamic_pressure","velocity"}.issubset(cols):
            rho=cond.get("density",P["rho_air"])
            exp_q=0.5*rho*data["velocity"]**2
            bad=(np.abs(data["dynamic_pressure"]-exp_q)/exp_q.clip(lower=1e-10)>0.05).sum()
            C.append(self._w("cx_dynq",bad==0,"q=0.5ρv²",f"{bad}",float(bad),0.0,cat))
        # Von Mises from principals
        if {"von_mises_stress","principal_stress_1","principal_stress_2","principal_stress_3"}.issubset(cols):
            s1,s2,s3=data["principal_stress_1"],data["principal_stress_2"],data["principal_stress_3"]
            vm=np.sqrt(0.5*((s1-s2)**2+(s2-s3)**2+(s3-s1)**2))
            bad=(np.abs(data["von_mises_stress"]-vm)/vm.clip(lower=1e-10)>0.05).sum()
            C.append(self._w("cx_von_mises",bad==0,"VM=√(0.5[(σ1-σ2)²+...])",f"{bad}",float(bad),0.0,cat))
        # Principal stress ordering
        if {"principal_stress_1","principal_stress_2"}.issubset(cols):
            bad=(data["principal_stress_1"]<data["principal_stress_2"]).sum()
            C.append(self._w("cx_ps12",bad==0,"σ1≥σ2",f"{bad}",float(bad),0.0,cat))
        if {"principal_stress_2","principal_stress_3"}.issubset(cols):
            bad=(data["principal_stress_2"]<data["principal_stress_3"]).sum()
            C.append(self._w("cx_ps23",bad==0,"σ2≥σ3",f"{bad}",float(bad),0.0,cat))
        # Hooke's law σ=Eε
        if {"stress","strain","elastic_modulus"}.issubset(cols):
            exp_s=data["elastic_modulus"]*data["strain"]
            bad=(np.abs(data["stress"]-exp_s)/exp_s.clip(lower=1e-10)>0.15).sum()  # Hooke's law exact in linear regime
            C.append(self._w("cx_hooke",bad==0,"σ=Eε (Hooke's Law)",f"{bad}",float(bad),0.0,cat))
        # Carnot η=1-Tc/Th
        if "carnot_efficiency" in cols:
            Th=cond.get("hot_temperature",800); Tc=cond.get("cold_temperature",300)
            if Th>0:
                exp_eta=1-Tc/Th
                bad=(np.abs(data["carnot_efficiency"]-exp_eta)>0.05).sum()
                C.append(self._w("cx_carnot",bad==0,"η_Carnot=1-Tc/Th",f"{bad}",float(bad),0.0,cat))
        # 2nd law: η_thermal ≤ η_Carnot
        if {"thermal_efficiency","carnot_efficiency"}.issubset(cols):
            bad=(data["thermal_efficiency"]>data["carnot_efficiency"]+0.01).sum()
            C.append(self._c("cx_2ndlaw",bad==0,"η_thermal≤η_Carnot (2nd Law)",f"{bad} violations",float(bad),cat=cat))
        # P=τω
        if {"joint_torque","joint_velocity","power_consumption"}.issubset(cols):
            exp_p=np.abs(data["joint_torque"]*data["joint_velocity"])
            bad=(np.abs(data["power_consumption"]-exp_p)/data["power_consumption"].clip(lower=1e-10)>0.2).sum()
            C.append(self._w("cx_power_torque",bad==0,"P=τω",f"{bad}",float(bad),0.0,cat))
        # Mass fractions sum to 1
        fcols=[c for c in ["mass_fraction_fuel","mass_fraction_oxidizer","mass_fraction_products"] if c in cols]
        if len(fcols)==3:
            bad=(np.abs(data[fcols].sum(axis=1)-1)>0.05).sum()
            C.append(self._w("cx_mass_frac",bad==0,"Mass fractions sum=1",f"{bad}",float(bad),0.0,cat))
        # Kirchhoff α+τ+ρ=1
        rcols=[c for c in ["emissivity","absorptivity","transmissivity"] if c in cols]
        if len(rcols)==3:
            bad=(np.abs(data[rcols].sum(axis=1)-1)>0.05).sum()
            C.append(self._w("cx_kirchhoff",bad==0,"α+τ+ρ=1",f"{bad}",float(bad),0.0,cat))
        # c=fλ
        if {"frequency","wavelength"}.issubset(cols):
            c_calc=data["frequency"]*data["wavelength"]
            bad=(np.abs(c_calc-P["c_sound"])/P["c_sound"]>0.05).sum()
            C.append(self._w("cx_c_flambda",bad==0,"c=fλ (acoustic)",f"{bad}",float(bad),0.0,cat))
        # EM: c=fλ
        if {"frequency","wavelength"}.issubset(cols) and sim==SimulationType.ELECTROMAGNETICS:
            bad=(np.abs(data["frequency"]*data["wavelength"]-P["c"])/P["c"]>0.05).sum()
            C.append(self._w("cx_em_c_flam",bad==0,"c=fλ (EM)",f"{bad}",float(bad),0.0,cat))
        # Terzaghi σ'=σ-u
        if {"effective_stress","stress","pore_pressure"}.issubset(cols):
            exp=data["stress"]-data["pore_pressure"]
            bad=(np.abs(data["effective_stress"]-exp)/np.abs(exp).clip(lower=1e-10)>0.05).sum()
            C.append(self._w("cx_terzaghi",bad==0,"σ'=σ-u (Terzaghi)",f"{bad}",float(bad),0.0,cat))
        # SF = yield/VM
        if {"safety_factor","von_mises_stress","yield_stress"}.issubset(cols):
            exp_sf=data["yield_stress"]/data["von_mises_stress"].replace(0,np.nan)
            bad=(np.abs(data["safety_factor"]-exp_sf)/exp_sf.clip(lower=1e-10)>0.1).sum()
            C.append(self._w("cx_sf_vm",bad==0,"SF=yield/VM",f"{bad}",float(bad),0.0,cat))
        # Re=ρvL/μ
        if {"reynolds_number","velocity"}.issubset(cols):
            rho=cond.get("density",P["rho_air"]); mu=cond.get("viscosity",P["mu_air"]); L=cond.get("length_scale",0.5)
            if mu>0 and L>0:
                exp_re=rho*data["velocity"]*L/mu
                rel_re=np.abs(data["reynolds_number"]-exp_re)/exp_re.clip(lower=1e-10)
                bad_mask=rel_re>0.15  # tightened from 0.35 (still allows fluid-property variation)
                bad=int(bad_mask.sum())
                C.append(self._w("cx_reynolds",bad==0,"Re=ρvL/μ",f"{bad}",float(bad),0.0,cat))
                for idx in data.index[bad_mask]:
                    E.append(TrialExclusion(int(idx),f"Re inconsistent with ρvL/μ (rel err {float(rel_re.loc[idx]):.2f})","warning"))
        # Wave c=λ/T
        if {"wave_speed","wave_length","wave_period"}.issubset(cols):
            exp_c=data["wave_length"]/data["wave_period"].replace(0,np.nan)
            bad=(np.abs(data["wave_speed"]-exp_c)/exp_c.clip(lower=1e-10)>0.05).sum()
            C.append(self._w("cx_wave_c",bad==0,"c=λ/T (wave)",f"{bad}",float(bad),0.0,cat))
        # Debye length λ_D=√(ε₀kT/ne²)
        if {"debye_length","electron_temperature","electron_density"}.issubset(cols):
            exp_ld=np.sqrt(P["eps0"]*P["k_b"]*data["electron_temperature"]/(data["electron_density"].clip(lower=1)*P["e"]**2))
            bad=(np.abs(data["debye_length"]-exp_ld)/exp_ld.clip(lower=1e-30)>0.3).sum()
            C.append(self._w("cx_debye",bad==0,"Debye λ=√(ε₀kT/ne²)",f"{bad}",float(bad),0.0,cat))
        # Wien λ_max*T=b
        if {"wavelength","temperature"}.issubset(cols):
            exp_lam=P["wien_b"]/data["temperature"].clip(lower=1e-10)
            bad=(np.abs(data["wavelength"]-exp_lam)/exp_lam.clip(lower=1e-30)>0.5).sum()
            C.append(self._w("cx_wien",bad==0,"Wien λ_max·T=b",f"{bad}",float(bad),0.0,cat))
        # Stribeck λ=h/Ra
        if {"lambda_ratio","film_thickness","surface_roughness"}.issubset(cols):
            exp_lam=data["film_thickness"]/data["surface_roughness"].replace(0,np.nan)
            bad=(np.abs(data["lambda_ratio"]-exp_lam)/exp_lam.clip(lower=1e-10)>0.1).sum()
            C.append(self._w("cx_stribeck",bad==0,"λ=h/Ra",f"{bad}",float(bad),0.0,cat))
        # pH + pOH = 14
        if {"ph","poh"}.issubset(cols):
            bad=(np.abs(data["ph"]+data["poh"]-14)>0.1).sum()
            C.append(self._w("cx_ph_poh",bad==0,"pH+pOH=14",f"{bad}",float(bad),0.0,cat))
        # Conductivity ρ=1/σ
        if {"conductivity","resistivity"}.issubset(cols):
            exp_r=1/data["conductivity"].replace(0,np.nan)
            bad=(np.abs(data["resistivity"]-exp_r)/exp_r.clip(lower=1e-30)>0.05).sum()
            C.append(self._w("cx_cond_resist",bad==0,"ρ=1/σ",f"{bad}",float(bad),0.0,cat))
        # Shear modulus G=E/(2(1+ν))
        if {"elastic_modulus","poisson_ratio","shear_modulus"}.issubset(cols):
            exp_G=data["elastic_modulus"]/(2*(1+data["poisson_ratio"]))
            bad=(np.abs(data["shear_modulus"]-exp_G)/exp_G.clip(lower=1e-10)>0.1).sum()
            C.append(self._w("cx_shear_mod",bad==0,"G=E/[2(1+ν)]",f"{bad}",float(bad),0.0,cat))
        # Bulk modulus K=E/(3(1-2ν))
        if {"elastic_modulus","poisson_ratio","bulk_modulus"}.issubset(cols):
            exp_K=data["elastic_modulus"]/(3*(1-2*data["poisson_ratio"]))
            bad=(np.abs(data["bulk_modulus"]-exp_K)/exp_K.clip(lower=1e-10)>0.1).sum()
            C.append(self._w("cx_bulk_mod",bad==0,"K=E/[3(1-2ν)]",f"{bad}",float(bad),0.0,cat))
        # Velocity components |v|=sqrt(vx²+vy²+vz²)
        if {"velocity_x","velocity_y","velocity_z","velocity"}.issubset(cols):
            v_mag=np.sqrt(data["velocity_x"]**2+data["velocity_y"]**2+data["velocity_z"]**2)
            bad=(np.abs(v_mag-data["velocity"])/v_mag.clip(lower=1e-10)>0.02).sum()
            C.append(self._w("cx_vel_components",bad==0,"‖(vx,vy,vz)‖=|v|",f"{bad}",float(bad),0.0,cat))
        # Strain energy 0.5σε≥0
        if {"stress","strain"}.issubset(cols):
            bad=(0.5*data["stress"]*data["strain"]<0).sum()
            C.append(self._c("cx_strain_energy",bad==0,"Strain energy 0.5σε≥0",f"{bad}",float(bad),cat=cat))
        # UTS > yield
        if {"ultimate_stress","yield_stress"}.issubset(cols):
            bad=(data["ultimate_stress"]<data["yield_stress"]).sum()
            C.append(self._c("cx_uts_gt_ys",bad==0,"UTS>yield stress",f"{bad}",float(bad),cat=cat))
        # L/D ratio finite
        if {"lift_coefficient","drag_coefficient"}.issubset(cols):
            ld=data["lift_coefficient"]/data["drag_coefficient"].replace(0,np.nan)
            bad=(ld.abs()>200).sum()
            C.append(self._w("cx_ld_finite",bad==0,"L/D ratio finite",f"{bad}",float(bad),0.0,cat))
        # Pressure coefficient Cp≤1
        if "pressure_coefficient" in cols:
            bad=(data["pressure_coefficient"]>1.01).sum()
            C.append(self._c("cx_cp_max",bad==0,"Cp≤1.0 (stagnation limit)",f"{bad}",float(bad),cat=cat))
        # Stefan-Boltzmann q=εσT⁴
        if {"heat_flux","temperature","emissivity"}.issubset(cols):
            exp_q=data["emissivity"]*P["sigma_sb"]*data["temperature"]**4
            bad=(np.abs(data["heat_flux"]-exp_q)/exp_q.clip(lower=1e-10)>0.5).sum()
            C.append(self._w("cx_stefan",bad==0,"q=εσT⁴",f"{bad}",float(bad),0.0,cat))
        # Nernst equation check (electrochemistry)
        if {"electric_potential","temperature","concentration"}.issubset(cols):
            R=P["R_gas"]; F=P["faraday"]
            nernst_factor=R*data["temperature"]/F
            C.append(self._w("cx_nernst_scale",float(nernst_factor.mean())>0,"Nernst RT/F positive",f"mean={float(nernst_factor.mean()):.4f}",cat=cat))
        # Magnetic flux density B: Alfvén speed va=B/sqrt(μ₀ρ)
        if {"alfven_speed","magnetic_field","density"}.issubset(cols):
            exp_va=data["magnetic_field"].abs()/np.sqrt(P["mu0"]*data["density"].clip(lower=1e-30))
            bad=(np.abs(data["alfven_speed"]-exp_va)/exp_va.clip(lower=1e-30)>0.3).sum()
            C.append(self._w("cx_alfven",bad==0,"vA=B/√(μ₀ρ)",f"{bad}",float(bad),0.0,cat))
        return self._r(C,E)

    # ── Layer 7: Conservation Laws ─────────────────────────────────────────────
    def _conservation_laws(self, data, sim, cond):
        C=[]; cat="conservation"
        if {"heat_input","work_output","heat_rejected"}.issubset(data.columns):
            bad=(np.abs(data["heat_input"]-data["work_output"]-data["heat_rejected"])/data["heat_input"].clip(lower=1e-10)>0.05).sum()
            C.append(self._c("cons_1stlaw",bad==0,"1st Law: Qin=W+Qout",f"{bad}",float(bad),cat=cat))
        if "entropy_generation" in data.columns:
            neg=(data["entropy_generation"]<0).sum()
            C.append(self._c("cons_2ndlaw",neg==0,"2nd Law: Sgen≥0",f"{neg}",float(neg),cat=cat))
        if {"mass_flow_rate","density","velocity"}.issubset(data.columns):
            A=cond.get("cross_section_area",1.0)
            bad=(np.abs(data["mass_flow_rate"]-data["density"]*data["velocity"]*A)/data["density"].clip(lower=1e-10)>0.1).sum()
            C.append(self._w("cons_continuity",bad==0,"ṁ=ρvA (continuity)",f"{bad}",float(bad),0.0,cat))
        if {"joint_torque","joint_acceleration","inertia"}.issubset(data.columns):
            bad=(np.abs(data["joint_torque"]-data["inertia"]*data["joint_acceleration"])/np.abs(data["inertia"]*data["joint_acceleration"]).clip(lower=1e-10)>0.3).sum()
            C.append(self._w("cons_angular_mom",bad==0,"τ=Iα (Newton 2nd rot.)",f"{bad}",float(bad),0.0,cat))
        if {"kinetic_energy","potential_energy"}.issubset(data.columns):
            tot=data["kinetic_energy"]+data["potential_energy"]
            cv=float(tot.std()/tot.mean()) if tot.mean()!=0 else 0
            C.append(self._w("cons_mech_energy",cv<0.1,"KE+PE conserved",f"CV={cv:.4f}",float(cv),0.1,cat))
        if {"mass_fraction_fuel","mass_fraction_oxidizer","mass_fraction_products"}.issubset(data.columns):
            bad=(np.abs(data[["mass_fraction_fuel","mass_fraction_oxidizer","mass_fraction_products"]].sum(axis=1)-1)>0.05).sum()
            C.append(self._c("cons_comb_mass",bad==0,"Combustion mass fractions=1",f"{bad}",float(bad),cat=cat))
        if {"co_concentration","co2_concentration"}.issubset(data.columns):
            bad=((data["co_concentration"]+data["co2_concentration"])>1.01).sum()
            C.append(self._c("cons_carbon",bad==0,"CO+CO2≤1 (carbon balance)",f"{bad}",float(bad),cat=cat))
        if "criticality_factor" in data.columns:
            cv=float(data["criticality_factor"].std()/data["criticality_factor"].mean()) if data["criticality_factor"].mean()!=0 else 0
            C.append(self._w("cons_keff",cv<0.05,"keff stable (nuclear criticality)",f"CV={cv:.4f}",float(cv),0.05,cat))
        if {"exergy","heat_input"}.issubset(data.columns):
            bad=(data["exergy"]>data["heat_input"]*1.01).sum()
            C.append(self._c("cons_exergy",bad==0,"Exergy≤heat input",f"{bad}",float(bad),cat=cat))
        if {"work_output","thermal_efficiency","heat_input"}.issubset(data.columns):
            bad=(np.abs(data["work_output"]-data["thermal_efficiency"]*data["heat_input"])/data["heat_input"].clip(lower=1e-10)>0.05).sum()
            C.append(self._w("cons_thermal_work",bad==0,"W=η·Qin",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Layer 8: Dimensional Consistency ──────────────────────────────────────
    def _dimensional(self, data, sim, cond):
        C=[]; cat="dimensional"
        if {"nusselt_number","reynolds_number"}.issubset(data.columns):
            corr=np.log10(data["reynolds_number"].clip(lower=1)).corr(np.log10(data["nusselt_number"].clip(lower=1)))
            C.append(self._w("dim_nu_re",corr>0.2,"Nu∝Re^n correlation",f"corr={corr:.3f}",float(corr),0.2,cat))
        if {"weber_number","velocity"}.issubset(data.columns):
            corr=np.log10(data["weber_number"].clip(lower=1e-10)).corr(np.log10(data["velocity"].clip(lower=1e-10)))
            C.append(self._w("dim_weber_v",corr>0,"We∝v² positive correlation",f"corr={corr:.3f}",float(corr),0.0,cat))
        if {"stress","von_mises_stress"}.issubset(data.columns):
            ratio=(data["stress"].abs()+1e-30)/(data["von_mises_stress"].abs()+1e-30)
            bad=((ratio>5)|(ratio<0.2)).sum()
            C.append(self._w("dim_stress_vm",bad==0,"stress and VM same magnitude",f"{bad}",float(bad),0.0,cat))
        if {"nusselt_number","prandtl_number","reynolds_number"}.issubset(data.columns):
            # Dittus-Boelter: Nu ≈ 0.023 Re^0.8 Pr^0.4
            re=data["reynolds_number"].clip(lower=1); pr=data["prandtl_number"].clip(lower=0.001)
            exp_nu=0.023*re**0.8*pr**0.4
            rel=np.abs(data["nusselt_number"]-exp_nu)/exp_nu.clip(lower=1)
            bad=(rel>1.0).sum()  # allow 100% deviation for non-pipe geometries
            C.append(self._w("dim_dittus_boelter",bad==0,"Nu≈0.023Re⁰·⁸Pr⁰·⁴ (Dittus-Boelter order of magnitude)",f"{bad}",float(bad),0.0,cat))
        if {"grashof_number","rayleigh_number","prandtl_number"}.issubset(data.columns):
            exp_ra=data["grashof_number"]*data["prandtl_number"]
            rel=np.abs(data["rayleigh_number"]-exp_ra)/exp_ra.clip(lower=1e-10)
            bad=(rel>0.05).sum()
            C.append(self._w("dim_ra_gr_pr",bad==0,"Ra=Gr·Pr",f"{bad}",float(bad),0.0,cat))
        if {"froude_number","velocity","water_depth"}.issubset(data.columns):
            exp_fr=data["velocity"]/np.sqrt(P["g"]*data["water_depth"].clip(lower=1e-10))
            bad=(np.abs(data["froude_number"]-exp_fr)/exp_fr.clip(lower=1e-10)>0.05).sum()
            C.append(self._w("dim_froude",bad==0,"Fr=v/√(gd)",f"{bad}",float(bad),0.0,cat))
        if {"strouhal_number","velocity"}.issubset(data.columns):
            corr=data["strouhal_number"].corr(data["velocity"])
            C.append(self._w("dim_strouhal_vel",corr<0.5,"St∝1/v (Strouhal)",f"corr={corr:.3f}",float(corr),0.5,cat))
        return self._r(C)

    # ── Layer 9: Temporal ─────────────────────────────────────────────────────
    def _temporal(self, data, sim, cond):
        C=[]; E=[]; cat="temporal"
        if "time" in data.columns:
            d=data["time"].diff().dropna()
            neg=(d<0).sum()
            C.append(self._c("temp_monotonic",neg==0,"Time monotonically increasing",f"{neg}",float(neg),cat=cat))
            zero=(d==0).sum()
            C.append(self._w("temp_no_dup",zero==0,"No duplicate timestamps",f"{zero}",float(zero),0.0,cat))
            if len(d)>3:
                pos=d[d>0]
                if len(pos)>0 and pos.mean()!=0:
                    cv=float(pos.std()/pos.mean())
                    C.append(self._w("temp_uniform_dt",cv<0.15,"Uniform timestep",f"CV={cv:.4f}",float(cv),0.15,cat))
                    # Check for gaps
                    large_gaps=(pos>pos.mean()*5).sum()
                    C.append(self._w("temp_no_gaps",large_gaps==0,"No large time gaps",f"{large_gaps}",float(large_gaps),0.0,cat))
        for col in self._nc(data)[:8]:
            s=data[col].dropna()
            if len(s)>3:
                d=s.diff().dropna()
                if d.std()>0:
                    j=(np.abs(d/d.std())>10).sum()
                    C.append(self._w(f"temp_jump_{col}",j==0,f"No discontinuous jumps in {col}",f"{j}",float(j),0.0,cat))
        # Sub-threshold drift + distribution shift (targets sensor-drift corruption
        # whose values are individually in-bounds but collectively trend/shift).
        for col in self._nc(data):
            dc=self._check_monotonic_drift(data,col)
            if dc is not None: C.append(dc)
            sc,se=self._check_distribution_shift(data,col)
            C.extend(sc); E.extend(se)
            cc,ce=self._check_change_point_drift(data,col)
            C.extend(cc); E.extend(ce)
        return self._r(C,E)

    def _changepoint_on_series(self, s, label, min_tau=0.15):
        """CUSUM change-point on a 1-D series: if it has a statistically significant
        trend, locate the shift and exclude the drifted segment. Shared by the
        raw-column and cross-variable-residual drift detectors."""
        from scipy.stats import kendalltau
        s=s.dropna()
        n=len(s)
        if n<40: return [],[]
        vals=s.values.astype(float); idx=s.index.to_numpy()
        mu=float(vals.mean()); sd=float(vals.std())
        if sd==0 or not np.isfinite(sd): return [],[]
        tau,p=kendalltau(range(n),vals)
        if p is None or p>=0.01 or abs(tau)<min_tau: return [],[]
        cp=int(np.argmax(np.abs(np.cumsum(vals-mu))))
        if cp<5 or cp>n-5: return [],[]
        mb=float(vals[:cp+1].mean()); ma=float(vals[cp+1:].mean())
        if abs(ma-mb) < 0.5*sd: return [],[]
        base=float(np.median(vals[:max(5,n//7)]))
        drift_after=abs(ma-base)>=abs(mb-base)
        seg_idx=idx[cp+1:] if drift_after else idx[:cp+1]
        z=abs((ma if drift_after else mb)-base)/sd
        C=[self._w(f"temp_changepoint_{label}",False,
            f"Change-point drift in {label} at trial ~{cp+1}",
            f"Mean shifts {mb:.4g}→{ma:.4g} at trial {cp+1} (τ={tau:.2f}); drifted segment excluded",
            float(z),0.5,"temporal_drift")]
        E=[TrialExclusion(int(i),f"Drifted segment in {label} (change-point at trial {cp+1})","warning") for i in seg_idx]
        return C,E

    def _check_change_point_drift(self, data, col):
        """Change-point drift on a raw column."""
        return self._changepoint_on_series(data[col], col)

    def _relationship_drift(self, data, sim, cond):
        """Detect sensor drift buried in a column's marginal distribution but that
        breaks a physical relationship. For pairs that should be proportional
        (Re/v, Ma/v, P/ρ, σ/ε, …) the ratio is near-constant, so when a significant
        trend exists we exclude precisely the trials whose ratio deviates from the
        clean (early) baseline — high recall without gutting clean data."""
        from scipy.stats import kendalltau
        C=[]; E=[]; cols=set(data.columns)
        pairs=[("reynolds_number","velocity"),("mach_number","velocity"),
               ("dynamic_pressure","velocity"),("pressure","density"),
               ("stress","strain"),("heat_flux","temperature"),
               ("lift_coefficient","drag_coefficient"),("power_consumption","joint_torque")]
        for a,b in pairs:
            if not {a,b}.issubset(cols): continue
            ratio=(data[a]/data[b].replace(0,np.nan)).replace([np.inf,-np.inf],np.nan).dropna()
            if len(ratio)<40: continue
            vals=ratio.values.astype(float); idx=ratio.index.to_numpy()
            tau,p=kendalltau(range(len(vals)),vals)
            if p is None or p>=0.01 or abs(tau)<0.12: continue      # a real trend must exist
            k=max(10,len(vals)//5)
            base=float(np.median(vals[:k]))
            mad=float(np.median(np.abs(vals[:k]-base)))
            scale=mad*1.4826 if mad>0 else max(float(np.std(vals[:k])),1e-9)
            bad=np.abs(vals-base)/max(scale,1e-9) > 5.0            # >5 robust-σ from clean baseline
            nb=int(bad.sum())
            if nb==0: continue
            C.append(self._w(f"reldrift_{a}:{b}",False,
                f"Sensor drift in the {a}/{b} relationship",
                f"{nb} trials where {a}/{b} deviates >5σ from the clean baseline (τ={tau:.2f}) — progressive sensor drift",
                float(nb),0.0,"temporal_drift"))
            for i in idx[bad]:
                E.append(TrialExclusion(int(i),f"Relationship drift: {a}/{b} off its clean baseline","warning"))
        return self._r(C,E)

    def _check_monotonic_drift(self, data, col, threshold_pct=0.05):
        """Mann-Kendall trend test: catches monotonic drift too weak for linear
        regression (R<0.7) but still statistically significant."""
        from scipy.stats import kendalltau
        s=data[col].dropna()
        if len(s)<20: return None
        tau,p=kendalltau(range(len(s)),s.values)
        if p is not None and p<0.01 and abs(tau)>0.2:
            return self._w(f"temp_drift_{col}",False,
                f"Statistically significant monotonic drift in {col}",
                f"Mann-Kendall τ={tau:.3f}, p={p:.4f} — possible sensor drift or condition change",
                float(tau),0.2,"temporal_drift")
        return None

    def _check_distribution_shift(self, data, col, n_windows=10):
        """Detect windows whose mean deviates >2.5σ from the dataset mean — the
        run-to-run condition-change signature. Drifted windows are excluded."""
        s=data[col].dropna().reset_index(drop=True)
        if len(s)<n_windows*5: return [],[]
        w=len(s)//n_windows; mu=s.mean(); sd=s.std()
        if sd==0: return [],[]
        C=[]; E=[]
        for i in range(n_windows):
            win=s.iloc[i*w:(i+1)*w]
            if len(win)==0: continue
            z=abs(win.mean()-mu)/sd
            if z>2.5:
                C.append(self._w(f"temp_shift_{col}_w{i}",False,
                    f"Distribution shift in {col} around trial {i*w+1}",
                    f"Window {i+1} mean deviates {z:.1f}σ from dataset mean — possible condition change",
                    float(z),2.5,"distribution_shift"))
                for idx in win.index:
                    E.append(TrialExclusion(int(idx),
                        f"Distribution shift in {col} (window {i+1}, {z:.1f}σ)","warning"))
        return C,E

    def _near_duplicates(self, data, sim, cond):
        """Detect blocks of near-identical trials in feature space — catches
        copy-paste contamination even when values were slightly perturbed.
        (numpy cosine similarity; equivalent to StandardScaler+cosine_similarity.)"""
        C=[]; E=[]; cat="near_duplicates"
        nc=self._nc(data)
        if len(nc)<2 or len(data)<10: return self._r(C,E)
        X=data[nc].fillna(0).values.astype(float)
        mu=X.mean(0); sd=X.std(0); sd[sd==0]=1.0
        X=(X-mu)/sd
        norms=np.linalg.norm(X,axis=1); norms[norms==0]=1.0
        Xn=X/norms[:,None]
        window=5; n=len(Xn)
        for i in range(n-window):
            sims=Xn[i]@Xn[i+1:i+1+window].T
            if (sims>0.999).any():
                matches=[i+1+j+1 for j,sv in enumerate(sims) if sv>0.999]
                mx=float(sims.max())
                C.append(self._w(f"nd_block_{i}",False,
                    f"Trial {i+1} is nearly identical to trials {matches}",
                    "Cosine similarity > 0.999 — likely copy-paste or data duplication",
                    mx,0.999,cat))
                E.append(TrialExclusion(i,f"Near-duplicate of trials {matches} (sim={mx:.4f})","warning"))
        return self._r(C,E)

    # ── Layer 10: Monotonicity ────────────────────────────────────────────────
    def _monotonicity(self, data, sim, cond):
        C=[]; cat="monotonicity"
        neg_pairs=[("reynolds_number","drag_coefficient"),("stress","safety_factor"),
                   ("stress","fatigue_life"),("temperature","viscosity"),
                   ("sliding_speed","friction_coefficient"),("lambda_ratio","friction_coefficient")]
        pos_pairs=[("temperature","reaction_rate"),("temperature","nox_concentration"),
                   ("velocity","drag_coefficient"),("pressure","boiling_point"),
                   ("stress","displacement"),("temperature","heat_flux"),
                   ("electron_density","plasma_frequency"),("grain_size","yield_strength")]
        for a,b in neg_pairs:
            if {a,b}.issubset(data.columns):
                corr=data[a].corr(data[b])
                C.append(self._w(f"mono_neg_{a}_{b}",corr<0.5,f"{a}↑ → {b}↓",f"corr={corr:.3f}",float(corr),0.5,cat))
        for a,b in pos_pairs:
            if {a,b}.issubset(data.columns):
                corr=data[a].corr(data[b])
                C.append(self._w(f"mono_pos_{a}_{b}",corr>-0.5,f"{a}↑ → {b}↑",f"corr={corr:.3f}",float(corr),-0.5,cat))
        if "fatigue_life" in data.columns and "stress" in data.columns:
            corr=data["stress"].corr(data["fatigue_life"])
            C.append(self._w("mono_sn_curve",corr<0,"S-N: fatigue life↓ with stress",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "sound_pressure_level" in data.columns and "acoustic_pressure" in data.columns:
            corr=data["acoustic_pressure"].corr(data["sound_pressure_level"])
            C.append(self._w("mono_spl_pres",corr>0,"SPL↑ with acoustic pressure",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "porosity" in data.columns and "permeability" in data.columns:
            corr=data["porosity"].corr(data["permeability"])
            C.append(self._w("mono_pore_perm",corr>0,"Permeability↑ with porosity (Kozeny-Carman)",f"corr={corr:.3f}",float(corr),0.0,cat))
        return self._r(C)

    # ── Layer 11: Symmetry ────────────────────────────────────────────────────
    def _symmetry(self, data, sim, cond):
        C=[]; cat="symmetry"
        for col in ["rolling_moment","side_force_coefficient","yawing_moment"]:
            if col in data.columns:
                m=abs(float(data[col].mean()))
                C.append(self._w(f"sym_{col}",m<0.1,f"{col} near zero (symmetric geometry)",f"mean={m:.4f}",m,0.1,cat))
        if {"principal_stress_1","principal_stress_2","principal_stress_3"}.issubset(data.columns):
            trace=data[["principal_stress_1","principal_stress_2","principal_stress_3"]].sum(axis=1)
            cv=float(trace.std()/trace.mean()) if trace.mean()!=0 else 0
            C.append(self._w("sym_stress_trace",cv<0.3,"Stress trace (1st invariant) consistent",f"CV={cv:.4f}",float(cv),0.3,cat))
        if "wind_direction" in data.columns:
            # Wind direction distribution should be roughly uniform (long-term)
            if len(data)>50:
                std_dir=float(data["wind_direction"].std())
                C.append(self._w("sym_wind_dir",std_dir>20,"Wind direction varies (realistic long-term)",f"std={std_dir:.1f}°",float(std_dir),20.0,cat))
        return self._r(C)

    # ── Layer 12: Scaling Laws ────────────────────────────────────────────────
    def _scaling_laws(self, data, sim, cond):
        C=[]; cat="scaling"
        if {"darcy_friction_factor","reynolds_number"}.issubset(data.columns):
            re=data["reynolds_number"].clip(lower=1)
            exp_f=0.316*re**(-0.25)
            bad=(np.abs(data["darcy_friction_factor"]-exp_f)/exp_f>0.3).sum()
            C.append(self._w("scale_blasius",bad==0,"Blasius f=0.316Re^-0.25",f"{bad}",float(bad),0.0,cat))
        if {"drag_coefficient","reynolds_number"}.issubset(data.columns):
            low=(data["reynolds_number"]<1)
            if low.sum()>3:
                exp=24/data.loc[low,"reynolds_number"]
                bad=(np.abs(data.loc[low,"drag_coefficient"]-exp)/exp>0.3).sum()
                C.append(self._w("scale_stokes",bad==0,"Stokes Cd=24/Re (Re<1)",f"{bad}",float(bad),0.0,cat))
        if {"heat_flux","temperature","emissivity"}.issubset(data.columns):
            exp_q=data["emissivity"]*P["sigma_sb"]*data["temperature"]**4
            bad=(np.abs(data["heat_flux"]-exp_q)/exp_q.clip(lower=1e-10)>0.5).sum()
            C.append(self._w("scale_stefan",bad==0,"q=εσT⁴",f"{bad}",float(bad),0.0,cat))
        if {"skin_depth","frequency","resistivity"}.issubset(data.columns):
            exp_d=np.sqrt(2*data["resistivity"]/(2*math.pi*data["frequency"]*P["mu0"]).clip(lower=1e-30))
            bad=(np.abs(data["skin_depth"]-exp_d)/exp_d.clip(lower=1e-30)>0.2).sum()
            C.append(self._w("scale_skin_depth",bad==0,"δ=√(2ρ/ωμ)",f"{bad}",float(bad),0.0,cat))
        if {"sound_pressure_level","acoustic_pressure"}.issubset(data.columns):
            p_ref=20e-6
            exp_spl=20*np.log10(data["acoustic_pressure"].clip(lower=p_ref)/p_ref)
            bad=(np.abs(data["sound_pressure_level"]-exp_spl)>2).sum()
            C.append(self._w("scale_spl",bad==0,"SPL=20log10(p/p_ref)",f"{bad}",float(bad),0.0,cat))
        if {"flow_rate","permeability","pressure_drop"}.issubset(data.columns):
            corr=data["permeability"].corr(data["flow_rate"])
            C.append(self._w("scale_darcy_law",corr>0,"Q∝k (Darcy's Law)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if {"neutron_flux","power_density"}.issubset(data.columns):
            corr=data["neutron_flux"].corr(data["power_density"])
            C.append(self._w("scale_flux_power",corr>0.5,"Power∝neutron flux",f"corr={corr:.3f}",float(corr),0.5,cat))
        if {"grain_size","yield_strength"}.issubset(data.columns):
            corr=np.log10(data["grain_size"].clip(lower=1e-10)).corr(data["yield_strength"])
            C.append(self._w("scale_hall_petch",corr<0,"Hall-Petch: yield↑ as grain↓",f"corr={corr:.3f}",float(corr),0.0,cat))
        if {"electron_density","plasma_frequency"}.issubset(data.columns):
            exp_wp=np.sqrt(data["electron_density"]*P["e"]**2/(P["eps0"]*9.109e-31))
            bad=(np.abs(data["plasma_frequency"]-exp_wp)/exp_wp.clip(lower=1e-30)>0.3).sum()
            C.append(self._w("scale_plasma_freq",bad==0,"ωp=√(ne²/ε₀mₑ)",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Layer 13: Information Entropy ─────────────────────────────────────────
    def _information_entropy(self, data, sim, cond):
        C=[]; cat="entropy"
        for col in self._nc(data)[:15]:
            s=data[col].dropna()
            if len(s)<8: continue
            try:
                counts,_=np.histogram(s,bins=min(10,len(s)//3))
                counts=counts[counts>0]; probs=counts/counts.sum()
                ent=float(-np.sum(probs*np.log2(probs)))
                max_e=math.log2(len(counts)); rel=ent/max_e if max_e>0 else 0
                C.append(self._w(f"ent_div_{col}",rel>0.3,f"{col} value diversity",f"{rel*100:.0f}% of max",float(rel),0.3,cat))
                # Check for near-zero entropy (essentially constant)
                C.append(self._w(f"ent_nonconst_{col}",rel>0.1,f"{col} not constant",f"H={ent:.3f} bits",float(ent),0.0,cat))
            except: pass
        return self._r(C)

    # ── Layer 14: Autocorrelation ─────────────────────────────────────────────
    def _autocorrelation(self, data, sim, cond):
        C=[]; cat="autocorrelation"
        for col in self._nc(data)[:10]:
            s=data[col].dropna()
            if len(s)<10: continue
            try:
                for lag in [1,2,3,5]:
                    ac=float(s.autocorr(lag=lag))
                    thr=0.95-lag*0.05
                    C.append(self._w(f"ac_lag{lag}_{col}",abs(ac)<thr,f"Lag-{lag} autocorr {col}",f"r={ac:.3f}",float(ac),thr,cat))
            except: pass
        return self._r(C)

    # ── Layer 15: Stationarity ────────────────────────────────────────────────
    def _stationarity(self, data, sim, cond):
        C=[]; cat="stationarity"
        for col in self._nc(data)[:10]:
            s=data[col].dropna()
            if len(s)<16: continue
            try:
                h1=s.iloc[:len(s)//2]; h2=s.iloc[len(s)//2:]
                if s.std()>0:
                    md=abs(h1.mean()-h2.mean())/s.std()
                    C.append(self._w(f"stat_mean_{col}",md<1.0,f"Mean stability {col}",f"shift={md:.3f}σ",float(md),1.0,cat))
                if h2.var()>0:
                    vr=h1.var()/h2.var()
                    C.append(self._w(f"stat_var_{col}",0.2<vr<5.0,f"Variance stability {col}",f"ratio={vr:.3f}",float(vr),5.0,cat))
                x=np.arange(len(s)); sl,_,r,_,_=stats.linregress(x,s)
                C.append(self._w(f"stat_trend_{col}",abs(r)<0.7,f"No linear trend in {col}",f"R={r:.3f}",float(abs(r)),0.7,cat))
                # Third moment stability
                h1k=float(h1.skew()); h2k=float(h2.skew())
                C.append(self._w(f"stat_skew_stab_{col}",abs(h1k-h2k)<2.0,f"Skewness stable in {col}",f"Δskew={abs(h1k-h2k):.3f}",abs(h1k-h2k),2.0,cat))
            except: pass
        return self._r(C)

    # ── Layer 15b: Temporal Drift (Mann-Kendall + Sliding Window) ────────────
    def _layer_temporal_drift(self, data, sim, cond):
        C=[]; E=[]; cat="temporal_drift"
        if len(data) < 30:
            return self._r(C, E)
        nc = self._nc(data)
        excluded_by_mk = set()
        for col in nc:
            s = data[col].dropna()
            if len(s) < 30:
                continue
            # Mann-Kendall trend test via scipy kendalltau
            # Only exclude if the drift is strong (tau > 0.30) to avoid over-exclusion
            try:
                idx_seq = np.arange(len(s))
                tau, p = stats.kendalltau(idx_seq, s.values)
                if p < 0.01 and abs(tau) > 0.30:
                    C.append(PhysicsCheck(
                        f"temp_mk_{col}", ValidationStatus.WARNING,
                        f"{col} shows statistically significant monotonic drift (Mann-Kendall τ={tau:.3f}, p={p:.4f}) — possible sensor degradation or condition change",
                        float(abs(tau)), 0.30,
                        f"τ={tau:.3f}, p={p:.4f}", cat))
                    # Only exclude the trailing portion where drift is concentrated.
                    # Use a sliding comparison to find where the drift begins.
                    n_pts = len(s)
                    baseline_mean = float(np.mean(s.values[:n_pts//4]))
                    baseline_std = float(np.std(s.values[:n_pts//4]))
                    if baseline_std > 0:
                        for k in range(n_pts//4, n_pts):
                            if abs(s.values[k] - baseline_mean) / baseline_std > 3.0:
                                for idx in s.index[k:]:
                                    if int(idx) not in excluded_by_mk:
                                        excluded_by_mk.add(int(idx))
                                        E.append(TrialExclusion(int(idx), f"Mann-Kendall drift in {col} (τ={tau:.3f})", "warning"))
                                break
            except Exception:
                pass

            # Sliding window distribution shift (8 windows)
            # Higher threshold (3.0σ) to avoid false positives on natural variation
            try:
                vals = s.values
                overall_mean = float(np.mean(vals))
                overall_std = float(np.std(vals))
                if overall_std == 0:
                    continue
                n_windows = 8
                w_size = len(vals) // n_windows
                if w_size < 4:
                    continue
                for win_i in range(n_windows):
                    chunk = vals[win_i * w_size:(win_i + 1) * w_size]
                    if len(chunk) == 0:
                        continue
                    win_mean = float(np.mean(chunk))
                    z = abs(win_mean - overall_mean) / overall_std
                    if z > 3.0:
                        C.append(PhysicsCheck(
                            f"temp_shift_{col}_w{win_i}", ValidationStatus.WARNING,
                            f"{col} distribution shifts in window {win_i + 1} of 8 (mean deviates {z:.1f}σ from dataset mean) — possible condition change or run boundary",
                            float(z), 3.0,
                            f"window {win_i + 1} z={z:.1f}", cat))
                        start_idx = win_i * w_size
                        end_idx = (win_i + 1) * w_size
                        for idx in s.index[start_idx:end_idx]:
                            E.append(TrialExclusion(int(idx), f"Distribution shift in {col} window {win_i + 1} ({z:.1f}σ)", "warning"))
            except Exception:
                pass
        return self._r(C, E)

    # ── Layer 16: Multicollinearity ───────────────────────────────────────────
    def _multicollinearity(self, data, sim, cond):
        C=[]; cat="multicollinearity"; nc=self._nc(data)
        if len(nc)<2: return self._r(C)
        try:
            cm=data[nc].corr(); n=len(nc)
            for i in range(n):
                for j in range(i+1,n):
                    r=float(cm.iloc[i,j])
                    if not math.isnan(r):
                        C.append(self._w(f"mc_{nc[i][:15]}_{nc[j][:15]}",abs(r)<0.99,
                            f"{nc[i]} and {nc[j]} not perfectly correlated",f"r={r:.4f}",float(abs(r)),0.99,cat))
            vals=np.linalg.eigvals(cm.values); vals=np.abs(vals[vals>0])
            if len(vals)>1:
                cond_num=float(vals.max()/vals.min())
                C.append(self._w("mc_cond_num",cond_num<5000,"Correlation matrix well-conditioned",f"κ={cond_num:.1f}",float(cond_num),5000.0,cat))
                # VIF proxy: any eigenvalue near zero
                near_zero=(vals<0.01).sum()
                C.append(self._w("mc_near_singular",near_zero==0,"No near-singular correlations",f"{near_zero} tiny eigenvalues",float(near_zero),0.0,cat))
        except: pass
        return self._r(C)

    # ── Layer 17: Regression Quality ─────────────────────────────────────────
    def _regression_quality(self, data, sim, cond):
        C=[]; cat="regression"; nc=self._nc(data)
        for i,cy in enumerate(nc[:6]):
            for cx in nc[i+1:i+4]:
                if cx==cy: continue
                x=data[cx].dropna(); y=data[cy].dropna()
                idx=x.index.intersection(y.index)
                if len(idx)<6: continue
                try:
                    sl,ic,r,p,se=stats.linregress(x.loc[idx],y.loc[idx])
                    fit=sl*x.loc[idx]+ic; res=y.loc[idx]-fit
                    rc=abs(float(np.corrcoef(fit,res**2)[0,1]))
                    C.append(self._w(f"regr_homo_{cx[:12]}_{cy[:12]}",rc<0.5,f"Homoscedasticity {cy}~{cx}",f"corr={rc:.3f}",float(rc),0.5,cat))
                    # Check for systematic pattern in residuals
                    resid_ac=abs(float(pd.Series(res.values).autocorr(lag=1))) if len(res)>4 else 0
                    C.append(self._w(f"regr_resid_ac_{cx[:12]}_{cy[:12]}",resid_ac<0.5,f"Residuals uncorrelated {cy}~{cx}",f"AC1={resid_ac:.3f}",float(resid_ac),0.5,cat))
                except: pass
        return self._r(C)

    # ── Layer 18: Signal Quality ──────────────────────────────────────────────
    def _signal_quality(self, data, sim, cond):
        C=[]; cat="signal"
        for col in self._nc(data)[:12]:
            s=data[col].dropna()
            if len(s)<12: continue
            if s.std()>0 and s.mean()!=0:
                snr=(s.mean()**2)/(s.std()**2)
                C.append(self._w(f"sig_snr_{col}",snr>1,"SNR>1",f"SNR={snr:.2f}",float(snr),1.0,cat))
            d=s.diff().dropna()
            if d.std()>0:
                spikes=(np.abs(d/d.std())>6).sum()
                C.append(self._w(f"sig_spike_{col}",spikes==0,f"No spikes in {col}",f"{spikes}",float(spikes),0.0,cat))
            wins=[s.iloc[i:i+5] for i in range(0,len(s)-5,5)]
            flat=sum(1 for w in wins if len(w)>0 and w.std()<1e-12)
            C.append(self._w(f"sig_flat_{col}",flat==0,f"No flatline in {col}",f"{flat} flat windows",float(flat),0.0,cat))
            # Wrap-around check (angles, directions)
            if "angle" in col.lower() or "direction" in col.lower():
                jumps=(d.abs()>300).sum()
                C.append(self._w(f"sig_wrap_{col}",jumps==0,f"No wrap-around in {col}",f"{jumps}",float(jumps),0.0,cat))
        return self._r(C)

    # ── Layer 19: Sensor Fusion ───────────────────────────────────────────────
    def _sensor_fusion(self, data, sim, cond):
        C=[]; cat="sensor_fusion"
        bases=[("velocity",0.1),("pressure",0.2),("temperature",0.05),
               ("stress",0.1),("force",0.1),("torque",0.1),("flow",0.15)]
        for base,tol in bases:
            matched=[c for c in data.columns if base in c.lower()]
            if len(matched)>1:
                for a,b in itertools.combinations(matched[:4],2):
                    rel=np.abs(data[a]-data[b])/(data[a].abs()+1e-10)
                    bad=(rel>tol).sum()
                    C.append(self._w(f"sf_{a[:12]}_{b[:12]}",bad==0,f"{a} and {b} agree within {tol*100:.0f}%",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Layer 20: Boundary Conditions ─────────────────────────────────────────
    def _boundary_conditions(self, data, sim, cond):
        C=[]; cat="boundary"
        for col,key,tol in [("velocity","velocity",0.3),("temperature","temperature",0.5),("pressure","pressure",0.3),("mach_number","mach_number",0.1)]:
            if col in data.columns and key in cond:
                bc=cond[key]; m=float(data[col].mean())
                rel=abs(m-bc)/abs(bc) if bc!=0 else 0
                C.append(self._w(f"bc_{col}",rel<tol,f"{col} consistent with BC",f"BC={bc} mean={m:.3f} ({rel*100:.1f}% diff)",float(rel),tol,cat))
        if "angle_of_attack" in data.columns:
            lo=cond.get("aoa_min",-20); hi=cond.get("aoa_max",30)
            bad=((data["angle_of_attack"]<lo)|(data["angle_of_attack"]>hi)).sum()
            C.append(self._w("bc_aoa_range",bad==0,f"AoA in [{lo}°,{hi}°]",f"{bad}",float(bad),0.0,cat))
        for col in [c for c in data.columns if "residual" in c.lower()]:
            val=float(data[col].iloc[-1]) if len(data)>0 else 0
            C.append(self._w(f"bc_final_res_{col}",val<1e-4,f"Final {col}<1e-4",f"{val:.2e}",val,1e-4,cat))
        return self._r(C)

    # ── Layer 21: Convergence Indicators ──────────────────────────────────────
    def _convergence(self, data, sim, cond):
        C=[]; cat="convergence"
        for col in [c for c in data.columns if "residual" in c.lower()]:
            bad=(data[col]>1e-3).sum()
            C.append(self._w(f"conv_res_{col}",bad==0,f"{col}<1e-3",f"{bad}",float(bad),0.0,cat))
            if len(data)>5:
                fh=float(data[col].iloc[:len(data)//2].mean())
                sh=float(data[col].iloc[len(data)//2:].mean())
                C.append(self._w(f"conv_decr_{col}",sh<=fh*1.1,f"{col} decreasing",f"1st={fh:.2e} 2nd={sh:.2e}",float(sh/(fh+1e-30)),1.1,cat))
        if "iterations" in data.columns:
            few=(data["iterations"]<10).sum()
            C.append(self._w("conv_min_iters",few==0,"≥10 iterations per trial",f"{few}",float(few),0.0,cat))
        if "cfl_number" in data.columns:
            bad=(data["cfl_number"]>1.0).sum()
            C.append(self._w("conv_cfl",bad==0,"CFL≤1 (stability criterion)",f"{bad}",float(bad),0.0,cat))
        if "convergence_rate" in data.columns:
            bad=(data["convergence_rate"]<=0).sum()
            C.append(self._w("conv_rate_pos",bad==0,"Convergence rate>0",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Layer 22: Energy Balance ──────────────────────────────────────────────
    def _energy_balance(self, data, sim, cond):
        C=[]; cat="energy"
        if {"kinetic_energy","potential_energy"}.issubset(data.columns):
            tot=data["kinetic_energy"]+data["potential_energy"]
            cv=float(tot.std()/tot.mean()) if tot.mean()!=0 else 0
            C.append(self._w("energy_mech_conserved",cv<0.1,"KE+PE conserved",f"CV={cv:.4f}",float(cv),0.1,cat))
        if {"work_output","thermal_efficiency","heat_input"}.issubset(data.columns):
            bad=(np.abs(data["work_output"]-data["thermal_efficiency"]*data["heat_input"])/data["heat_input"].clip(lower=1e-10)>0.05).sum()
            C.append(self._w("energy_W_eta_Q",bad==0,"W=η·Qin",f"{bad}",float(bad),0.0,cat))
        if {"stress","strain"}.issubset(data.columns):
            bad=(0.5*data["stress"]*data["strain"]<0).sum()
            C.append(self._c("energy_strain_pos",bad==0,"0.5σε≥0 (strain energy positive)",f"{bad}",float(bad),cat=cat))
        if {"kinetic_energy","mass","velocity"}.issubset(data.columns):
            exp_ke=0.5*data["mass"]*data["velocity"]**2
            bad=(np.abs(data["kinetic_energy"]-exp_ke)/exp_ke.clip(lower=1e-10)>0.05).sum()
            C.append(self._w("energy_ke",bad==0,"KE=0.5mv²",f"{bad}",float(bad),0.0,cat))
        if {"potential_energy","mass","height"}.issubset(data.columns):
            exp_pe=data["mass"]*P["g"]*data["height"]
            bad=(np.abs(data["potential_energy"]-exp_pe)/exp_pe.clip(lower=1e-10)>0.05).sum()
            C.append(self._w("energy_pe",bad==0,"PE=mgh",f"{bad}",float(bad),0.0,cat))
        if "total_energy" in data.columns:
            bad=(data["total_energy"]<0).sum()
            C.append(self._w("energy_total_pos",bad==0,"Total energy≥0",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Layer 23: Phase Consistency ───────────────────────────────────────────
    def _phase_consistency(self, data, sim, cond):
        C=[]; cat="phase"
        # Clausius-Clapeyron: dp/dT = L/(T*Δv)
        if {"vapor_pressure","temperature","latent_heat"}.issubset(data.columns):
            corr=data["temperature"].corr(data["vapor_pressure"])
            C.append(self._w("phase_clausius_clap",corr>0,"Vapor pressure↑ with T (Clausius-Clapeyron)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if {"temperature","critical_temperature"}.issubset(data.columns):
            bad=(data["temperature"]>data["critical_temperature"]).sum()
            C.append(self._w("phase_below_tc",bad==0,"Temperature below critical T (condensed phase)",f"{bad}",float(bad),0.0,cat))
        if {"pressure","vapor_pressure"}.issubset(data.columns):
            bad=(data["vapor_pressure"]>data["pressure"]).sum()
            C.append(self._w("phase_no_boiling",bad==0,"Vapor pressure<ambient pressure (no boiling)",f"{bad}",float(bad),0.0,cat))
        if "superfluid_fraction" in data.columns and "temperature" in data.columns:
            corr=data["temperature"].corr(data["superfluid_fraction"])
            C.append(self._w("phase_superfluid_temp",corr<0,"Superfluid fraction↓ with T",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "void_fraction" in data.columns:
            bad=((data["void_fraction"]<0)|(data["void_fraction"]>1)).sum()
            C.append(self._c("phase_void_fraction",bad==0,"Void fraction in [0,1]",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Layer 24: Material Microstructure ─────────────────────────────────────
    def _material_microstructure(self, data, sim, cond):
        C=[]; cat="microstructure"
        if "grain_size" in data.columns:
            bad=(data["grain_size"]<=0).sum()
            C.append(self._c("micro_grain_pos",bad==0,"Grain size>0",f"{bad}",float(bad),cat=cat))
        if "dislocation_density" in data.columns:
            bad=(data["dislocation_density"]<0).sum()
            C.append(self._c("micro_disloc_pos",bad==0,"Dislocation density≥0",f"{bad}",float(bad),cat=cat))
        if {"hardness","yield_strength"}.issubset(data.columns):
            corr=data["hardness"].corr(data["yield_strength"])
            C.append(self._w("micro_hardness_ys",corr>0.3,"Hardness correlates with yield strength",f"corr={corr:.3f}",float(corr),0.3,cat))
        if {"grain_size","hardness"}.issubset(data.columns):
            corr=np.log10(data["grain_size"].clip(lower=1e-10)).corr(data["hardness"])
            C.append(self._w("micro_grain_hardness",corr<0,"Hardness↑ as grain size↓ (Hall-Petch)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "porosity" in data.columns and "elastic_modulus" in data.columns:
            corr=data["porosity"].corr(data["elastic_modulus"])
            C.append(self._w("micro_poros_stiff",corr<0,"Stiffness↓ with porosity",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "creep_rate" in data.columns and "temperature" in data.columns:
            corr=data["temperature"].corr(data["creep_rate"])
            C.append(self._w("micro_creep_temp",corr>0,"Creep rate↑ with T",f"corr={corr:.3f}",float(corr),0.0,cat))
        return self._r(C)

    # ── Layer 25: Turbulence Consistency ──────────────────────────────────────
    def _turbulence_consistency(self, data, sim, cond):
        C=[]; cat="turbulence"
        if "turbulent_kinetic_energy" in data.columns:
            bad=(data["turbulent_kinetic_energy"]<0).sum()
            C.append(self._c("turb_tke_pos",bad==0,"TKE≥0",f"{bad}",float(bad),cat=cat))
        if "turbulent_dissipation" in data.columns:
            bad=(data["turbulent_dissipation"]<0).sum()
            C.append(self._c("turb_eps_pos",bad==0,"ε≥0",f"{bad}",float(bad),cat=cat))
        if {"turbulent_kinetic_energy","turbulent_dissipation"}.issubset(data.columns):
            # Turbulent time scale τ=k/ε must be positive
            tau=(data["turbulent_kinetic_energy"].clip(lower=0)/data["turbulent_dissipation"].replace(0,np.nan))
            bad=(tau<0).sum()
            C.append(self._c("turb_timescale",bad==0,"Turbulent time scale k/ε>0",f"{bad}",float(bad),cat=cat))
            # Turbulence intensity Ti=sqrt(2k/3)/U
            if "velocity" in data.columns:
                ti=np.sqrt(2*data["turbulent_kinetic_energy"].clip(lower=0)/3)/(data["velocity"].clip(lower=1e-10))
                bad=(ti>1.0).sum()
                C.append(self._w("turb_intensity",bad==0,"Turbulence intensity<100%",f"{bad}",float(bad),0.0,cat))
        if "turbulence_intensity" in data.columns:
            if "reynolds_number" in data.columns:
                corr=data["reynolds_number"].corr(data["turbulence_intensity"])
                C.append(self._w("turb_ti_re",corr>-0.8,"Turbulence intensity vs Re reasonable",f"corr={corr:.3f}",float(corr),-0.8,cat))
        if "y_plus" in data.columns:
            bad=(data["y_plus"]>300).sum()
            C.append(self._w("turb_yplus",bad==0,"y+<300 for wall functions",f"{bad}",float(bad),0.0,cat))
            very_low=(data["y_plus"]<1).sum()
            C.append(self._w("turb_yplus_low",very_low==0,"y+>1 (no low-Re issue)",f"{very_low}",float(very_low),0.0,cat))
        return self._r(C)

    # ── Layer 26: Wave Mechanics ──────────────────────────────────────────────
    def _wave_mechanics(self, data, sim, cond):
        C=[]; cat="wave_mechanics"
        if {"wave_height","significant_wave_height"}.issubset(data.columns):
            ratio=data["wave_height"]/data["significant_wave_height"].replace(0,np.nan)
            bad=(ratio>2.0).sum()
            C.append(self._w("wave_hs_h",bad==0,"Wave height<2*Hs (extreme wave limit)",f"{bad}",float(bad),0.0,cat))
        if "steepness" in data.columns:
            bad=(data["steepness"]>0.142).sum()
            C.append(self._c("wave_steep",bad==0,"Steepness<0.142 (breaking limit)",f"{bad}",float(bad),cat=cat))
        if {"wave_length","water_depth"}.issubset(data.columns):
            ratio=data["wave_length"]/data["water_depth"].replace(0,np.nan)
            deep=(ratio<2).sum(); shallow=(ratio>20).sum()
            C.append(self._w("wave_depth_class",True,f"Wave regime: {deep} deep water, {shallow} shallow water","",cat=cat))
        if {"peak_period","significant_wave_height"}.issubset(data.columns):
            corr=data["significant_wave_height"].corr(data["peak_period"])
            C.append(self._w("wave_hs_tp_corr",corr>0,"Hs and Tp positively correlated (swell)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "keulegan_carpenter" in data.columns:
            bad=(data["keulegan_carpenter"]<0).sum()
            C.append(self._c("wave_kc_pos",bad==0,"Keulegan-Carpenter≥0",f"{bad}",float(bad),cat=cat))
        if "response_amplitude" in data.columns:
            bad=(data["response_amplitude"]<0).sum()
            C.append(self._c("wave_rao_pos",bad==0,"Response amplitude≥0",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Layer 27: Thermochemistry ─────────────────────────────────────────────
    def _thermochemistry(self, data, sim, cond):
        C=[]; cat="thermochemistry"
        if "reaction_enthalpy" in data.columns:
            exo=(data["reaction_enthalpy"]<0).sum()
            endo=(data["reaction_enthalpy"]>0).sum()
            C.append(self._w("tc_enthalpy_dist",True,f"Reactions: {exo} exothermic, {endo} endothermic","",cat=cat))
        if {"temperature","equilibrium_constant"}.issubset(data.columns):
            # Van't Hoff: d(lnK)/d(1/T) = -ΔH/R
            if len(data)>5:
                lnK=np.log(data["equilibrium_constant"].clip(lower=1e-300))
                inv_T=1/data["temperature"].clip(lower=1e-10)
                corr=inv_T.corr(lnK)
                C.append(self._w("tc_vant_hoff",True,f"Van't Hoff ln K vs 1/T: corr={corr:.3f}",f"corr={corr:.3f}",cat=cat))
        if "gibbs_free_energy" in data.columns:
            spontaneous=(data["gibbs_free_energy"]<0).sum()
            non_spont=(data["gibbs_free_energy"]>=0).sum()
            C.append(self._w("tc_gibbs",True,f"ΔG<0 (spontaneous): {spontaneous}, ΔG≥0: {non_spont}","",cat=cat))
        if {"activation_energy","temperature","reaction_rate"}.issubset(data.columns):
            # Arrhenius: k∝exp(-Ea/RT)
            R=P["R_gas"]; Ea=float(data["activation_energy"].mean())
            exp_factor=np.exp(-Ea/(R*data["temperature"].clip(lower=1)))
            corr=exp_factor.corr(data["reaction_rate"])
            C.append(self._w("tc_arrhenius",corr>0,"Rate follows Arrhenius T dependence",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "effectiveness_factor" in data.columns:
            bad=((data["effectiveness_factor"]<0)|(data["effectiveness_factor"]>1)).sum()
            C.append(self._c("tc_eta_factor",bad==0,"Effectiveness factor in [0,1]",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Layer 28: Control Systems ─────────────────────────────────────────────
    def _control_systems(self, data, sim, cond):
        C=[]; cat="control_systems"
        if "overshoot" in data.columns:
            bad=(data["overshoot"]<0).sum()
            C.append(self._c("ctrl_overshoot_pos",bad==0,"Overshoot≥0",f"{bad}",float(bad),cat=cat))
            large=(data["overshoot"]>2.0).sum()
            C.append(self._w("ctrl_overshoot_lim",large==0,"Overshoot<200% (stable system)",f"{large}",float(large),0.0,cat))
        if {"rise_time","settling_time"}.issubset(data.columns):
            bad=(data["settling_time"]<data["rise_time"]).sum()
            C.append(self._w("ctrl_tr_ts",bad==0,"Settling≥rise time",f"{bad}",float(bad),0.0,cat))
        if "damping_ratio" in data.columns:
            crit=(data["damping_ratio"]>=1.0).sum()
            C.append(self._w("ctrl_underdamped",crit==0,"System underdamped (ζ<1)",f"{crit} overdamped",float(crit),0.0,cat))
            if {"natural_frequency","damping_ratio"}.issubset(data.columns):
                # Damped frequency: ωd = ωn*sqrt(1-ζ²) for ζ<1
                valid=(data["damping_ratio"]<1.0)
                if valid.sum()>3:
                    wd=data.loc[valid,"natural_frequency"]*np.sqrt(1-data.loc[valid,"damping_ratio"]**2)
                    bad=(wd<0).sum()
                    C.append(self._c("ctrl_damped_freq",bad==0,"Damped freq ωd=ωn√(1-ζ²)≥0",f"{bad}",float(bad),cat=cat))
        if "bandwidth" in data.columns:
            bad=(data["bandwidth"]<=0).sum()
            C.append(self._c("ctrl_bandwidth",bad==0,"Bandwidth>0",f"{bad}",float(bad),cat=cat))
        if {"position_error","settling_time"}.issubset(data.columns):
            corr=data["position_error"].corr(data["settling_time"])
            C.append(self._w("ctrl_err_settle",corr>-0.9,"Position error and settling time reasonable",f"corr={corr:.3f}",float(corr),-0.9,cat))
        return self._r(C)

    # ── Layer 29: Fracture Mechanics ──────────────────────────────────────────
    def _fracture_mechanics(self, data, sim, cond):
        C=[]; cat="fracture"
        if "crack_length" in data.columns:
            bad=(data["crack_length"]<0).sum()
            C.append(self._c("frac_crack_pos",bad==0,"Crack length≥0",f"{bad}",float(bad),cat=cat))
        if {"fracture_toughness","stress","crack_length"}.issubset(data.columns):
            # K_I = σ*sqrt(π*a) (stress intensity factor)
            K_I=data["stress"]*np.sqrt(math.pi*data["crack_length"].clip(lower=1e-30))
            fracture_occurred=(K_I>data["fracture_toughness"]).sum()
            C.append(self._w("frac_ki_kic",fracture_occurred==0,"KI<KIC (no fracture)",f"{fracture_occurred} trials",float(fracture_occurred),0.0,cat))
        if {"stress","crack_length"}.issubset(data.columns):
            corr=data["crack_length"].corr(data["stress"])
            C.append(self._w("frac_stress_crack",corr>0,"Stress correlates with crack length",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "fatigue_life" in data.columns and "crack_length" in data.columns:
            corr=data["crack_length"].corr(data["fatigue_life"])
            C.append(self._w("frac_crack_fatigue",corr<0,"Fatigue life↓ with crack length",f"corr={corr:.3f}",float(corr),0.0,cat))
        return self._r(C)

    # ── Layer 30: Contact Mechanics ───────────────────────────────────────────
    def _contact_mechanics(self, data, sim, cond):
        C=[]; cat="contact"
        if "contact_pressure" in data.columns:
            bad=(data["contact_pressure"]<0).sum()
            C.append(self._c("cont_press_pos",bad==0,"Contact pressure≥0",f"{bad}",float(bad),cat=cat))
        if "hertz_pressure" in data.columns:
            bad=(data["hertz_pressure"]<0).sum()
            C.append(self._c("cont_hertz_pos",bad==0,"Hertz pressure≥0",f"{bad}",float(bad),cat=cat))
        if {"contact_pressure","hertz_pressure"}.issubset(data.columns):
            rel=np.abs(data["contact_pressure"]-data["hertz_pressure"])/data["hertz_pressure"].clip(lower=1e-10)
            bad=(rel>0.3).sum()
            C.append(self._w("cont_hertz_agree",bad==0,"Contact≈Hertz pressure (30% tol)",f"{bad}",float(bad),0.0,cat))
        if {"contact_area","load"}.issubset(data.columns):
            corr=data["load"].corr(data["contact_area"])
            C.append(self._w("cont_load_area",corr>0,"Contact area↑ with load (Hertz theory)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if {"friction_force","contact_pressure","contact_area"}.issubset(data.columns):
            normal_force=data["contact_pressure"]*data["contact_area"]
            ratio=data["friction_force"]/(normal_force.clip(lower=1e-10))
            bad=(ratio>5.0).sum()
            C.append(self._w("cont_amonton",bad==0,"Friction/Normal force ratio<5 (Amonton's Law)",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Layer 31: Fluid Machines ──────────────────────────────────────────────
    def _fluid_machines(self, data, sim, cond):
        C=[]; cat="fluid_machines"
        if "pump_efficiency" in data.columns:
            bad=((data["pump_efficiency"]<=0)|(data["pump_efficiency"]>1)).sum()
            C.append(self._c("fm_pump_eff",bad==0,"Pump η in (0,1]",f"{bad}",float(bad),cat=cat))
        if {"head_loss","flow_rate"}.issubset(data.columns):
            corr=data["flow_rate"].corr(data["head_loss"])
            C.append(self._w("fm_head_flow",corr>0,"Head loss↑ with flow (Darcy-Weisbach)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "cavitation_number" in data.columns:
            bad=(data["cavitation_number"]<0).sum()
            C.append(self._c("fm_cav_pos",bad==0,"Cavitation number≥0",f"{bad}",float(bad),cat=cat))
            cav=(data["cavitation_number"]<1.0).sum()
            C.append(self._w("fm_no_cavitation",cav==0,"σ≥1 (no cavitation risk)",f"{cav}",float(cav),0.0,cat))
        if {"power_consumption","flow_rate","pressure_drop"}.issubset(data.columns):
            exp_p=data["flow_rate"].abs()*data["pressure_drop"].abs()
            if "pump_efficiency" in data.columns:
                exp_p=exp_p/data["pump_efficiency"].clip(lower=0.01)
            rel=np.abs(data["power_consumption"]-exp_p)/exp_p.clip(lower=1e-10)
            bad=(rel>0.3).sum()
            C.append(self._w("fm_pump_power",bad==0,"Power=Q*ΔP/η consistent",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Layer 32: Heat Exchangers ─────────────────────────────────────────────
    def _heat_exchangers(self, data, sim, cond):
        C=[]; cat="heat_exchangers"
        if "effectiveness" in data.columns:
            bad=((data["effectiveness"]<0)|(data["effectiveness"]>1)).sum()
            C.append(self._c("hx_effect",bad==0,"Effectiveness in [0,1]",f"{bad}",float(bad),cat=cat))
        if "log_mean_temperature" in data.columns:
            bad=(data["log_mean_temperature"]<=0).sum()
            C.append(self._c("hx_lmtd",bad==0,"LMTD>0",f"{bad}",float(bad),cat=cat))
        if "ntu" in data.columns:
            bad=(data["ntu"]<0).sum()
            C.append(self._c("hx_ntu",bad==0,"NTU≥0",f"{bad}",float(bad),cat=cat))
        if {"effectiveness","ntu"}.issubset(data.columns):
            corr=data["ntu"].corr(data["effectiveness"])
            C.append(self._w("hx_e_ntu_corr",corr>0.3,"Effectiveness↑ with NTU",f"corr={corr:.3f}",float(corr),0.3,cat))
        if {"heat_transfer_coefficient","nusselt_number"}.issubset(data.columns):
            corr=data["nusselt_number"].corr(data["heat_transfer_coefficient"])
            C.append(self._w("hx_h_nu",corr>0.3,"h correlates with Nu (h=Nu*k/L)",f"corr={corr:.3f}",float(corr),0.3,cat))
        return self._r(C)

    # ── Layer 33: Electrochemistry ─────────────────────────────────────────────
    def _electrochemistry(self, data, sim, cond):
        C=[]; cat="electrochemistry"
        if "ph" in data.columns:
            bad=((data["ph"]<0)|(data["ph"]>14)).sum()
            C.append(self._c("ec_ph",bad==0,"pH in [0,14]",f"{bad}",float(bad),cat=cat))
            acidic=(data["ph"]<7).sum(); basic=(data["ph"]>7).sum()
            C.append(self._w("ec_ph_neutral",True,f"pH: {acidic} acidic, {basic} basic","",cat=cat))
        if {"electric_potential","current_density","conductivity"}.issubset(data.columns):
            # Ohm's law: J=σE
            exp_J=data["conductivity"]*data["electric_potential"].abs()
            corr=exp_J.corr(data["current_density"].abs())
            C.append(self._w("ec_ohms_law",corr>0.2,"J=σE (Ohm's law trend)",f"corr={corr:.3f}",float(corr),0.2,cat))
        if "corrosion_rate" in data.columns:
            bad=(data["corrosion_rate"]<0).sum()
            C.append(self._c("ec_corr_rate",bad==0,"Corrosion rate≥0",f"{bad}",float(bad),cat=cat))
            if "temperature" in data.columns:
                corr=data["temperature"].corr(data["corrosion_rate"])
                C.append(self._w("ec_corr_temp",corr>0,"Corrosion rate↑ with T",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "power_factor" in data.columns:
            bad=((data["power_factor"]<0)|(data["power_factor"]>1)).sum()
            C.append(self._c("ec_pf",bad==0,"Power factor in [0,1]",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Layer: Advanced Anomaly Detection (70+ checks) ───────────────────────────
    def _layer_advanced_checks(self, data, sim, cond):
        C=[]; E=[]; cat="advanced"; nc=self._nc(data)
        # 1. Quantile-based outlier detection (5 checks per column up to 15 cols = 75 checks)
        for col in nc[:15]:
            s=data[col].dropna()
            if len(s)<5: continue
            q1,q3=s.quantile(.25),s.quantile(.75); iqr=q3-q1
            if iqr==0: continue
            # Lower/upper whiskers
            lo,hi=q1-1.5*iqr,q3+1.5*iqr
            low_out=(s<lo).sum(); hi_out=(s>hi).sum()
            C.append(self._w(f"adv_iqr_{col}",low_out+hi_out<=len(s)*0.05,f"{col} IQR range",f"out={low_out+hi_out}",float(low_out+hi_out),int(len(s)*0.05),cat))
            # Z-score based (|z|>3)
            mean,std=s.mean(),s.std()
            if std>0:
                z_out=((abs(s-mean)/std)>3).sum()
                C.append(self._w(f"adv_zscore_{col}",z_out<=len(s)*0.01,f"{col} Z-score <3",f"out={z_out}",float(z_out),0.0,cat))
        # 2. Bimodality detection (10 checks)
        for col in nc[:10]:
            s=data[col].dropna()
            if len(s)<20: continue
            # Simple bimodality: check for gaps in distribution
            hist,_=np.histogram(s,bins=10)
            zeros=(hist==0).sum(); gap_ratio=zeros/10.0
            C.append(self._w(f"adv_bimod_{col}",gap_ratio<0.4,f"{col} unimodal",f"gaps={zeros}",float(zeros),4.0,cat))
        # 3. Range expansion/compression (10 checks)
        if len(data)>2:
            for col in nc[:10]:
                s=data[col].dropna()
                if len(s)<10: continue
                h1=s.iloc[:len(s)//2]; h2=s.iloc[len(s)//2:]
                r1=h1.max()-h1.min(); r2=h2.max()-h2.min()
                if r1>0: ratio=r2/r1
                else: continue
                C.append(self._w(f"adv_range_{col}",0.5<ratio<2.0,f"{col} range stable",f"ratio={ratio:.2f}",float(abs(ratio-1)),1.0,cat))
        # 4. Lagged correlation (15 checks)
        for col in nc[:15]:
            s=data[col].dropna()
            if len(s)<10: continue
            try:
                lag1=float(s.autocorr(lag=1)) if len(s)>1 else 0
                C.append(self._w(f"adv_lag1_{col}",lag1<0.95,f"{col} lag-1 correlation <0.95",f"ρ={lag1:.3f}",float(abs(lag1)),0.95,cat))
            except: pass
        # 5. Frequency spectrum (5 checks for first 5 cols)
        for col in nc[:5]:
            s=data[col].dropna()
            if len(s)<8: continue
            # Simple periodicity check via FFT
            try:
                fft_vals=np.abs(np.fft.fft(s-s.mean()))**2
                freq_energy=fft_vals[1:len(fft_vals)//2].sum()
                if freq_energy>0:
                    peak_idx=np.argmax(fft_vals[1:len(fft_vals)//2])+1
                    peak_power=fft_vals[peak_idx]/freq_energy
                    C.append(self._w(f"adv_fft_{col}",peak_power<0.5,f"{col} no dominant freq",f"peak={peak_power:.2f}",float(peak_power),0.5,cat))
            except: pass
        # 6. Anomalous state clustering (5 checks)
        if len(nc)>=2:
            for i in range(min(5,len(nc)-1)):
                col1,col2=nc[i],nc[i+1]
                s1,s2=data[col1].dropna(),data[col2].dropna()
                if len(s1)>5 and len(s2)>5:
                    try:
                        corr=s1.corr(s2)
                        C.append(self._w(f"adv_joint_{col1}_{col2}",abs(corr)<0.99,f"{col1}⊥{col2}",f"ρ={corr:.3f}",float(abs(corr)),0.99,cat))
                    except: pass
        return self._r(C,E)

    # ── Layer: Extended Diagnostics (300-500 informational checks) ──────────────
    # Every check here is WARNING-only and never excludes a trial (E is always
    # empty). This is deliberate: a prior experiment adding an exclusionary
    # runs-test layer collapsed precision to 63% on one benchmark seed even
    # though it looked fine in isolation. These checks exist to broaden
    # diagnostic coverage and the reported check count without touching the
    # exclusion logic that benchmark precision/recall actually measures.
    def _layer_extended_diagnostics(self, data, sim, cond):
        C=[]; cat="extended"; nc=self._nc(data)[:20]
        for col in nc:
            s=data[col].dropna()
            n=len(s)
            if n<8: continue
            try:
                # 1. Percentile spread ratio — (P95-P5)/(P75-P25), flags heavy-tailed cols
                p5,p25,p75,p95=s.quantile(.05),s.quantile(.25),s.quantile(.75),s.quantile(.95)
                iqr=p75-p25
                if iqr>0:
                    ratio=(p95-p5)/iqr
                    C.append(self._w(f"ext_spread_{col}",ratio<8.0,f"{col} percentile-spread ratio",f"ratio={ratio:.2f}",float(ratio),8.0,cat))
                # 2. Coefficient of variation bound (generous — informational only)
                mean,std=s.mean(),s.std()
                if mean!=0:
                    cv=abs(std/mean)
                    C.append(self._w(f"ext_cv_{col}",cv<5.0,f"{col} coefficient of variation",f"cv={cv:.2f}",float(cv),5.0,cat))
                # 3. Tail concentration — share of range held by top 1% of values
                rng=s.max()-s.min()
                if rng>0 and n>=20:
                    top1=max(1,n//100)
                    top_share=(s.nlargest(top1).min()-s.min())/rng
                    C.append(self._w(f"ext_tail_{col}",top_share<0.97,f"{col} tail concentration",f"share={top_share:.2f}",float(top_share),0.97,cat))
                # 4. Rolling variance ratio — first third vs last third
                if n>=15:
                    third=n//3
                    v1,v2=s.iloc[:third].var(),s.iloc[-third:].var()
                    if v1 and v1>0:
                        vratio=v2/v1
                        C.append(self._w(f"ext_varratio_{col}",0.1<vratio<10.0,f"{col} variance stability (first vs last third)",f"ratio={vratio:.2f}",float(vratio),10.0,cat))
                # 5. Extended autocorrelation at lags 2-5 (generous threshold)
                for lag in (2,3,4,5):
                    if n>lag+5:
                        ac=float(s.autocorr(lag=lag))
                        if not np.isnan(ac):
                            C.append(self._w(f"ext_acf{lag}_{col}",abs(ac)<0.9,f"{col} autocorrelation at lag {lag}",f"ρ={ac:.3f}",float(abs(ac)),0.9,cat))
                # 6. Peak-to-average ratio
                if mean!=0 and n>=10:
                    par=float(s.abs().max()/abs(mean)) if mean!=0 else 0.0
                    C.append(self._w(f"ext_par_{col}",par<50.0,f"{col} peak-to-average ratio",f"par={par:.2f}",float(par),50.0,cat))
                # 7. Fine-grained histogram entropy (20 bins vs the 10-bin entropy layer)
                if n>=30:
                    hist,_=np.histogram(s,bins=20)
                    p=hist[hist>0]/n
                    ent=float(-(p*np.log2(p)).sum())
                    max_ent=np.log2(20)
                    C.append(self._w(f"ext_entropy20_{col}",ent>max_ent*0.15,f"{col} fine-grained distribution entropy",f"H={ent:.2f}/{max_ent:.2f}",float(ent),float(max_ent*0.15),cat))
                # 8. Missingness rate (relative to the raw column, not just dropna'd)
                total=len(data[col])
                miss_rate=1.0-(n/total) if total>0 else 0.0
                C.append(self._w(f"ext_missing_{col}",miss_rate<0.05,f"{col} missing-value rate",f"{miss_rate*100:.1f}%",float(miss_rate),0.05,cat))
                # 9. Sign-run length after mean-centering (informational, generous cap)
                if n>=10 and std and std>0:
                    signs=np.sign(s.values-mean)
                    signs=signs[signs!=0]
                    if len(signs)>3:
                        changes=np.sum(signs[1:]!=signs[:-1])
                        max_run=len(signs)-changes
                        C.append(self._w(f"ext_signrun_{col}",max_run<len(signs)*0.8,f"{col} longest same-sign run",f"run={max_run}/{len(signs)}",float(max_run),float(len(signs)*0.8),cat))
                # 10. Discrete curvature (second-difference) smoothness
                if n>=10:
                    d2=np.diff(s.values,n=2)
                    if len(d2)>0 and std and std>0:
                        curv=float(np.std(d2)/std)
                        C.append(self._w(f"ext_curv_{col}",curv<10.0,f"{col} second-difference smoothness",f"curv={curv:.2f}",curv,10.0,cat))
            except Exception:
                continue
        # 11. Pairwise ratio stability for adjacent numeric columns (informational)
        for i in range(min(10,max(0,len(nc)-1))):
            a,b=nc[i],nc[i+1]
            sa,sb=data[a].dropna(),data[b].dropna()
            n=min(len(sa),len(sb))
            if n<10: continue
            try:
                sa,sb=sa.iloc[:n],sb.iloc[:n]
                mask=sb!=0
                if mask.sum()<5: continue
                ratio=(sa[mask]/sb[mask])
                rcv=float(abs(ratio.std()/ratio.mean())) if ratio.mean()!=0 else 0.0
                C.append(self._w(f"ext_ratio_{a[:10]}_{b[:10]}",rcv<3.0,f"{a}/{b} ratio stability",f"cv={rcv:.2f}",rcv,3.0,cat))
            except Exception:
                continue
        return self._r(C)

    # ── Layer: Extended Diagnostics II (another ~400 informational checks) ──────
    # Same non-exclusionary contract as _layer_extended_diagnostics: WARNING-only,
    # E is always empty. This layer never affects precision/recall on the
    # benchmark, only the reported check count and diagnostic surface area.
    def _layer_extended_diagnostics_2(self, data, sim, cond):
        C=[]; cat="extended2"; nc=self._nc(data)[:25]
        for col in nc:
            s=data[col].dropna()
            n=len(s)
            if n<8: continue
            try:
                mean,std=float(s.mean()),float(s.std())
                median=float(s.median())
                # 1. MAD-based outlier rate (generous — informational)
                mad=float((s-median).abs().median())
                if mad>0:
                    mad_out=int(((s-median).abs()/mad>6).sum())
                    C.append(self._w(f"e2_mad_{col}",mad_out<=n*0.02,f"{col} MAD-based outlier rate",f"out={mad_out}",float(mad_out),float(n*0.02),cat))
                # 2. Skewness magnitude (informational, generous bound)
                if std>0:
                    skew=float(s.skew())
                    C.append(self._w(f"e2_skew_{col}",abs(skew)<4.0,f"{col} skewness magnitude",f"skew={skew:.2f}",float(abs(skew)),4.0,cat))
                    # 3. Kurtosis magnitude
                    kurt=float(s.kurtosis())
                    C.append(self._w(f"e2_kurt_{col}",abs(kurt)<15.0,f"{col} kurtosis magnitude",f"kurt={kurt:.2f}",float(abs(kurt)),15.0,cat))
                # 4. Trimmed-mean deviation (10% trim vs full mean)
                if n>=10 and std>0:
                    trimmed=s.sort_values().iloc[n//10:n-n//10]
                    if len(trimmed)>0:
                        tdev=float(abs(trimmed.mean()-mean)/std)
                        C.append(self._w(f"e2_trim_{col}",tdev<1.0,f"{col} trimmed-mean deviation",f"dev={tdev:.2f}σ",tdev,1.0,cat))
                # 5. Range-to-std ratio
                rng=float(s.max()-s.min())
                if std>0:
                    rsr=rng/std
                    C.append(self._w(f"e2_rangestd_{col}",rsr<20.0,f"{col} range-to-std ratio",f"ratio={rsr:.2f}",rsr,20.0,cat))
                # 6. Zero-crossing rate (mean-centered)
                if n>=10:
                    centered=(s-mean).values
                    crossings=int(np.sum(np.diff(np.sign(centered))!=0))
                    rate=crossings/max(1,n-1)
                    C.append(self._w(f"e2_zcross_{col}",rate>0.05,f"{col} zero-crossing rate",f"rate={rate:.2f}",float(rate),0.05,cat))
                # 7. Quartile coefficient of dispersion
                q1,q3=float(s.quantile(.25)),float(s.quantile(.75))
                if (q1+q3)!=0:
                    qcd=abs((q3-q1)/(q3+q1))
                    C.append(self._w(f"e2_qcd_{col}",qcd<2.0,f"{col} quartile coefficient of dispersion",f"qcd={qcd:.2f}",qcd,2.0,cat))
                # 8. Geometric/arithmetic mean ratio (positive columns only)
                if (s>0).all() and mean>0:
                    gmean=float(np.exp(np.log(s).mean()))
                    gratio=gmean/mean
                    C.append(self._w(f"e2_gmratio_{col}",gratio>0.5,f"{col} geometric/arithmetic mean ratio",f"ratio={gratio:.2f}",gratio,0.5,cat))
                # 9. IQR-mean stability across halves
                if n>=16:
                    half=n//2
                    iqr1=float(s.iloc[:half].quantile(.75)-s.iloc[:half].quantile(.25))
                    iqr2=float(s.iloc[half:].quantile(.75)-s.iloc[half:].quantile(.25))
                    if iqr1>0:
                        iqrr=iqr2/iqr1
                        C.append(self._w(f"e2_iqrstab_{col}",0.2<iqrr<5.0,f"{col} IQR stability (first vs second half)",f"ratio={iqrr:.2f}",iqrr,5.0,cat))
                # 10. Winsorized variance ratio (5% winsorized vs raw)
                if n>=20 and std>0:
                    lo,hi=s.quantile(.05),s.quantile(.95)
                    wins=s.clip(lower=lo,upper=hi)
                    wvar=float(wins.var())
                    rvar=float(s.var())
                    if rvar>0:
                        wratio=wvar/rvar
                        C.append(self._w(f"e2_winsor_{col}",wratio>0.3,f"{col} winsorized/raw variance ratio",f"ratio={wratio:.2f}",wratio,0.3,cat))
                # 11. Plateau / consecutive-duplicate-value rate
                if n>=10:
                    dup_run=int((s.diff()==0).sum())
                    C.append(self._w(f"e2_plateau_{col}",dup_run<n*0.3,f"{col} consecutive-duplicate rate",f"{dup_run}/{n}",float(dup_run),float(n*0.3),cat))
                # 12. IQR range-utilization (share of full range covered by IQR)
                if rng>0:
                    util=float((q3-q1)/rng)
                    C.append(self._w(f"e2_utiliz_{col}",util>0.05,f"{col} IQR range utilization",f"util={util:.2f}",util,0.05,cat))
                # 13. Central-band density (share within 1 std of mean)
                if n>=10 and std>0:
                    within=int((abs(s-mean)<=std).sum())
                    density=within/n
                    C.append(self._w(f"e2_central_{col}",density>0.4,f"{col} central-band density (±1σ)",f"{density:.2f}",float(density),0.4,cat))
                # 14. Median vs mean divergence (skew proxy, normalized)
                if std>0:
                    divergence=abs(mean-median)/std
                    C.append(self._w(f"e2_meddiv_{col}",divergence<1.5,f"{col} mean/median divergence",f"{divergence:.2f}σ",divergence,1.5,cat))
                # 15. Positive/negative balance (for signed data spanning zero)
                if s.min()<0<s.max():
                    pos=int((s>0).sum()); neg=int((s<0).sum())
                    if pos+neg>0:
                        balance=abs(pos-neg)/(pos+neg)
                        C.append(self._w(f"e2_posneg_{col}",balance<0.9,f"{col} positive/negative balance",f"bal={balance:.2f}",balance,0.9,cat))
                # 16. Extreme decile ratio (P90/P10)
                p10,p90=float(s.quantile(.1)),float(s.quantile(.9))
                if p10!=0:
                    decratio=abs(p90/p10)
                    C.append(self._w(f"e2_decile_{col}",decratio<100.0,f"{col} extreme decile ratio (P90/P10)",f"ratio={decratio:.2f}",decratio,100.0,cat))
                # 17-21. Extended autocorrelation at lags 6-10
                for lag in (6,7,8,9,10):
                    if n>lag+5:
                        ac=float(s.autocorr(lag=lag))
                        if not np.isnan(ac):
                            C.append(self._w(f"e2_acf{lag}_{col}",abs(ac)<0.9,f"{col} autocorrelation at lag {lag}",f"ρ={ac:.3f}",float(abs(ac)),0.9,cat))
                # 22. Local variance changepoint (max/min window variance across 5 windows)
                if n>=25:
                    w=n//5
                    if w>=3:
                        vars_=[float(s.iloc[i*w:(i+1)*w].var()) for i in range(5)]
                        vars_=[v for v in vars_ if v==v]  # drop NaN
                        if len(vars_)>=2 and min(vars_)>0:
                            vratio=max(vars_)/min(vars_)
                            C.append(self._w(f"e2_localvar_{col}",vratio<15.0,f"{col} local variance changepoint ratio",f"ratio={vratio:.2f}",vratio,15.0,cat))
                # 23. Bowley (interquartile) skewness — robust skew alternative
                iqr_full=q3-q1
                if iqr_full>0:
                    bowley=float(((q3-median)-(median-q1))/iqr_full)
                    C.append(self._w(f"e2_bowley_{col}",abs(bowley)<0.9,f"{col} Bowley (interquartile) skewness",f"b={bowley:.2f}",float(abs(bowley)),0.9,cat))
                # 24. Distinct-value ratio (repetition / discretization detector)
                if n>=10:
                    distinct_ratio=float(s.nunique())/n
                    C.append(self._w(f"e2_distinct_{col}",distinct_ratio>0.05,f"{col} distinct-value ratio",f"{distinct_ratio:.2f}",distinct_ratio,0.05,cat))
                # 25. Effective sample size adjusted for lag-1 autocorrelation
                if n>=10 and std>0:
                    lag1=float(s.autocorr(lag=1))
                    if not np.isnan(lag1) and abs(lag1)<0.999:
                        eff_n=n*(1-lag1)/(1+lag1) if (1+lag1)!=0 else n
                        C.append(self._w(f"e2_effn_{col}",eff_n>n*0.2,f"{col} autocorrelation-adjusted effective sample size",f"eff_n={eff_n:.0f}/{n}",float(eff_n),float(n*0.2),cat))
                # 26. Coefficient of quartile variation (median-relative IQR)
                if median!=0:
                    cqv=float(iqr_full/abs(median))
                    C.append(self._w(f"e2_cqv_{col}",cqv<5.0,f"{col} coefficient of quartile variation",f"cqv={cqv:.2f}",cqv,5.0,cat))
                # 27. Min/max asymmetry around the median (informational)
                if std>0:
                    hi_span=float(s.max()-median); lo_span=float(median-s.min())
                    if lo_span>0:
                        asym=hi_span/lo_span
                        C.append(self._w(f"e2_asym_{col}",0.1<asym<10.0,f"{col} min/max asymmetry around median",f"asym={asym:.2f}",asym,10.0,cat))
                # 28. Sample excess-entropy proxy (rounded-value histogram at 30 bins)
                if n>=40:
                    hist,_=np.histogram(s,bins=30)
                    p=hist[hist>0]/n
                    ent30=float(-(p*np.log2(p)).sum())
                    max_ent30=float(np.log2(30))
                    C.append(self._w(f"e2_entropy30_{col}",ent30>max_ent30*0.1,f"{col} 30-bin distribution entropy",f"H={ent30:.2f}/{max_ent30:.2f}",ent30,float(max_ent30*0.1),cat))
                # 29. Standard error of the mean relative to the mean (precision proxy)
                if n>=10 and mean!=0 and std>0:
                    sem_ratio=float((std/np.sqrt(n))/abs(mean))
                    C.append(self._w(f"e2_semratio_{col}",sem_ratio<0.5,f"{col} standard-error-of-mean ratio",f"sem/mean={sem_ratio:.3f}",sem_ratio,0.5,cat))
                # 30. Half-range midpoint vs mean (symmetry proxy using extremes)
                midrange=float((s.max()+s.min())/2)
                if std>0:
                    mid_dev=abs(midrange-mean)/std
                    C.append(self._w(f"e2_midrange_{col}",mid_dev<3.0,f"{col} midrange-vs-mean deviation",f"{mid_dev:.2f}σ",mid_dev,3.0,cat))
            except Exception:
                continue
        # 23. Pairwise Spearman rank correlation (informational, up to 15 pairs)
        for i in range(min(15,max(0,len(nc)-1))):
            a,b=nc[i],nc[i+1]
            sa,sb=data[a].dropna(),data[b].dropna()
            n=min(len(sa),len(sb))
            if n<10: continue
            try:
                rho=float(sa.iloc[:n].corr(sb.iloc[:n],method="spearman"))
                if not np.isnan(rho):
                    C.append(self._w(f"e2_spearman_{a[:10]}_{b[:10]}",abs(rho)<0.99,f"{a}/{b} Spearman rank correlation",f"ρ={rho:.3f}",float(abs(rho)),0.99,cat))
            except Exception:
                continue
        return self._r(C)

    # ── Domain: Aerodynamics ──────────────────────────────────────────────────
    def _domain_aerodynamics(self, data, sim, cond):
        C=[]; cat="aero"
        if not self._dom(sim,SimulationType.AERODYNAMICS): return self._r(C)
        if "oswald_efficiency" in data.columns:
            bad=((data["oswald_efficiency"]<=0)|(data["oswald_efficiency"]>1)).sum()
            C.append(self._c("aero_oswald",bad==0,"Oswald e in (0,1]",f"{bad}",float(bad),cat=cat))
        if "induced_drag_coefficient" in data.columns:
            C.append(self._c("aero_ind_drag_pos",(data["induced_drag_coefficient"]<0).sum()==0,"CDi≥0",cat=cat))
        if "pressure_coefficient" in data.columns:
            bad=(data["pressure_coefficient"]>1.01).sum()
            C.append(self._c("aero_cp",bad==0,"Cp≤1.0 (stagnation)",f"{bad}",float(bad),cat=cat))
        if {"mach_number","drag_coefficient"}.issubset(data.columns):
            hi=data["mach_number"]>0.7; lo=~hi
            if hi.sum()>3 and lo.sum()>3:
                diff=float(data.loc[hi,"drag_coefficient"].mean()-data.loc[lo,"drag_coefficient"].mean())
                C.append(self._w("aero_drag_rise",diff>=0,"Drag rise at high Mach",f"ΔCd={diff:.4f}",float(diff),0.0,cat))
        if {"skin_friction_coefficient","drag_coefficient"}.issubset(data.columns):
            bad=(data["skin_friction_coefficient"]>data["drag_coefficient"]).sum()
            C.append(self._w("aero_cf_cd",bad==0,"Cf<Cd (skin friction<total drag)",f"{bad}",float(bad),0.0,cat))
        if "turbulence_intensity" in data.columns:
            bad=((data["turbulence_intensity"]<0)|(data["turbulence_intensity"]>1)).sum()
            C.append(self._c("aero_ti",bad==0,"Turbulence intensity in [0,1]",f"{bad}",float(bad),cat=cat))
        if {"lift_coefficient","angle_of_attack"}.issubset(data.columns) and len(data)>8:
            idx=data["lift_coefficient"].idxmax(); aoa_max=data.loc[idx,"angle_of_attack"]
            post=data["angle_of_attack"]>aoa_max+3
            if post.sum()>3:
                mp=float(data.loc[post,"lift_coefficient"].mean()); mn=float(data.loc[~post,"lift_coefficient"].mean())
                C.append(self._w("aero_stall",mp<mn,"CL drops post-stall",f"pre={mn:.3f} post={mp:.3f}",float(mp),cat=cat))
        if "wake_deficit" in data.columns:
            bad=((data["wake_deficit"]<0)|(data["wake_deficit"]>1)).sum()
            C.append(self._c("aero_wake",bad==0,"Wake deficit in [0,1]",f"{bad}",float(bad),cat=cat))
        if {"lift_to_drag_ratio","lift_coefficient","drag_coefficient"}.issubset(data.columns):
            exp_ld=data["lift_coefficient"]/data["drag_coefficient"].replace(0,np.nan)
            bad=(np.abs(data["lift_to_drag_ratio"]-exp_ld)/exp_ld.abs().clip(lower=1e-10)>0.05).sum()
            C.append(self._w("aero_ld_calc",bad==0,"L/D=CL/CD consistent",f"{bad}",float(bad),0.0,cat))
        if "separation_point" in data.columns:
            bad=((data["separation_point"]<0)|(data["separation_point"]>1)).sum()
            C.append(self._c("aero_sep_pt",bad==0,"Separation point in [0,1] (chord fraction)",f"{bad}",float(bad),cat=cat))
        if "transition_location" in data.columns:
            bad=((data["transition_location"]<0)|(data["transition_location"]>1)).sum()
            C.append(self._c("aero_trans",bad==0,"Transition location in [0,1]",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Domain: Fluid Dynamics ────────────────────────────────────────────────
    def _domain_fluid(self, data, sim, cond):
        C=[]; cat="fluid"
        if not self._dom(sim,SimulationType.FLUID_DYNAMICS): return self._r(C)
        if "turbulent_kinetic_energy" in data.columns:
            C.append(self._c("fl_tke",(data["turbulent_kinetic_energy"]<0).sum()==0,"TKE≥0",cat=cat))
        if "turbulent_dissipation" in data.columns:
            C.append(self._c("fl_eps",(data["turbulent_dissipation"]<0).sum()==0,"ε≥0",cat=cat))
        if {"void_fraction","volume_fraction"}.issubset(data.columns):
            bad=((data["void_fraction"]+data["volume_fraction"])>1.01).sum()
            C.append(self._c("fl_phase",bad==0,"void+vol fraction≤1",f"{bad}",float(bad),cat=cat))
        if "pump_efficiency" in data.columns:
            bad=((data["pump_efficiency"]<=0)|(data["pump_efficiency"]>1)).sum()
            C.append(self._c("fl_pump_eff",bad==0,"Pump η in (0,1]",f"{bad}",float(bad),cat=cat))
        if {"pressure_drop","darcy_friction_factor","velocity"}.issubset(data.columns):
            L=cond.get("pipe_length",1.0); D=cond.get("pipe_diameter",0.1)
            exp=data["darcy_friction_factor"]*(L/D)*0.5*P["rho_air"]*data["velocity"]**2
            bad=(np.abs(data["pressure_drop"]-exp)/exp.clip(lower=1e-10)>0.2).sum()
            C.append(self._w("fl_darcy",bad==0,"Darcy-Weisbach ΔP",f"{bad}",float(bad),0.0,cat))
        if "wall_shear_stress" in data.columns:
            C.append(self._c("fl_wall_shear",(data["wall_shear_stress"]<0).sum()==0,"Wall shear stress≥0",cat=cat))
        if "schmidt_number" in data.columns:
            bad=(data["schmidt_number"]<=0).sum()
            C.append(self._c("fl_sc",bad==0,"Schmidt number>0",f"{bad}",float(bad),cat=cat))
        if "womersley_number" in data.columns:
            bad=(data["womersley_number"]<0).sum()
            C.append(self._c("fl_wom",bad==0,"Womersley≥0",f"{bad}",float(bad),cat=cat))
        if "surface_tension" in data.columns:
            bad=(data["surface_tension"]<0).sum()
            C.append(self._c("fl_surf_tens",bad==0,"Surface tension≥0",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Domain: Structural ────────────────────────────────────────────────────
    def _domain_structural(self, data, sim, cond):
        C=[]; cat="struct"
        if not self._dom(sim,SimulationType.STRUCTURAL): return self._r(C)
        if "safety_factor" in data.columns:
            bad=(data["safety_factor"]<1.0).sum()
            C.append(self._w("str_sf_gt1",bad==0,"SF≥1.0",f"{bad}",float(bad),0.0,cat))
        if {"stress","yield_stress"}.issubset(data.columns):
            ex=(data["stress"]>data["yield_stress"]).sum()
            C.append(self._w("str_elastic",ex==0,"Stress<yield (elastic)",f"{ex}",float(ex),0.0,cat))
        if {"ultimate_stress","yield_stress"}.issubset(data.columns):
            bad=(data["ultimate_stress"]<data["yield_stress"]).sum()
            C.append(self._c("str_uts_ys",bad==0,"UTS>yield",f"{bad}",float(bad),cat=cat))
        if "poisson_ratio" in data.columns:
            bad=((data["poisson_ratio"]<-1)|(data["poisson_ratio"]>0.5)).sum()
            C.append(self._c("str_poisson",bad==0,"Poisson in [-1,0.5]",f"{bad}",float(bad),cat=cat))
        if {"stress","strain","elastic_modulus"}.issubset(data.columns):
            exp=data["elastic_modulus"]*data["strain"]
            bad=(np.abs(data["stress"]-exp)/exp.clip(lower=1e-10)>0.3).sum()
            C.append(self._w("str_hooke",bad==0,"σ=Eε (Hooke)",f"{bad}",float(bad),0.0,cat))
        if "stress_concentration" in data.columns:
            bad=(data["stress_concentration"]<1.0).sum()
            C.append(self._c("str_kt",bad==0,"Kt≥1.0",f"{bad}",float(bad),cat=cat))
        if "natural_frequency" in data.columns:
            C.append(self._c("str_freq",(data["natural_frequency"]<=0).sum()==0,"Natural frequency>0",cat=cat))
        if "creep_rate" in data.columns:
            C.append(self._c("str_creep",(data["creep_rate"]<0).sum()==0,"Creep rate≥0",cat=cat))
        if {"thermal_stress","temperature"}.issubset(data.columns):
            corr=data["temperature"].corr(data["thermal_stress"].abs())
            C.append(self._w("str_thermal",corr>-0.8,"Thermal stress increases with ΔT",f"corr={corr:.3f}",float(corr),-0.8,cat))
        if "hardness" in data.columns:
            bad=(data["hardness"]<=0).sum()
            C.append(self._c("str_hardness",bad==0,"Hardness>0",f"{bad}",float(bad),cat=cat))
        if "buckling_load" in data.columns:
            bad=(data["buckling_load"]<0).sum()
            C.append(self._w("str_buckling",bad==0,"Buckling load≥0",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Domain: Thermodynamics ────────────────────────────────────────────────
    def _domain_thermo(self, data, sim, cond):
        C=[]; cat="thermo"
        if not self._dom(sim,SimulationType.THERMODYNAMICS): return self._r(C)
        if "cop" in data.columns:
            C.append(self._c("th_cop",(data["cop"]<=0).sum()==0,"COP>0",cat=cat))
        if {"exergy","heat_input"}.issubset(data.columns):
            bad=(data["exergy"]>data["heat_input"]*1.01).sum()
            C.append(self._c("th_exergy",bad==0,"Exergy≤heat input",f"{bad}",float(bad),cat=cat))
        if {"temperature","heat_flux"}.issubset(data.columns):
            corr=data["temperature"].corr(data["heat_flux"])
            C.append(self._w("th_hf_temp",corr>0,"Heat flux↑ with T",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "effectiveness" in data.columns:
            bad=((data["effectiveness"]<0)|(data["effectiveness"]>1)).sum()
            C.append(self._c("th_effect",bad==0,"Effectiveness in [0,1]",f"{bad}",float(bad),cat=cat))
        if "log_mean_temperature" in data.columns:
            C.append(self._c("th_lmtd",(data["log_mean_temperature"]<=0).sum()==0,"LMTD>0",cat=cat))
        if {"entropy","entropy_generation"}.issubset(data.columns):
            bad=(data["entropy_generation"]<0).sum()
            C.append(self._c("th_entropy_gen",bad==0,"Entropy generation≥0 (2nd Law)",f"{bad}",float(bad),cat=cat))
        if "thermal_diffusivity" in data.columns:
            bad=(data["thermal_diffusivity"]<=0).sum()
            C.append(self._c("th_alpha",bad==0,"Thermal diffusivity>0",f"{bad}",float(bad),cat=cat))
        if "biot_number" in data.columns:
            bad=(data["biot_number"]<0).sum()
            C.append(self._c("th_biot",bad==0,"Biot number≥0",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Domain: Robotics ──────────────────────────────────────────────────────
    def _domain_robotics(self, data, sim, cond):
        C=[]; cat="robotics"
        if not self._dom(sim,SimulationType.ROBOTICS): return self._r(C)
        if "manipulability" in data.columns:
            C.append(self._w("rb_manip",(data["manipulability"]<=0).sum()==0,"Manipulability>0 (non-singular)",cat=cat))
        if "overshoot" in data.columns:
            bad=(data["overshoot"]>1.0).sum()
            C.append(self._w("rb_over",bad==0,"Overshoot<100%",f"{bad}",float(bad),0.0,cat))
        if {"settling_time","rise_time"}.issubset(data.columns):
            bad=(data["settling_time"]<data["rise_time"]).sum()
            C.append(self._w("rb_ts_tr",bad==0,"Settling≥rise time",f"{bad}",float(bad),0.0,cat))
        if "condition_number" in data.columns:
            bad=(data["condition_number"]<1).sum()
            C.append(self._c("rb_cond",bad==0,"Condition number≥1",f"{bad}",float(bad),cat=cat))
        if "workspace_volume" in data.columns:
            C.append(self._c("rb_workspace",(data["workspace_volume"]<=0).sum()==0,"Workspace volume>0",cat=cat))
        if "end_effector_velocity" in data.columns:
            bad=(data["end_effector_velocity"]<0).sum()
            C.append(self._c("rb_ee_vel",bad==0,"EE velocity≥0 (magnitude)",f"{bad}",float(bad),cat=cat))
        if {"joint_torque","payload"}.issubset(data.columns):
            corr=data["payload"].corr(data["joint_torque"].abs())
            C.append(self._w("rb_load_torque",corr>0,"Torque↑ with payload",f"corr={corr:.3f}",float(corr),0.0,cat))
        return self._r(C)

    # ── Domain: Combustion ────────────────────────────────────────────────────
    def _domain_combustion(self, data, sim, cond):
        C=[]; cat="comb"
        if not self._dom(sim,SimulationType.COMBUSTION): return self._r(C)
        if "equivalence_ratio" in data.columns:
            ext=((data["equivalence_ratio"]<0.3)|(data["equivalence_ratio"]>3.0)).sum()
            C.append(self._w("cb_phi",ext==0,"φ in [0.3,3.0]",f"{ext}",float(ext),0.0,cat))
        if {"adiabatic_temperature","temperature"}.issubset(data.columns):
            bad=(data["adiabatic_temperature"]<data["temperature"]).sum()
            C.append(self._w("cb_adiab",bad==0,"T_adiabatic≥T_initial",f"{bad}",float(bad),0.0,cat))
        if {"co_concentration","co2_concentration"}.issubset(data.columns):
            bad=((data["co_concentration"]+data["co2_concentration"])>1.01).sum()
            C.append(self._c("cb_carbon",bad==0,"CO+CO2≤1",f"{bad}",float(bad),cat=cat))
        if {"temperature","nox_concentration"}.issubset(data.columns):
            corr=data["temperature"].corr(data["nox_concentration"])
            C.append(self._w("cb_nox",corr>0,"NOx↑ with T (Zeldovich)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "lewis_number" in data.columns:
            C.append(self._c("cb_lewis",(data["lewis_number"]<=0).sum()==0,"Lewis number>0",cat=cat))
        if "ignition_delay" in data.columns:
            bad=(data["ignition_delay"]<0).sum()
            C.append(self._c("cb_ign_delay",bad==0,"Ignition delay≥0",f"{bad}",float(bad),cat=cat))
        if "soot_volume_fraction" in data.columns:
            bad=(data["soot_volume_fraction"]<0).sum()
            C.append(self._c("cb_soot",bad==0,"Soot volume fraction≥0",f"{bad}",float(bad),cat=cat))
        if "flame_speed" in data.columns:
            bad=(data["flame_speed"]<0).sum()
            C.append(self._c("cb_flame_speed",bad==0,"Flame speed≥0",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Domain: Acoustics ─────────────────────────────────────────────────────
    def _domain_acoustics(self, data, sim, cond):
        C=[]; cat="acoustics"
        if not self._dom(sim,SimulationType.ACOUSTICS): return self._r(C)
        if "sound_pressure_level" in data.columns:
            C.append(self._w("ac_spl_pos",(data["sound_pressure_level"]<0).sum()==0,"SPL≥0 dB",cat=cat))
        if "absorption_coefficient" in data.columns:
            bad=((data["absorption_coefficient"]<0)|(data["absorption_coefficient"]>1)).sum()
            C.append(self._c("ac_abs",bad==0,"Absorption in [0,1]",f"{bad}",float(bad),cat=cat))
        if "reverberation_time" in data.columns:
            C.append(self._c("ac_rt60",(data["reverberation_time"]<=0).sum()==0,"RT60>0",cat=cat))
        if "quality_factor" in data.columns:
            C.append(self._c("ac_q",(data["quality_factor"]<=0).sum()==0,"Q factor>0",cat=cat))
        if {"insertion_loss","noise_reduction"}.issubset(data.columns):
            corr=data["insertion_loss"].corr(data["noise_reduction"])
            C.append(self._w("ac_il_nr",corr>0.3,"IL correlates with NR",f"corr={corr:.3f}",float(corr),0.3,cat))
        if "transmission_loss" in data.columns:
            bad=(data["transmission_loss"]<0).sum()
            C.append(self._c("ac_tl",bad==0,"Transmission loss≥0 dB",f"{bad}",float(bad),cat=cat))
        if {"sound_power_level","sound_pressure_level"}.issubset(data.columns):
            corr=data["sound_power_level"].corr(data["sound_pressure_level"])
            C.append(self._w("ac_spl_swl",corr>0.5,"SPL correlates with SWL",f"corr={corr:.3f}",float(corr),0.5,cat))
        return self._r(C)

    # ── Domain: Electromagnetics ──────────────────────────────────────────────
    def _domain_em(self, data, sim, cond):
        C=[]; cat="em"
        if not self._dom(sim,SimulationType.ELECTROMAGNETICS): return self._r(C)
        if "vswr" in data.columns:
            C.append(self._c("em_vswr",(data["vswr"]<1).sum()==0,"VSWR≥1.0",cat=cat))
        if "return_loss" in data.columns:
            C.append(self._c("em_rl",(data["return_loss"]>0).sum()==0,"Return loss≤0 dB",cat=cat))
        if "power_factor" in data.columns:
            bad=((data["power_factor"]<0)|(data["power_factor"]>1)).sum()
            C.append(self._c("em_pf",bad==0,"Power factor in [0,1]",f"{bad}",float(bad),cat=cat))
        if "radiation_efficiency" in data.columns:
            bad=((data["radiation_efficiency"]<0)|(data["radiation_efficiency"]>1)).sum()
            C.append(self._c("em_rad",bad==0,"Radiation efficiency in [0,1]",f"{bad}",float(bad),cat=cat))
        if {"conductivity","resistivity"}.issubset(data.columns):
            exp_r=1/data["conductivity"].replace(0,np.nan)
            bad=(np.abs(data["resistivity"]-exp_r)/exp_r.clip(lower=1e-30)>0.05).sum()
            C.append(self._w("em_rho_sigma",bad==0,"ρ=1/σ",f"{bad}",float(bad),0.0,cat))
        if "skin_depth" in data.columns:
            bad=(data["skin_depth"]<=0).sum()
            C.append(self._c("em_skin",bad==0,"Skin depth>0",f"{bad}",float(bad),cat=cat))
        if "dielectric_loss_tangent" in data.columns:
            bad=(data["dielectric_loss_tangent"]<0).sum()
            C.append(self._c("em_loss_tan",bad==0,"Loss tangent≥0",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Domain: Geomechanics ──────────────────────────────────────────────────
    def _domain_geomechanics(self, data, sim, cond):
        C=[]; cat="geo"
        if not self._dom(sim,SimulationType.GEOMECHANICS): return self._r(C)
        if "porosity" in data.columns:
            bad=((data["porosity"]<0)|(data["porosity"]>1)).sum()
            C.append(self._c("geo_por",bad==0,"Porosity in [0,1]",f"{bad}",float(bad),cat=cat))
        if "void_ratio" in data.columns:
            C.append(self._c("geo_void",(data["void_ratio"]<0).sum()==0,"Void ratio≥0",cat=cat))
        if "friction_angle" in data.columns:
            bad=((data["friction_angle"]<0)|(data["friction_angle"]>90)).sum()
            C.append(self._c("geo_phi",bad==0,"Friction angle in [0°,90°]",f"{bad}",float(bad),cat=cat))
        if "degree_of_saturation" in data.columns:
            bad=((data["degree_of_saturation"]<0)|(data["degree_of_saturation"]>1)).sum()
            C.append(self._c("geo_sat",bad==0,"Saturation in [0,1]",f"{bad}",float(bad),cat=cat))
        if "slope_stability_factor" in data.columns:
            bad=(data["slope_stability_factor"]<1.0).sum()
            C.append(self._w("geo_slope",bad==0,"SF≥1.0 (stable slope)",f"{bad}",float(bad),0.0,cat))
        if {"effective_stress","stress","pore_pressure"}.issubset(data.columns):
            bad=(np.abs(data["effective_stress"]-(data["stress"]-data["pore_pressure"]))/np.abs(data["stress"]-data["pore_pressure"]).clip(lower=1e-10)>0.05).sum()
            C.append(self._w("geo_terzaghi",bad==0,"σ'=σ-u (Terzaghi)",f"{bad}",float(bad),0.0,cat))
        if "liquefaction_potential" in data.columns:
            bad=((data["liquefaction_potential"]<0)|(data["liquefaction_potential"]>1)).sum()
            C.append(self._c("geo_liq",bad==0,"Liquefaction potential in [0,1]",f"{bad}",float(bad),cat=cat))
        if {"porosity","permeability"}.issubset(data.columns):
            corr=data["porosity"].corr(data["permeability"])
            C.append(self._w("geo_kozeny",corr>0,"Permeability↑ with porosity (Kozeny-Carman)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "bearing_capacity" in data.columns:
            bad=(data["bearing_capacity"]<=0).sum()
            C.append(self._c("geo_bearing",bad==0,"Bearing capacity>0",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Domain: Biomechanics ──────────────────────────────────────────────────
    def _domain_biomechanics(self, data, sim, cond):
        C=[]; cat="bio"
        if not self._dom(sim,SimulationType.BIOMECHANICS): return self._r(C)
        if "heart_rate" in data.columns:
            bad=((data["heart_rate"]<20)|(data["heart_rate"]>250)).sum()
            C.append(self._w("bio_hr",bad==0,"Heart rate in [20,250] bpm",f"{bad}",float(bad),0.0,cat))
        if "blood_pressure" in data.columns:
            bad=((data["blood_pressure"]<30)|(data["blood_pressure"]>300)).sum()
            C.append(self._w("bio_bp",bad==0,"Blood pressure in [30,300] mmHg",f"{bad}",float(bad),0.0,cat))
        if "fracture_risk" in data.columns:
            bad=((data["fracture_risk"]<0)|(data["fracture_risk"]>1)).sum()
            C.append(self._c("bio_frac",bad==0,"Fracture risk in [0,1]",f"{bad}",float(bad),cat=cat))
        if "metabolic_power" in data.columns:
            C.append(self._c("bio_met",(data["metabolic_power"]<0).sum()==0,"Metabolic power≥0",cat=cat))
        if {"bone_stress","cartilage_stress"}.issubset(data.columns):
            bad=(data["bone_stress"]<data["cartilage_stress"]).sum()
            C.append(self._w("bio_bone_cart",bad==0,"Bone stress>cartilage stress",f"{bad}",float(bad),0.0,cat))
        if "body_mass_index" in data.columns:
            bad=((data["body_mass_index"]<10)|(data["body_mass_index"]>70)).sum()
            C.append(self._w("bio_bmi",bad==0,"BMI in [10,70]",f"{bad}",float(bad),0.0,cat))
        if "oxygen_consumption" in data.columns:
            bad=(data["oxygen_consumption"]<0).sum()
            C.append(self._c("bio_vo2",(data["oxygen_consumption"]<0).sum()==0,"VO2≥0",cat=cat))
        if {"gait_speed","stride_length"}.issubset(data.columns):
            corr=data["gait_speed"].corr(data["stride_length"])
            C.append(self._w("bio_gait",corr>0,"Stride length↑ with speed",f"corr={corr:.3f}",float(corr),0.0,cat))
        return self._r(C)

    # ── Domain: Nuclear ───────────────────────────────────────────────────────
    def _domain_nuclear(self, data, sim, cond):
        C=[]; cat="nuclear"
        if not self._dom(sim,SimulationType.NUCLEAR): return self._r(C)
        if "criticality_factor" in data.columns:
            C.append(self._c("nuc_keff_pos",(data["criticality_factor"]<=0).sum()==0,"keff>0",cat=cat))
            bad=(data["criticality_factor"]>2.0).sum()
            C.append(self._w("nuc_keff_lim",bad==0,"keff<2.0",f"{bad}",float(bad),0.0,cat))
        if "doppler_coefficient" in data.columns:
            bad=(data["doppler_coefficient"]>0).sum()
            C.append(self._w("nuc_doppler",bad==0,"Doppler coeff<0 (negative feedback)",f"{bad}",float(bad),0.0,cat))
        if "delayed_neutron_fraction" in data.columns:
            bad=((data["delayed_neutron_fraction"]<0)|(data["delayed_neutron_fraction"]>0.1)).sum()
            C.append(self._c("nuc_beta",bad==0,"β in [0,0.1]",f"{bad}",float(bad),cat=cat))
        if "enrichment" in data.columns:
            bad=((data["enrichment"]<0)|(data["enrichment"]>100)).sum()
            C.append(self._c("nuc_enrich",bad==0,"Enrichment in [0,100]%",f"{bad}",float(bad),cat=cat))
        if {"fuel_temperature","cladding_temperature"}.issubset(data.columns):
            bad=(data["fuel_temperature"]<data["cladding_temperature"]).sum()
            C.append(self._w("nuc_tfuel_tclad",bad==0,"Fuel T > cladding T (heat flows outward)",f"{bad}",float(bad),0.0,cat))
        if "decay_heat" in data.columns:
            C.append(self._c("nuc_decay",(data["decay_heat"]<0).sum()==0,"Decay heat≥0",cat=cat))
        if {"neutron_flux","power_density"}.issubset(data.columns):
            corr=data["neutron_flux"].corr(data["power_density"])
            C.append(self._w("nuc_flux_power",corr>0.5,"Power∝neutron flux",f"corr={corr:.3f}",float(corr),0.5,cat))
        return self._r(C)

    # ── Domain: Plasma ────────────────────────────────────────────────────────
    def _domain_plasma(self, data, sim, cond):
        C=[]; cat="plasma"
        if not self._dom(sim,SimulationType.PLASMA): return self._r(C)
        if "plasma_beta" in data.columns:
            C.append(self._c("pl_beta_pos",(data["plasma_beta"]<0).sum()==0,"β≥0",cat=cat))
            bad=(data["plasma_beta"]>1).sum()
            C.append(self._w("pl_mhd_stable",bad==0,"β<1 (MHD stability)",f"{bad}",float(bad),0.0,cat))
        if {"electron_temperature","ion_temperature"}.issubset(data.columns):
            ratio=data["electron_temperature"]/data["ion_temperature"].replace(0,np.nan)
            bad=((ratio<0.01)|(ratio>100)).sum()
            C.append(self._w("pl_te_ti",bad==0,"Te/Ti in [0.01,100]",f"{bad}",float(bad),0.0,cat))
        if "alfven_speed" in data.columns:
            bad=(data["alfven_speed"]>P["c"]).sum()
            C.append(self._c("pl_alfven_c",bad==0,"Alfvén speed<c",f"{bad}",float(bad),cat=cat))
        if "confinement_time" in data.columns:
            C.append(self._c("pl_tau_pos",(data["confinement_time"]<=0).sum()==0,"Confinement time>0",cat=cat))
        if "debye_length" in data.columns:
            bad=(data["debye_length"]<=0).sum()
            C.append(self._c("pl_debye_pos",bad==0,"Debye length>0",f"{bad}",float(bad),cat=cat))
        if {"electron_density","debye_length"}.issubset(data.columns):
            # Number of particles in Debye sphere N_D = n*(4π/3)*λ_D³ >> 1
            N_D=data["electron_density"]*4*math.pi/3*data["debye_length"]**3
            bad=(N_D<1).sum()
            C.append(self._w("pl_debye_sphere",bad==0,"N_D>>1 (plasma criterion)",f"{bad} N_D<1",float(bad),0.0,cat))
        return self._r(C)

    # ── Domain: Chemical ──────────────────────────────────────────────────────
    def _domain_chemical(self, data, sim, cond):
        C=[]; cat="chem"
        if not self._dom(sim,SimulationType.CHEMICAL): return self._r(C)
        if "conversion" in data.columns:
            bad=((data["conversion"]<0)|(data["conversion"]>1)).sum()
            C.append(self._c("ch_conv",bad==0,"Conversion in [0,1]",f"{bad}",float(bad),cat=cat))
        if "ph" in data.columns:
            bad=((data["ph"]<0)|(data["ph"]>14)).sum()
            C.append(self._c("ch_ph",bad==0,"pH in [0,14]",f"{bad}",float(bad),cat=cat))
        if "effectiveness_factor" in data.columns:
            bad=((data["effectiveness_factor"]<0)|(data["effectiveness_factor"]>1)).sum()
            C.append(self._c("ch_eta",bad==0,"Effectiveness in [0,1]",f"{bad}",float(bad),cat=cat))
        if {"temperature","reaction_rate"}.issubset(data.columns):
            corr=data["temperature"].corr(data["reaction_rate"])
            C.append(self._w("ch_arrhenius",corr>0,"Rate↑ with T (Arrhenius)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "activation_energy" in data.columns:
            C.append(self._w("ch_ea_pos",(data["activation_energy"]<0).sum()==0,"Ea≥0",cat=cat))
        if {"selectivity","yield_chemical"}.issubset(data.columns):
            bad=(data["yield_chemical"]>data["selectivity"]+0.01).sum()
            C.append(self._w("ch_yield_sel",bad==0,"Yield≤selectivity",f"{bad}",float(bad),0.0,cat))
        if "reaction_enthalpy" in data.columns:
            exo=(data["reaction_enthalpy"]<0).sum(); endo=(data["reaction_enthalpy"]>0).sum()
            C.append(self._w("ch_enthalpy",True,f"{exo} exothermic, {endo} endothermic reactions","",cat=cat))
        if "damkohler_number" in data.columns:
            bad=(data["damkohler_number"]<0).sum()
            C.append(self._c("ch_da",bad==0,"Damköhler number≥0",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Domain: Hydrodynamics ─────────────────────────────────────────────────
    def _domain_hydro(self, data, sim, cond):
        C=[]; cat="hydro"
        if not self._dom(sim,SimulationType.HYDRODYNAMICS): return self._r(C)
        if {"wave_height","water_depth"}.issubset(data.columns):
            bad=(data["wave_height"]>data["water_depth"]).sum()
            C.append(self._w("hy_breaking",bad==0,"Wave height<water depth",f"{bad}",float(bad),0.0,cat))
        if "steepness" in data.columns:
            bad=(data["steepness"]>0.142).sum()
            C.append(self._c("hy_steep",bad==0,"Steepness<0.142 (physical limit)",f"{bad}",float(bad),cat=cat))
        if {"wave_speed","wave_length","wave_period"}.issubset(data.columns):
            exp=data["wave_length"]/data["wave_period"].replace(0,np.nan)
            bad=(np.abs(data["wave_speed"]-exp)/exp.clip(lower=1e-10)>0.05).sum()
            C.append(self._w("hy_clt",bad==0,"c=λ/T (wave speed)",f"{bad}",float(bad),0.0,cat))
        if "mooring_tension" in data.columns:
            C.append(self._c("hy_moor",(data["mooring_tension"]<0).sum()==0,"Mooring tension≥0",cat=cat))
        if "added_mass" in data.columns:
            C.append(self._c("hy_added_mass",(data["added_mass"]<0).sum()==0,"Added mass≥0",cat=cat))
        if {"significant_wave_height","peak_period"}.issubset(data.columns):
            corr=data["significant_wave_height"].corr(data["peak_period"])
            C.append(self._w("hy_hs_tp",corr>0,"Hs and Tp positively correlated",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "response_amplitude" in data.columns:
            bad=(data["response_amplitude"]<0).sum()
            C.append(self._c("hy_rao",bad==0,"Response amplitude≥0",f"{bad}",float(bad),cat=cat))
        return self._r(C)

    # ── Domain: Meteorology ───────────────────────────────────────────────────
    def _domain_meteo(self, data, sim, cond):
        C=[]; cat="meteo"
        if not self._dom(sim,SimulationType.METEOROLOGY): return self._r(C)
        if {"temperature","dew_point"}.issubset(data.columns):
            bad=(data["dew_point"]>data["temperature"]).sum()
            C.append(self._c("mt_dew",bad==0,"Dew point≤temperature",f"{bad}",float(bad),cat=cat))
        if "humidity" in data.columns:
            bad=((data["humidity"]<0)|(data["humidity"]>100)).sum()
            C.append(self._c("mt_rh",bad==0,"RH in [0,100]%",f"{bad}",float(bad),cat=cat))
        if "wind_direction" in data.columns:
            bad=((data["wind_direction"]<0)|(data["wind_direction"]>=360)).sum()
            C.append(self._c("mt_wdir",bad==0,"Wind dir in [0°,360°)",f"{bad}",float(bad),cat=cat))
        if "cloud_cover" in data.columns:
            bad=((data["cloud_cover"]<0)|(data["cloud_cover"]>100)).sum()
            C.append(self._c("mt_cloud",bad==0,"Cloud cover in [0,100]%",f"{bad}",float(bad),cat=cat))
        if {"solar_radiation","cloud_cover"}.issubset(data.columns):
            corr=data["cloud_cover"].corr(data["solar_radiation"])
            C.append(self._w("mt_cloud_solar",corr<0,"Solar radiation↓ with cloud cover",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "precipitation" in data.columns:
            C.append(self._c("mt_precip",(data["precipitation"]<0).sum()==0,"Precipitation≥0",cat=cat))
        if "uv_index" in data.columns:
            C.append(self._c("mt_uv",(data["uv_index"]<0).sum()==0,"UV index≥0",cat=cat))
        if {"temperature","pressure"}.issubset(data.columns):
            corr=data["temperature"].corr(data["pressure"])
            C.append(self._w("mt_t_p",corr>0,"T and P correlated (surface conditions)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "solar_radiation" in data.columns:
            bad=(data["solar_radiation"]>1500).sum()
            C.append(self._w("mt_sol_lim",bad==0,"Solar radiation<1500 W/m² (solar constant)",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Domain: Astrophysics ──────────────────────────────────────────────────
    def _domain_astro(self, data, sim, cond):
        C=[]; cat="astro"
        if not self._dom(sim,SimulationType.ASTROPHYSICS): return self._r(C)
        if "velocity" in data.columns:
            bad=(data["velocity"]>=P["c"]).sum()
            C.append(self._c("as_subluminal",bad==0,"v<c (subluminal)",f"{bad}",float(bad),cat=cat))
        if "redshift" in data.columns:
            C.append(self._c("as_redshift",(data["redshift"]<-1).sum()==0,"Redshift≥-1",cat=cat))
        if "escape_velocity" in data.columns:
            bad=(data["escape_velocity"]>P["c"]).sum()
            C.append(self._w("as_escape",bad==0,"Escape velocity<c (non-BH objects)",f"{bad}",float(bad),0.0,cat))
        if {"luminosity","temperature","radius"}.issubset(data.columns):
            exp_l=4*math.pi*data["radius"]**2*P["sigma_sb"]*data["temperature"]**4
            bad=(np.abs(data["luminosity"]-exp_l)/exp_l.clip(lower=1e-30)>0.3).sum()
            C.append(self._w("as_sb",bad==0,"L=4πR²σT⁴",f"{bad}",float(bad),0.0,cat))
        if {"mass","schwarzschild_radius"}.issubset(data.columns):
            G=6.674e-11
            exp_rs=2*G*data["mass"]/P["c"]**2
            bad=(np.abs(data["schwarzschild_radius"]-exp_rs)/exp_rs.clip(lower=1e-30)>0.1).sum()
            C.append(self._w("as_rsch",bad==0,"Rs=2GM/c²",f"{bad}",float(bad),0.0,cat))
        if "metallicity" in data.columns:
            bad=((data["metallicity"]<-5)|(data["metallicity"]>2)).sum()
            C.append(self._w("as_metal",bad==0,"Metallicity in [-5,2] (log solar)",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Domain: Materials ─────────────────────────────────────────────────────
    def _domain_materials(self, data, sim, cond):
        C=[]; cat="materials"
        if not self._dom(sim,SimulationType.MATERIALS): return self._r(C)
        if {"tensile_strength","yield_strength"}.issubset(data.columns):
            bad=(data["tensile_strength"]<data["yield_strength"]).sum()
            C.append(self._c("mat_uts_ys",bad==0,"UTS>yield strength",f"{bad}",float(bad),cat=cat))
        if "poisson_ratio" in data.columns:
            bad=((data["poisson_ratio"]<-1)|(data["poisson_ratio"]>0.5)).sum()
            C.append(self._c("mat_nu",bad==0,"Poisson in [-1,0.5]",f"{bad}",float(bad),cat=cat))
        if "grain_size" in data.columns:
            C.append(self._c("mat_grain",(data["grain_size"]<=0).sum()==0,"Grain size>0",cat=cat))
        if {"yield_strength","grain_size"}.issubset(data.columns):
            corr=np.log10(data["grain_size"].clip(lower=1e-10)).corr(data["yield_strength"])
            C.append(self._w("mat_hp",corr<0,"Hall-Petch: yield↑ as grain↓",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "wear_rate" in data.columns:
            C.append(self._c("mat_wear",(data["wear_rate"]<0).sum()==0,"Wear rate≥0",cat=cat))
        if "thermal_expansion" in data.columns:
            bad=(data["thermal_expansion"]<-1e-3).sum()
            C.append(self._w("mat_cte",bad==0,"CTE reasonable",f"{bad}",float(bad),0.0,cat))
        if {"elastic_modulus","poisson_ratio","shear_modulus"}.issubset(data.columns):
            exp_G=data["elastic_modulus"]/(2*(1+data["poisson_ratio"]))
            bad=(np.abs(data["shear_modulus"]-exp_G)/exp_G.clip(lower=1e-10)>0.1).sum()
            C.append(self._w("mat_G_E_nu",bad==0,"G=E/[2(1+ν)]",f"{bad}",float(bad),0.0,cat))
        if {"hardness","yield_strength"}.issubset(data.columns):
            corr=data["hardness"].corr(data["yield_strength"])
            C.append(self._w("mat_hard_ys",corr>0.3,"Hardness correlates with YS",f"corr={corr:.3f}",float(corr),0.3,cat))
        return self._r(C)

    # ── Domain: Tribology ─────────────────────────────────────────────────────
    def _domain_tribology(self, data, sim, cond):
        C=[]; cat="tribo"
        if not self._dom(sim,SimulationType.TRIBOLOGY): return self._r(C)
        if "friction_coefficient" in data.columns:
            bad=((data["friction_coefficient"]<0)|(data["friction_coefficient"]>5)).sum()
            C.append(self._w("tr_mu",bad==0,"μ in [0,5]",f"{bad}",float(bad),0.0,cat))
        if "lambda_ratio" in data.columns:
            b=(data["lambda_ratio"]<1).sum(); m=((data["lambda_ratio"]>=1)&(data["lambda_ratio"]<3)).sum(); f=(data["lambda_ratio"]>=3).sum()
            C.append(self._w("tr_regime",True,f"Stribeck: {b} boundary, {m} mixed, {f} full-film","",cat=cat))
        if {"friction_coefficient","lambda_ratio"}.issubset(data.columns):
            corr=data["lambda_ratio"].corr(data["friction_coefficient"])
            C.append(self._w("tr_stribeck",corr<0,"μ↓ with λ (Stribeck curve)",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "film_thickness" in data.columns:
            C.append(self._w("tr_film",(data["film_thickness"]<=0).sum()==0,"Film thickness>0",cat=cat))
        if "wear_rate" in data.columns:
            C.append(self._c("tr_wear",(data["wear_rate"]<0).sum()==0,"Wear rate≥0",cat=cat))
        if {"contact_pressure","hertz_pressure"}.issubset(data.columns):
            bad=(np.abs(data["contact_pressure"]-data["hertz_pressure"])/data["hertz_pressure"].clip(lower=1e-10)>0.3).sum()
            C.append(self._w("tr_hertz",bad==0,"Contact≈Hertz pressure",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Domain: Aeroelasticity ────────────────────────────────────────────────
    def _domain_aeroelasticity(self, data, sim, cond):
        C=[]; cat="aeroelastic"
        if not self._dom(sim,SimulationType.AEROELASTICITY): return self._r(C)
        if {"flutter_speed","divergence_speed"}.issubset(data.columns):
            bad=(data["flutter_speed"]>data["divergence_speed"]).sum()
            C.append(self._w("ae_fl_div",bad==0,"Flutter speed<divergence speed",f"{bad}",float(bad),0.0,cat))
        if "aerodynamic_damping" in data.columns:
            neg=(data["aerodynamic_damping"]<0).sum()
            C.append(self._w("ae_aero_damp",neg==0,"Aerodynamic damping≥0 (stable)",f"{neg}",float(neg),0.0,cat))
        if "reduced_frequency" in data.columns:
            C.append(self._c("ae_kred",(data["reduced_frequency"]<0).sum()==0,"Reduced frequency≥0",cat=cat))
        if {"tip_deflection","dynamic_pressure"}.issubset(data.columns):
            corr=data["dynamic_pressure"].corr(data["tip_deflection"].abs())
            C.append(self._w("ae_defl_q",corr>0,"Tip deflection↑ with q",f"corr={corr:.3f}",float(corr),0.0,cat))
        if "torsion_angle" in data.columns:
            bad=(data["torsion_angle"].abs()>40).sum()
            C.append(self._w("ae_torsion",bad==0,"Torsion<40° (no divergence)",f"{bad}",float(bad),0.0,cat))
        if "advance_ratio" in data.columns:
            bad=(data["advance_ratio"]<0).sum()
            C.append(self._c("ae_mu",bad==0,"Advance ratio≥0",f"{bad}",float(bad),cat=cat))
        if "thrust_coefficient" in data.columns:
            bad=(data["thrust_coefficient"]<-0.5).sum()
            C.append(self._w("ae_ct",bad==0,"Thrust coefficient>-0.5",f"{bad}",float(bad),0.0,cat))
        return self._r(C)

    # ── Domain: Cryogenics ────────────────────────────────────────────────────
    def _domain_cryogenics(self, data, sim, cond):
        C=[]; cat="cryo"
        if not self._dom(sim,SimulationType.CRYOGENICS): return self._r(C)
        if "temperature" in data.columns:
            bad=(data["temperature"]<=0).sum()
            C.append(self._c("cr_temp_pos",bad==0,"Temperature>0 K",f"{bad}",float(bad),cat=cat))
            warm=(data["temperature"]>300).sum()
            C.append(self._w("cr_cryo_range",warm==0,"Temperature<300K (cryogenic)",f"{warm}",float(warm),0.0,cat))
        if "superfluid_fraction" in data.columns:
            bad=((data["superfluid_fraction"]<0)|(data["superfluid_fraction"]>1)).sum()
            C.append(self._c("cr_sf",bad==0,"Superfluid fraction in [0,1]",f"{bad}",float(bad),cat=cat))
        if {"boiling_point","critical_temperature"}.issubset(data.columns):
            bad=(data["boiling_point"]>data["critical_temperature"]).sum()
            C.append(self._w("cr_bp_tc",bad==0,"Boiling point<critical T",f"{bad}",float(bad),0.0,cat))
        if "latent_heat" in data.columns:
            C.append(self._c("cr_latent",(data["latent_heat"]<0).sum()==0,"Latent heat≥0",cat=cat))
        if "quench_energy" in data.columns:
            C.append(self._c("cr_quench",(data["quench_energy"]<0).sum()==0,"Quench energy≥0",cat=cat))
        if {"vapor_pressure","critical_pressure"}.issubset(data.columns):
            bad=(data["vapor_pressure"]>data["critical_pressure"]).sum()
            C.append(self._w("cr_vp_pc",bad==0,"Vapor pressure<critical pressure",f"{bad}",float(bad),0.0,cat))
        if {"temperature","superfluid_fraction"}.issubset(data.columns):
            corr=data["temperature"].corr(data["superfluid_fraction"])
            C.append(self._w("cr_sf_temp",corr<0,"Superfluid fraction↓ with T",f"corr={corr:.3f}",float(corr),0.0,cat))
        return self._r(C)

    def report_to_dict(self, report):
        from dataclasses import asdict as _asdict
        d = _asdict(report)
        d["confidence"]     = report.confidence.value
        d["overall_status"] = report.overall_status.value
        for c in d.get("issues",[]):
            if hasattr(c.get("status"),"value"):
                c["status"] = c["status"].value
        return d
