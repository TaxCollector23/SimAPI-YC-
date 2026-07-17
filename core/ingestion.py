"""
SimAPI — Data Ingestion Layer v2
Handles CSV, JSON, YAML, TOML, TXT/Markdown, VTK, NumPy, OpenFOAM.
Aggressive column alias normalization so physics checks fire
regardless of what naming convention the user's sim tool uses.
"""

import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

try:
    import tomllib  # Python 3.11+ stdlib
except ModuleNotFoundError:
    import tomli as tomllib  # Python 3.10 backport

# ── Exhaustive alias map ───────────────────────────────────────────────────────
# Every common variant → canonical SimAPI name.
# Covers ANSYS, OpenFOAM, STAR-CCM+, Fluent, COMSOL, SU2, Abaqus, MATLAB conventions.
COLUMN_ALIASES = {
    # ── Aerodynamics ──────────────────────────────────────────────────────────
    "cd": "drag_coefficient", "c_d": "drag_coefficient",
    "drag_coeff": "drag_coefficient", "drag_coefficient": "drag_coefficient",
    "coeff_drag": "drag_coefficient", "coefficient_of_drag": "drag_coefficient",
    "cdtotal": "drag_coefficient", "cd_total": "drag_coefficient",

    "cl": "lift_coefficient", "c_l": "lift_coefficient",
    "lift_coeff": "lift_coefficient", "lift_coefficient": "lift_coefficient",
    "coeff_lift": "lift_coefficient", "coefficient_of_lift": "lift_coefficient",

    "cy": "side_force_coefficient", "c_y": "side_force_coefficient",
    "side_force_coefficient": "side_force_coefficient",

    "cm": "pitching_moment", "c_m": "pitching_moment",
    "pitching_moment": "pitching_moment", "pitching_moment_coefficient": "pitching_moment",

    "cp": "pressure_coefficient", "c_p": "pressure_coefficient",
    "pressure_coefficient": "pressure_coefficient", "coeff_pressure": "pressure_coefficient",

    "cf": "skin_friction_coefficient", "c_f": "skin_friction_coefficient",
    "skin_friction_coefficient": "skin_friction_coefficient",
    "skin_friction": "skin_friction_coefficient",

    "e": "oswald_efficiency", "oswald_e": "oswald_efficiency",
    "oswald_efficiency": "oswald_efficiency", "span_efficiency": "oswald_efficiency",

    "cdi": "induced_drag_coefficient", "c_di": "induced_drag_coefficient",
    "induced_drag_coefficient": "induced_drag_coefficient",
    "induced_drag": "induced_drag_coefficient",

    "ld": "lift_to_drag_ratio", "l_d": "lift_to_drag_ratio",
    "lift_to_drag": "lift_to_drag_ratio", "lift_to_drag_ratio": "lift_to_drag_ratio",
    "l/d": "lift_to_drag_ratio",

    "aoa": "angle_of_attack", "alpha": "angle_of_attack",
    "angle_of_attack": "angle_of_attack", "attack_angle": "angle_of_attack",
    "incidence": "angle_of_attack",

    "ti": "turbulence_intensity", "tu": "turbulence_intensity",
    "turbulence_intensity": "turbulence_intensity",
    "turb_intensity": "turbulence_intensity",

    "st": "strouhal_number", "sr": "strouhal_number",
    "strouhal": "strouhal_number", "strouhal_number": "strouhal_number",

    "delta_bl": "boundary_layer_thickness", "delta": "boundary_layer_thickness",
    "boundary_layer_thickness": "boundary_layer_thickness",
    "bl_thickness": "boundary_layer_thickness",

    # ── Flow / fluid ──────────────────────────────────────────────────────────
    "p": "pressure", "pres": "pressure", "press": "pressure",
    "pressure": "pressure", "static_pressure": "pressure",
    "p_static": "pressure", "p_s": "pressure",

    "v": "velocity", "vel": "velocity", "u": "velocity",
    "velocity": "velocity", "speed": "velocity",
    "flow_velocity": "velocity", "u_mag": "velocity",
    "velocity_magnitude": "velocity", "vmag": "velocity",

    "ux": "velocity_x", "u_x": "velocity_x", "vx": "velocity_x",
    "velocity_x": "velocity_x", "x_velocity": "velocity_x",
    "uy": "velocity_y", "u_y": "velocity_y", "vy": "velocity_y",
    "velocity_y": "velocity_y", "y_velocity": "velocity_y",
    "uz": "velocity_z", "u_z": "velocity_z", "vz": "velocity_z",
    "velocity_z": "velocity_z", "z_velocity": "velocity_z",

    "re": "reynolds_number", "reynolds": "reynolds_number",
    "reynolds_number": "reynolds_number", "re_number": "reynolds_number",
    "re_l": "reynolds_number", "re_x": "reynolds_number",

    "ma": "mach_number", "mach": "mach_number",
    "mach_number": "mach_number", "m": "mach_number",
    "mach_no": "mach_number",

    "fr": "froude_number", "froude": "froude_number",
    "froude_number": "froude_number",

    "we": "weber_number", "weber": "weber_number",
    "weber_number": "weber_number",

    "rho": "density", "dens": "density", "density": "density",
    "fluid_density": "density", "air_density": "density",

    "mu": "viscosity", "visc": "viscosity", "viscosity": "viscosity",
    "dynamic_viscosity": "viscosity", "dyn_visc": "viscosity",

    "k": "turbulent_kinetic_energy", "tke": "turbulent_kinetic_energy",
    "turbulent_kinetic_energy": "turbulent_kinetic_energy",
    "turb_ke": "turbulent_kinetic_energy",

    "eps": "turbulent_dissipation", "epsilon": "turbulent_dissipation",
    "turbulent_dissipation": "turbulent_dissipation",
    "turb_dissipation": "turbulent_dissipation",

    "dp": "pressure_drop", "delta_p": "pressure_drop",
    "pressure_drop": "pressure_drop", "pressure_loss": "pressure_drop",

    "q_flow": "flow_rate", "flowrate": "flow_rate",
    "flow_rate": "flow_rate", "volumetric_flow_rate": "flow_rate",

    "mdot": "mass_flow_rate", "m_dot": "mass_flow_rate",
    "mass_flow_rate": "mass_flow_rate", "massflow": "mass_flow_rate",

    "tau_w": "wall_shear_stress", "wall_shear": "wall_shear_stress",
    "wall_shear_stress": "wall_shear_stress",

    "f": "darcy_friction_factor", "darcy_f": "darcy_friction_factor",
    "darcy_friction_factor": "darcy_friction_factor",
    "friction_factor": "darcy_friction_factor",

    "sigma_cav": "cavitation_number", "cavitation": "cavitation_number",
    "cavitation_number": "cavitation_number",

    "yplus": "y_plus", "y_plus": "y_plus", "y+": "y_plus",

    "q_dyn": "dynamic_pressure", "dynamic_pressure": "dynamic_pressure",
    "qinf": "dynamic_pressure",

    # ── Structural ────────────────────────────────────────────────────────────
    "sigma": "stress", "s": "stress", "stress": "stress",
    "normal_stress": "stress", "axial_stress": "stress",

    "epsilon_s": "strain", "strain": "strain", "eps_s": "strain",
    "total_strain": "strain",

    "e_mod": "elastic_modulus", "youngs_modulus": "elastic_modulus",
    "elastic_modulus": "elastic_modulus", "young_modulus": "elastic_modulus",
    "e_young": "elastic_modulus",

    "vm": "von_mises_stress", "von_mises": "von_mises_stress",
    "von_mises_stress": "von_mises_stress", "mises": "von_mises_stress",
    "equivalent_stress": "von_mises_stress",

    "s1": "principal_stress_1", "sigma1": "principal_stress_1",
    "principal_stress_1": "principal_stress_1",
    "max_principal_stress": "principal_stress_1",
    "s2": "principal_stress_2", "sigma2": "principal_stress_2",
    "principal_stress_2": "principal_stress_2",
    "s3": "principal_stress_3", "sigma3": "principal_stress_3",
    "principal_stress_3": "principal_stress_3",
    "min_principal_stress": "principal_stress_3",

    "tau": "shear_stress", "shear": "shear_stress",
    "shear_stress": "shear_stress",

    "sf": "safety_factor", "fos": "safety_factor",
    "safety_factor": "safety_factor", "factor_of_safety": "safety_factor",

    "nu": "poisson_ratio", "poisson": "poisson_ratio",
    "poisson_ratio": "poisson_ratio", "nu_poisson": "poisson_ratio",

    "uy_struct": "displacement", "u_total": "displacement",
    "displacement": "displacement", "deformation": "displacement",
    "total_displacement": "displacement",

    "sy": "yield_stress", "yield": "yield_stress",
    "yield_stress": "yield_stress", "yield_strength": "yield_stress",
    "tensile_yield": "yield_stress",

    "su": "ultimate_stress", "uts": "ultimate_stress",
    "ultimate_stress": "ultimate_stress", "ultimate_strength": "ultimate_stress",
    "tensile_strength": "ultimate_stress",

    "kt": "stress_concentration", "stress_concentration": "stress_concentration",
    "scf": "stress_concentration", "concentration_factor": "stress_concentration",

    "nf": "fatigue_life", "cycles": "fatigue_life",
    "fatigue_life": "fatigue_life", "life": "fatigue_life",
    "fatigue_cycles": "fatigue_life",

    "fn": "natural_frequency", "omega_n": "natural_frequency",
    "natural_frequency": "natural_frequency", "resonant_frequency": "natural_frequency",
    "freq_natural": "natural_frequency",

    "zeta": "damping_ratio", "damping": "damping_ratio",
    "damping_ratio": "damping_ratio", "critical_damping_ratio": "damping_ratio",

    "kic": "fracture_toughness", "k_ic": "fracture_toughness",
    "fracture_toughness": "fracture_toughness",

    "a_crack": "crack_length", "crack_length": "crack_length",
    "crack_size": "crack_length",

    # ── Thermodynamics ────────────────────────────────────────────────────────
    "t": "temperature", "temp": "temperature",
    "temperature": "temperature", "T": "temperature",
    "fluid_temp": "temperature", "bulk_temperature": "temperature",

    "q": "heat_flux", "heat_flux": "heat_flux",
    "q_flux": "heat_flux", "heat_flow": "heat_flux",

    "eta": "thermal_efficiency", "efficiency": "thermal_efficiency",
    "thermal_efficiency": "thermal_efficiency", "thermo_efficiency": "thermal_efficiency",

    "s_gen": "entropy_generation", "entropy_gen": "entropy_generation",
    "entropy_generation": "entropy_generation",

    "h": "enthalpy", "enthalpy": "enthalpy",
    "specific_enthalpy": "enthalpy",

    "k_therm": "thermal_conductivity", "conductivity": "thermal_conductivity",
    "thermal_conductivity": "thermal_conductivity", "lambda": "thermal_conductivity",

    "alpha_therm": "thermal_diffusivity", "thermal_diffusivity": "thermal_diffusivity",

    "bi": "biot_number", "biot": "biot_number", "biot_number": "biot_number",

    "nu_heat": "nusselt_number", "nu_nusselt": "nusselt_number",
    "nusselt": "nusselt_number", "nusselt_number": "nusselt_number",

    "pr": "prandtl_number", "prandtl": "prandtl_number",
    "prandtl_number": "prandtl_number",

    "gr": "grashof_number", "grashof": "grashof_number",
    "grashof_number": "grashof_number",

    "ra": "rayleigh_number", "rayleigh": "rayleigh_number",
    "rayleigh_number": "rayleigh_number",

    "h_conv": "heat_transfer_coefficient",
    "heat_transfer_coefficient": "heat_transfer_coefficient",
    "htc": "heat_transfer_coefficient", "convection_coefficient": "heat_transfer_coefficient",

    "eps_emit": "emissivity", "emissivity": "emissivity",
    "emittance": "emissivity",

    "carnot_eta": "carnot_efficiency", "carnot_efficiency": "carnot_efficiency",
    "eta_carnot": "carnot_efficiency",

    "cop_heat": "cop", "cop": "cop", "coefficient_of_performance": "cop",

    "w_out": "work_output", "work_output": "work_output", "work": "work_output",

    "q_in": "heat_input", "heat_input": "heat_input",
    "heat_added": "heat_input",

    "ex": "exergy", "exergy": "exergy", "available_work": "exergy",

    "eps_hx": "effectiveness", "effectiveness": "effectiveness",
    "hx_effectiveness": "effectiveness",

    "lmtd": "log_mean_temperature", "log_mean_temperature": "log_mean_temperature",
    "delta_t_lm": "log_mean_temperature",

    "ntu_val": "ntu", "ntu": "ntu", "number_of_transfer_units": "ntu",

    # ── Robotics ──────────────────────────────────────────────────────────────
    "torque": "joint_torque", "joint_torque": "joint_torque",
    "tau_joint": "joint_torque", "motor_torque": "joint_torque",

    "omega": "joint_velocity", "joint_velocity": "joint_velocity",
    "angular_velocity": "joint_velocity", "dtheta": "joint_velocity",

    "alpha_joint": "joint_acceleration", "joint_acceleration": "joint_acceleration",
    "angular_acceleration": "joint_acceleration",

    "theta": "joint_position", "joint_position": "joint_position",
    "joint_angle": "joint_position",

    "f_ee": "end_effector_force", "ee_force": "end_effector_force",
    "end_effector_force": "end_effector_force",

    "pos_err": "position_error", "position_error": "position_error",
    "tracking_error": "position_error",

    "w": "manipulability", "manipulability": "manipulability",
    "manip_index": "manipulability",

    "kappa": "condition_number", "condition_number": "condition_number",
    "cond_num": "condition_number",

    "p_elec": "power_consumption", "power_consumption": "power_consumption",
    "power": "power_consumption", "electrical_power": "power_consumption",

    "ts": "settling_time", "settling_time": "settling_time",
    "t_settle": "settling_time",

    "tr_rise": "rise_time", "rise_time": "rise_time", "t_rise": "rise_time",

    "mp": "overshoot", "overshoot": "overshoot", "percent_overshoot": "overshoot",

    # ── Combustion ────────────────────────────────────────────────────────────
    "phi": "equivalence_ratio", "equiv_ratio": "equivalence_ratio",
    "equivalence_ratio": "equivalence_ratio", "lambda_inv": "equivalence_ratio",

    "hrr": "heat_release_rate", "heat_release_rate": "heat_release_rate",
    "q_release": "heat_release_rate",

    "sl": "flame_speed", "flame_speed": "flame_speed",
    "burning_velocity": "flame_speed",

    "ign_delay": "ignition_delay", "ignition_delay": "ignition_delay",
    "tau_ign": "ignition_delay",

    "t_flame": "flame_temperature", "flame_temperature": "flame_temperature",
    "t_ad": "adiabatic_temperature", "adiabatic_temperature": "adiabatic_temperature",

    "eta_comb": "combustion_efficiency", "combustion_efficiency": "combustion_efficiency",

    "le": "lewis_number", "lewis": "lewis_number", "lewis_number": "lewis_number",

    "ze": "zeldovich_number", "zeldovich_number": "zeldovich_number",

    # ── Acoustics ─────────────────────────────────────────────────────────────
    "spl": "sound_pressure_level", "sound_pressure_level": "sound_pressure_level",
    "l_p": "sound_pressure_level",

    "swl": "sound_power_level", "sound_power_level": "sound_power_level",
    "l_w": "sound_power_level",

    "freq": "frequency", "frequency": "frequency", "f_freq": "frequency",
    "hz": "frequency",

    "wl": "wavelength", "wavelength": "wavelength", "lambda_wave": "wavelength",

    "z_ac": "acoustic_impedance", "acoustic_impedance": "acoustic_impedance",

    "tl": "transmission_loss", "transmission_loss": "transmission_loss",

    "alpha_ac": "absorption_coefficient", "absorption_coefficient": "absorption_coefficient",
    "abs_coeff": "absorption_coefficient",

    "r_ac": "reflection_coefficient", "reflection_coefficient": "reflection_coefficient",

    "rt60": "reverberation_time", "reverberation_time": "reverberation_time",
    "t60": "reverberation_time",

    "q_ac": "quality_factor", "quality_factor": "quality_factor",
    "q_factor": "quality_factor",

    "il": "insertion_loss", "insertion_loss": "insertion_loss",

    "nr": "noise_reduction", "noise_reduction": "noise_reduction",

    # ── Electromagnetics ──────────────────────────────────────────────────────
    "e_field": "electric_field", "electric_field": "electric_field", "E": "electric_field",

    "b_field": "magnetic_field", "magnetic_field": "magnetic_field",
    "H": "magnetic_field", "h_field": "magnetic_field",

    "v_elec": "electric_potential", "electric_potential": "electric_potential",
    "voltage": "electric_potential", "volt": "electric_potential",

    "j": "current_density", "current_density": "current_density",

    "pd": "power_density", "power_density": "power_density",

    "perm_r": "permittivity", "permittivity": "permittivity", "eps_r": "permittivity",

    "mu_r": "permeability", "permeability": "permeability",

    "sigma_e": "conductivity", "conductivity": "conductivity",
    "electrical_conductivity": "conductivity",

    "rho_e": "resistivity", "resistivity": "resistivity",
    "electrical_resistivity": "resistivity",

    "z": "impedance", "impedance": "impedance",

    "delta_skin": "skin_depth", "skin_depth": "skin_depth",

    "eta_rad": "radiation_efficiency", "radiation_efficiency": "radiation_efficiency",

    "rl": "return_loss", "return_loss": "return_loss", "s11": "return_loss",

    "vswr_val": "vswr", "vswr": "vswr",

    "pf": "power_factor", "power_factor": "power_factor",

    # ── Geomechanics ──────────────────────────────────────────────────────────
    "sigma_eff": "effective_stress", "effective_stress": "effective_stress",
    "sigma_prime": "effective_stress",

    "u_pore": "pore_pressure", "pore_pressure": "pore_pressure",
    "u_water": "pore_pressure",

    "k_perm": "permeability", "perm": "permeability",

    "n_por": "porosity", "por": "porosity", "porosity": "porosity",
    "void_fraction_geo": "porosity",

    "e_void": "void_ratio", "void_ratio": "void_ratio",

    "sr": "degree_of_saturation", "degree_of_saturation": "degree_of_saturation",
    "saturation": "degree_of_saturation",

    "su_shear": "shear_strength", "shear_strength": "shear_strength",
    "undrained_strength": "shear_strength",

    "c_coh": "cohesion", "cohesion": "cohesion",

    "phi_angle": "friction_angle", "friction_angle": "friction_angle",
    "angle_of_friction": "friction_angle",

    "delta_v": "settlement", "settlement": "settlement",
    "consolidation_settlement": "settlement",

    "fs": "slope_stability_factor", "slope_stability_factor": "slope_stability_factor",
    "factor_of_safety_slope": "slope_stability_factor",

    "pl": "liquefaction_potential", "liquefaction_potential": "liquefaction_potential",

    "k0": "earth_pressure_coefficient", "earth_pressure_coefficient": "earth_pressure_coefficient",

    # ── Materials ─────────────────────────────────────────────────────────────
    "ys": "yield_strength", "yield_strength": "yield_strength",
    "sigma_y": "yield_strength",

    "d_grain": "grain_size", "grain_size": "grain_size",
    "grain_diameter": "grain_size",

    "rho_disl": "dislocation_density", "dislocation_density": "dislocation_density",

    "k_wear": "wear_rate", "wear_rate": "wear_rate",

    "cte": "thermal_expansion", "thermal_expansion": "thermal_expansion",
    "alpha_cte": "thermal_expansion",

    "tm": "melting_point", "melting_point": "melting_point",
    "t_melt": "melting_point",

    "hv": "hardness", "hardness": "hardness",
    "vickers_hardness": "hardness", "brinell_hardness": "hardness",

    # ── Tribology ─────────────────────────────────────────────────────────────
    "mu_fric": "friction_coefficient", "friction_coefficient": "friction_coefficient",
    "coefficient_of_friction": "friction_coefficient", "cof": "friction_coefficient",

    "h_film": "film_thickness", "film_thickness": "film_thickness",
    "oil_film_thickness": "film_thickness",

    "lambda_tr": "lambda_ratio", "lambda_ratio": "lambda_ratio",
    "film_parameter": "lambda_ratio",

    "p_hertz": "hertz_pressure", "hertz_pressure": "hertz_pressure",

    "ra_rough": "surface_roughness", "surface_roughness": "surface_roughness",
    "rms_roughness": "surface_roughness", "roughness": "surface_roughness",

    # ── Nuclear ───────────────────────────────────────────────────────────────
    "phi_n": "neutron_flux", "neutron_flux": "neutron_flux", "flux": "neutron_flux",

    "keff": "criticality_factor", "k_eff": "criticality_factor",
    "criticality_factor": "criticality_factor", "multiplication_factor": "criticality_factor",

    "rho_react": "reactivity", "reactivity": "reactivity",

    "bu": "burnup", "burnup": "burnup", "fuel_burnup": "burnup",

    "enrich": "enrichment", "enrichment": "enrichment",
    "u235_enrichment": "enrichment",

    "alpha_d": "doppler_coefficient", "doppler_coefficient": "doppler_coefficient",

    "beta_eff": "delayed_neutron_fraction", "delayed_neutron_fraction": "delayed_neutron_fraction",
    "beta": "delayed_neutron_fraction",

    "t_fuel": "fuel_temperature", "fuel_temperature": "fuel_temperature",
    "t_clad": "cladding_temperature", "cladding_temperature": "cladding_temperature",

    # ── Plasma ────────────────────────────────────────────────────────────────
    "te": "electron_temperature", "electron_temperature": "electron_temperature",
    "t_electron": "electron_temperature",

    "ti_plasma": "ion_temperature", "ion_temperature": "ion_temperature",
    "t_ion": "ion_temperature",

    "ne": "electron_density", "electron_density": "electron_density",
    "n_e": "electron_density",

    "beta_plasma": "plasma_beta", "plasma_beta": "plasma_beta",
    "normalized_pressure": "plasma_beta",

    "va": "alfven_speed", "alfven_speed": "alfven_speed",
    "alfven_velocity": "alfven_speed",

    "lambda_d": "debye_length", "debye_length": "debye_length",
    "debye_screening_length": "debye_length",

    "omega_p": "plasma_frequency", "plasma_frequency": "plasma_frequency",

    "tau_e": "confinement_time", "confinement_time": "confinement_time",
    "energy_confinement_time": "confinement_time",

    "q_plasma": "q_factor", "q_factor": "q_factor",
    "fusion_gain": "q_factor",

    # ── Chemical ─────────────────────────────────────────────────────────────
    "c_conc": "concentration", "conc": "concentration",
    "concentration": "concentration", "molar_concentration": "concentration",

    "r_rxn": "reaction_rate", "reaction_rate": "reaction_rate",
    "rate": "reaction_rate",

    "x": "conversion", "conversion": "conversion", "x_conv": "conversion",

    "sel": "selectivity", "selectivity": "selectivity",

    "y_yield": "yield_chemical", "yield_chem": "yield_chemical",
    "yield_chemical": "yield_chemical",

    "ph_val": "ph", "ph": "ph",

    "ea": "activation_energy", "activation_energy": "activation_energy",
    "e_act": "activation_energy",

    "keq": "equilibrium_constant", "equilibrium_constant": "equilibrium_constant",
    "k_eq": "equilibrium_constant",

    "da": "damkohler_number", "damkohler_number": "damkohler_number",
    "damkohler": "damkohler_number",

    "eta_eff": "effectiveness_factor", "effectiveness_factor": "effectiveness_factor",
    "thiele_eff": "effectiveness_factor",

    "delta_h_rxn": "reaction_enthalpy", "reaction_enthalpy": "reaction_enthalpy",
    "heat_of_reaction": "reaction_enthalpy",

    # ── Hydrodynamics ─────────────────────────────────────────────────────────
    "hs": "significant_wave_height", "significant_wave_height": "significant_wave_height",
    "h_s": "significant_wave_height",

    "hw": "wave_height", "wave_height": "wave_height", "h_wave": "wave_height",

    "tw": "wave_period", "wave_period": "wave_period", "t_wave": "wave_period",
    "tp": "peak_period", "peak_period": "peak_period",

    "lw": "wave_length", "wave_length": "wave_length", "l_wave": "wave_length",

    "cw": "wave_speed", "wave_speed": "wave_speed", "c_wave": "wave_speed",

    "d_water": "water_depth", "water_depth": "water_depth", "depth": "water_depth",

    "uc": "current_velocity", "current_velocity": "current_velocity",

    "kc": "keulegan_carpenter", "keulegan_carpenter": "keulegan_carpenter",

    "rao": "response_amplitude", "response_amplitude": "response_amplitude",

    "t_moor": "mooring_tension", "mooring_tension": "mooring_tension",

    "ma_add": "added_mass", "added_mass": "added_mass",

    # ── Meteorology ───────────────────────────────────────────────────────────
    "t_air": "temperature", "air_temp": "temperature",
    "p_atm": "pressure", "atm_pressure": "pressure",
    "ws": "wind_speed", "wind_speed": "wind_speed",
    "rh": "humidity", "relative_humidity": "humidity", "humidity": "humidity",
    "precip": "precipitation", "precipitation": "precipitation", "rain": "precipitation",
    "vis": "visibility", "visibility": "visibility",
    "cc": "cloud_cover", "cloud_cover": "cloud_cover", "clouds": "cloud_cover",
    "td": "dew_point", "dew_point": "dew_point", "dewpoint": "dew_point",
    "wd": "wind_direction", "wind_direction": "wind_direction", "wdir": "wind_direction",
    "ghi": "solar_radiation", "solar_radiation": "solar_radiation", "irradiance": "solar_radiation",
    "uvi": "uv_index", "uv_index": "uv_index",

    # ── Biomechanics ──────────────────────────────────────────────────────────
    "sigma_bone": "bone_stress", "bone_stress": "bone_stress",
    "sigma_cart": "cartilage_stress", "cartilage_stress": "cartilage_stress",
    "f_muscle": "muscle_force", "muscle_force": "muscle_force",
    "f_joint": "joint_contact_force", "joint_contact_force": "joint_contact_force",
    "grf": "ground_reaction_force", "ground_reaction_force": "ground_reaction_force",
    "v_gait": "gait_speed", "gait_speed": "gait_speed", "walking_speed": "gait_speed",
    "hr": "heart_rate", "heart_rate": "heart_rate", "bpm": "heart_rate",
    "bp": "blood_pressure", "blood_pressure": "blood_pressure", "sbp": "blood_pressure",
    "vo2": "oxygen_consumption", "oxygen_consumption": "oxygen_consumption",
    "bmi": "body_mass_index", "body_mass_index": "body_mass_index",
    "p_met": "metabolic_power", "metabolic_power": "metabolic_power",
    "frac_risk": "fracture_risk", "fracture_risk": "fracture_risk",

    # ── Astrophysics ──────────────────────────────────────────────────────────
    "lum": "luminosity", "luminosity": "luminosity", "l_star": "luminosity",
    "t_star": "temperature",
    "rho_star": "density",
    "z_red": "redshift", "redshift": "redshift",
    "m_star": "mass", "mass": "mass",
    "r_star": "radius", "radius": "radius",
    "v_esc": "escape_velocity", "escape_velocity": "escape_velocity",
    "rs": "schwarzschild_radius", "schwarzschild_radius": "schwarzschild_radius",
    "feh": "metallicity", "metallicity": "metallicity",

    # ── Cryogenics ────────────────────────────────────────────────────────────
    "t_cryo": "temperature",
    "p_cryo": "pressure",
    "rho_cryo": "density",
    "k_cryo": "thermal_conductivity",
    "mu_cryo": "viscosity",
    "gamma_cryo": "surface_tension",
    "p_vap": "vapor_pressure", "vapor_pressure": "vapor_pressure",
    "l_lat": "latent_heat", "latent_heat": "latent_heat",
    "tb": "boiling_point", "boiling_point": "boiling_point",
    "tc": "critical_temperature", "critical_temperature": "critical_temperature",
    "pc": "critical_pressure", "critical_pressure": "critical_pressure",
    "sf_frac": "superfluid_fraction", "superfluid_fraction": "superfluid_fraction",
    "e_quench": "quench_energy", "quench_energy": "quench_energy",
    "r_kap": "kapitza_resistance", "kapitza_resistance": "kapitza_resistance",

    # ── Control / general ─────────────────────────────────────────────────────
    "time": "time", "t_sim": "time", "timestep": "time",
    "iter": "iterations", "iterations": "iterations", "n_iter": "iterations",
    "res": "continuity_residual", "residual": "continuity_residual",
    "cfl": "cfl_number", "cfl_number": "cfl_number",
}


def _normalize_col(col: str) -> str:
    """Clean a column name for alias lookup."""
    return col.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def _coerce_numeric(series: pd.Series) -> pd.Series:
    """Convert a column to numeric where possible, leaving it untouched otherwise."""
    converted = pd.to_numeric(series, errors="coerce")
    return converted if converted.notna().any() else series


class DataIngester:
    def ingest(self, data, format_hint=None, filename=None):
        metadata = {"original_format": format_hint, "filename": filename,
                    "columns_renamed": {}, "columns_dropped": [], "rows_ingested": 0}

        fmt = self._detect(data, format_hint, filename)
        metadata["detected_format"] = fmt

        if fmt == "csv":           df = self._csv(data)
        elif fmt == "json":        df = self._json(data)
        elif fmt == "yaml":        df = self._yaml(data)
        elif fmt == "toml":        df = self._toml(data)
        elif fmt in ("txt", "md"): df = self._text(data)
        elif fmt == "vtk":         df = self._vtk(data)
        elif fmt == "numpy":       df = self._numpy(data)
        elif fmt == "openfoam":    df = self._openfoam(data)
        elif fmt == "dataframe":   df = data.copy()
        else:                      raise ValueError(f"Unsupported format: {fmt}")

        df, renamed = self._normalize(df)
        metadata["columns_renamed"] = renamed

        numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        dropped = [c for c in df.columns if c not in numeric]
        df = df[numeric].reset_index(drop=True)
        metadata.update({"columns_dropped": dropped, "rows_ingested": len(df),
                         "columns_found": list(df.columns)})
        return df, metadata

    def _detect(self, data, hint, filename):
        if isinstance(data, pd.DataFrame): return "dataframe"
        if isinstance(data, np.ndarray):   return "numpy"
        if hint: return hint.lower()
        if filename:
            ext = Path(filename).suffix.lower()
            return {
                ".csv": "csv", ".json": "json", ".vtk": "vtk", ".npy": "numpy", ".npz": "numpy",
                ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".sim": "yaml",
                ".txt": "txt", ".md": "md", ".markdown": "md",
            }.get(ext, "csv")
        if isinstance(data, (dict, list)): return "json"
        if isinstance(data, (str, bytes)):
            text = data.decode() if isinstance(data, bytes) else data
            stripped = text.strip()
            if stripped.startswith(("{", "[")): return "json"
            if "vtk datafile" in text.lower():     return "vtk"
            if stripped.startswith("FoamFile"): return "openfoam"
            if re.match(r"^[A-Za-z0-9_.\-\[\]\"' ]+\s*=", stripped) and "\n---" not in stripped and ":" not in stripped.split("\n", 1)[0]:
                return "toml"
            if re.search(r"^[A-Za-z][\w \-]*:\s*(.+)?$", stripped, re.MULTILINE) and not stripped.startswith("|") and "," not in stripped.split("\n", 1)[0]:
                # Looks like key: value structure — could be YAML or loose text/markdown.
                if stripped.startswith("#") or "**" in stripped or stripped.count("|") > 2:
                    return "md"
                try:
                    yaml.safe_load(stripped)
                    return "yaml"
                except yaml.YAMLError:
                    return "txt"
            return "csv"
        return "csv"

    def _csv(self, data):
        if isinstance(data, bytes): data = data.decode("utf-8", errors="replace")
        return pd.read_csv(io.StringIO(data) if isinstance(data, str) else data)

    def _json(self, data):
        if isinstance(data, (str, bytes)): data = json.loads(data)
        if isinstance(data, list):         return pd.DataFrame(data)
        for key in ("trials","results","data"):
            if key in data: return pd.DataFrame(data[key])
        return pd.DataFrame([data])

    def _yaml(self, data):
        if isinstance(data, bytes): data = data.decode("utf-8", errors="replace")
        parsed = yaml.safe_load(data)
        if isinstance(parsed, list):
            return pd.DataFrame(parsed)
        if isinstance(parsed, dict):
            for key in ("trials", "results", "data"):
                if key in parsed and isinstance(parsed[key], list):
                    return pd.DataFrame(parsed[key])
            return pd.DataFrame([parsed])
        raise ValueError("YAML document must be a list of trials or a dict containing one")

    def _toml(self, data):
        if isinstance(data, str): data = data.encode("utf-8")
        parsed = tomllib.loads(data.decode("utf-8")) if isinstance(data, bytes) else tomllib.load(data)
        for key in ("trials", "results", "data"):
            if key in parsed and isinstance(parsed[key], list):
                return pd.DataFrame(parsed[key])
        # TOML array-of-tables at the top level, e.g. [[trial]] blocks.
        for v in parsed.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return pd.DataFrame(v)
        return pd.DataFrame([parsed])

    def _text(self, data):
        """Parse loose TXT/Markdown into trial records.

        Supports three shapes, tried in order: a Markdown/pipe table, a CSV-like
        whitespace table, and free-form "key: value" or "key = value" blocks
        (one trial per blank-line-separated paragraph — the common shape when
        someone pastes simulation output or writes results in prose).
        """
        if isinstance(data, bytes): data = data.decode("utf-8", errors="replace")
        lines = [ln for ln in data.split("\n") if ln.strip() and not ln.strip().startswith("#")]

        table_lines = [ln for ln in lines if ln.strip().startswith("|")]
        if len(table_lines) >= 2:
            rows = [
                [c.strip() for c in ln.strip().strip("|").split("|")]
                for ln in table_lines
                if not re.match(r"^[\s:|-]+$", ln.strip().strip("|"))
            ]
            if len(rows) >= 2:
                header, *body = rows
                return pd.DataFrame(body, columns=header).apply(_coerce_numeric)

        kv_pattern = re.compile(r"^\s*[\w][\w \-/%]*\s*[:=]\s*.+$")
        if lines and all(kv_pattern.match(ln) or ln.strip() == "" for ln in lines[:20]):
            records, current = [], {}
            for ln in data.split("\n"):
                if not ln.strip():
                    if current: records.append(current); current = {}
                    continue
                m = re.match(r"^\s*([\w][\w \-/%]*?)\s*[:=]\s*(.+?)\s*$", ln)
                if m:
                    key = _normalize_col(m.group(1))
                    val = m.group(2).strip().strip('"\'')
                    current[key] = val
            if current: records.append(current)
            if records:
                return pd.DataFrame(records).apply(_coerce_numeric)

        # Whitespace/CSV-like table fallback (first line = header).
        try:
            return pd.read_csv(io.StringIO(data), sep=r"\s+|,", engine="python")
        except Exception as e:
            raise ValueError("Could not parse text/markdown input as trial records") from e

    def _numpy(self, data):
        if isinstance(data, (str, bytes, Path)):
            arr = np.load(data, allow_pickle=True)
            if hasattr(arr, "files"): arr = arr[arr.files[0]]
        else:
            arr = np.array(data)
        if arr.ndim == 1: arr = arr.reshape(-1, 1)
        return pd.DataFrame(arr, columns=[f"col_{i}" for i in range(arr.shape[1])])

    def _vtk(self, data):
        if isinstance(data, bytes): data = data.decode("utf-8", errors="replace")
        rows = {}; current = None
        for line in data.split("\n"):
            line = line.strip()
            if line.upper().startswith("SCALARS"):
                current = line.split()[1]; rows[current] = []
            elif line.upper().startswith("LOOKUP_TABLE"): continue
            elif current and line and not line.startswith("#"):
                try: rows[current].extend([float(v) for v in line.split()])
                except ValueError: current = None
        if not rows: raise ValueError("No scalar fields in VTK file")
        max_len = max(len(v) for v in rows.values())
        for k in rows:
            rows[k] = (rows[k] + [np.nan]*max_len)[:max_len]
        return pd.DataFrame(rows)

    def _openfoam(self, data):
        if isinstance(data, bytes): data = data.decode("utf-8", errors="replace")
        lines = []
        for line in data.split("\n"):
            if line.strip().startswith("#"):
                header = re.sub(r"[#()]", "", line)
                lines.insert(0, header)
                continue
            clean = re.sub(r"[()]", " ", line)
            if clean.strip(): lines.append(clean)
        try:
            return pd.read_csv(io.StringIO("\n".join(lines)), sep=r"\s+", engine="python")
        except Exception as e:
            raise ValueError("Could not parse OpenFOAM postProcessing CSV format") from e

    def _normalize(self, df):
        rename = {}
        for col in df.columns:
            norm = _normalize_col(col)
            canonical = COLUMN_ALIASES.get(norm) or COLUMN_ALIASES.get(col.lower())
            if canonical and canonical != col:
                rename[col] = canonical
        return df.rename(columns=rename), rename
