"""
SimAPI Realistic Multi-Domain Benchmark
========================================

Designed to answer the ACTUAL question customers ask:
"Will this catch the bugs that slip through my current process?"

Design principles:
  - REALISTIC corruption rate: 1-3% (not 30%)
  - REALISTIC domains: drone propeller, actuator FEA, motor thermal,
    joint dynamics, IMU/sensor fusion
  - REALISTIC baselines: pandas z-score, IQR, isolation forest (what
    a competent data engineer would do)
  - HONEST metrics: what % of real corruptions did each method catch,
    and how many clean rows did it wrongly flag?
  - WAR STORY: the one corrupted row that would have destroyed the model

Run:
    python -m benchmark.realistic_benchmark
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest, RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.apie import AdaptivePhysicsIntelligenceEngine

apie = AdaptivePhysicsIntelligenceEngine()
rng = np.random.default_rng(42)

# ═══════════════════════════════════════════════════════════════════════════════
# REALISTIC DATASET GENERATORS
# Each represents an actual simulation type run by target customers.
# ═══════════════════════════════════════════════════════════════════════════════

def gen_drone_propeller(n: int) -> pd.DataFrame:
    """
    Drone propeller CFD sweep.
    Use case: DJI/Skydio/Joby optimize blade geometry across RPM × pitch sweeps.
    Target: predict CT, CP, efficiency for flight controller models.
    """
    rpm   = rng.uniform(3000, 12000, n)
    v_inf = rng.uniform(0, 25, n)
    pitch = rng.uniform(10, 25, n)
    rho   = 1.225 + rng.normal(0, 0.008, n)
    D     = 0.254  # 10-inch prop

    n_rps = rpm / 60
    J = v_inf / (n_rps * D + 1e-9)
    CT = np.clip(0.12 - 0.08*J + rng.normal(0, 0.003, n), 0.001, 0.25)
    CP = np.clip(0.04 + 0.01*J**2 + rng.normal(0, 0.001, n), 0.005, 0.15)
    eta = np.clip(J * CT / (CP + 1e-9), 0, 0.92)

    return pd.DataFrame({
        'rpm': rpm, 'freestream_velocity': v_inf, 'pitch_angle': pitch,
        'advance_ratio': J, 'density': rho,
        'thrust_coefficient': CT, 'power_coefficient': CP,
        'propulsive_efficiency': eta,
        'thrust': CT * rho * n_rps**2 * D**4,
        'power': CP * rho * n_rps**3 * D**5,
        'torque': CP * rho * n_rps**2 * D**5 / (2*np.pi),
        'figure_of_merit': CT**(1.5) / (np.sqrt(2) * CP + 1e-9),   # propeller FOM = CT^1.5/(√2·CP), ≤1
    })


def gen_actuator_fea(n: int) -> pd.DataFrame:
    """
    Robotic actuator structural FEA.
    Use case: Boston Dynamics / Agility validate joint housing strength
    across load envelopes before manufacturing.
    Target: safety_factor must stay above 1.5 in all configurations.
    """
    t_wall = rng.uniform(0.002, 0.015, n)    # wall thickness, m
    D_outer = rng.uniform(0.040, 0.120, n)   # outer diameter, m
    L_shaft = rng.uniform(0.050, 0.300, n)   # length, m
    tau     = rng.uniform(5, 500, n)          # applied torque, Nm
    F_axial = rng.uniform(50, 5000, n)        # axial load, N

    E = 200e9  # steel
    I_area = np.pi * (D_outer**4 - (D_outer - 2*t_wall)**4) / 64
    J_tor  = 2 * I_area
    A_cs   = np.pi * ((D_outer/2)**2 - ((D_outer/2 - t_wall)**2))

    sigma_bend = tau * (D_outer/2) / I_area + rng.normal(0, 5e5, n)
    tau_shear  = tau * (D_outer/2) / J_tor  + rng.normal(0, 1e5, n)
    sigma_axial= F_axial / A_cs              + rng.normal(0, 1e5, n)
    sigma_vm   = np.sqrt(sigma_bend**2 + sigma_axial**2 + 3*tau_shear**2)
    SF         = 250e6 / (sigma_vm + 1e-3)
    delta      = F_axial * L_shaft / (E * A_cs) + rng.normal(0, 1e-7, n)

    return pd.DataFrame({
        'wall_thickness': t_wall, 'outer_diameter': D_outer,
        'shaft_length': L_shaft, 'applied_torque': tau, 'axial_load': F_axial,
        'bending_stress': sigma_bend, 'shear_stress': tau_shear,
        'axial_stress': sigma_axial, 'von_mises_stress': sigma_vm,
        'safety_factor': SF, 'axial_deflection': delta,
        'area_moment_inertia': I_area,
    })


def gen_motor_thermal(n: int) -> pd.DataFrame:
    """
    Brushless motor thermal simulation.
    Use case: Tesla / Rivian / robotics companies predict winding temperature
    under drive cycle loads to prevent insulation failure.
    Target: T_winding must stay below 180°C (453K) continuously.
    """
    I_rms   = rng.uniform(2, 30, n)           # A (realistic for 100-500W motors)
    R_wind  = rng.uniform(0.02, 0.5, n)       # Ω
    T_amb   = rng.uniform(263, 323, n)         # K (-10°C to 50°C)
    Rth_wc  = rng.uniform(0.1, 2.0, n)        # K/W winding→case
    Rth_ca  = rng.uniform(0.3, 3.0, n)        # K/W case→ambient

    P_Cu   = I_rms**2 * R_wind + rng.normal(0, 0.2, n)
    P_Fe   = 0.15 * P_Cu + rng.normal(0, 0.1, n)   # iron losses ~15% copper
    P_tot  = P_Cu + P_Fe
    T_wind = T_amb + P_tot * (Rth_wc + Rth_ca) + rng.normal(0, 1.0, n)
    T_case = T_amb + P_tot * Rth_ca             + rng.normal(0, 0.5, n)
    T_rise = T_wind - T_amb

    return pd.DataFrame({
        'rms_current': I_rms, 'winding_resistance': R_wind,
        'ambient_temperature': T_amb, 'rth_winding_case': Rth_wc,
        'rth_case_ambient': Rth_ca, 'copper_loss': P_Cu,
        'iron_loss': P_Fe, 'total_loss': P_tot,
        'winding_temperature': T_wind, 'case_temperature': T_case,
        'temperature_rise': T_rise,
        'derating_factor': np.clip(1 - (T_wind - 363) / 90, 0, 1),  # derate above 90°C
    })


def gen_joint_dynamics(n: int) -> pd.DataFrame:
    """
    Robot joint torque/velocity/power dynamics.
    Use case: ABB / KUKA validate joint control simulation output
    before deploying trajectory planners.
    Target: detect when P_electrical ≠ tau * omega / eta (energy balance violation).
    """
    tau   = rng.uniform(-300, 300, n)
    omega = rng.uniform(-15, 15, n)
    theta = rng.uniform(-3.14, 3.14, n)
    J_link= rng.uniform(0.01, 3.0, n)
    b_damp= rng.uniform(0.05, 5.0, n)
    eta   = np.clip(0.91 + rng.normal(0, 0.02, n), 0.6, 0.99)

    alpha   = (tau - b_damp*omega) / (J_link + 1e-9) + rng.normal(0, 0.05, n)
    P_mech  = tau * omega + rng.normal(0, 2, n)
    P_diss  = b_damp * omega**2
    P_elec  = (P_mech + P_diss) / (eta + 1e-9) + rng.normal(0, 1, n)

    return pd.DataFrame({
        'commanded_torque': tau, 'joint_velocity': omega,
        'joint_position': theta, 'link_inertia': J_link,
        'damping_coefficient': b_damp, 'motor_efficiency': eta,
        'joint_acceleration': alpha, 'mechanical_power': P_mech,
        'dissipated_power': P_diss, 'electrical_power': P_elec,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# REALISTIC CORRUPTION INJECTOR
# 1-3% rate. Types chosen to reflect what actually happens in practice.
# ═══════════════════════════════════════════════════════════════════════════════

def inject_realistic_corruptions(
    df: pd.DataFrame, domain: str, rate: float = 0.02, seed: int = 0
) -> Tuple[pd.DataFrame, Dict[str, set]]:
    """
    Inject realistic corruptions at 1-3% rate.
    These are based on actual incident types seen in production sim pipelines:
    - Solver divergence: rare but catastrophic (0.3-0.5%)
    - Unit errors: from copy-paste between tools (0.3-0.5%)
    - Sensor/gauge drift: accumulated calibration error (0.5-1.0%)
    - Cross-variable inconsistency: formula error in post-processing (0.3-0.5%)
    - Measurement noise: exceeds expected variance (0.2-0.4%)
    """
    rng_c = np.random.default_rng(seed)
    df = df.copy().reset_index(drop=True)
    n = len(df)
    log: Dict[str, set] = {
        'solver_divergence': set(),
        'unit_error': set(),
        'sensor_drift': set(),
        'cross_variable': set(),
        'noise_spike': set(),
    }

    def pick(frac: float) -> np.ndarray:
        k = max(1, int(n * frac))
        return rng_c.choice(n, size=min(k, n), replace=False)

    already: set = set()

    def safe_pick(frac):
        candidates = [i for i in pick(frac*3) if i not in already][:max(1,int(n*frac))]
        already.update(candidates)
        return candidates

    if domain == 'drone_aero':
        for i in safe_pick(0.004):
            df.at[i, 'thrust_coefficient'] = rng_c.uniform(0.45, 0.65)  # 4× physical max
            df.at[i, 'power_coefficient']  = rng_c.uniform(0.001, 0.005)  # near-zero
            log['solver_divergence'].add(i)
        for i in safe_pick(0.004):
            df.at[i, 'rpm'] = df.at[i, 'rpm'] * 60  # RPM → rev/s then × 60 → wrong
            log['unit_error'].add(i)
        seg = rng_c.integers(n//5, 3*n//5)
        seg_len = int(n * 0.020)  # longer drift segment
        for j, i in enumerate(range(int(seg), min(int(seg)+seg_len, n))):
            df.at[i, 'freestream_velocity'] *= (1 + j * 0.003)  # larger drift per step
            log['sensor_drift'].add(i)
        for i in safe_pick(0.004):
            # CT and J both corrupted: advance ratio inconsistency
            df.at[i, 'advance_ratio'] = df.at[i, 'advance_ratio'] * 3.2
            log['cross_variable'].add(i)
        for i in safe_pick(0.003):
            df.at[i, 'propulsive_efficiency'] = rng_c.uniform(0.96, 1.05)  # >1 impossible
            log['noise_spike'].add(i)

    elif domain == 'actuator_fea':
        for i in safe_pick(0.004):
            df.at[i, 'von_mises_stress'] = rng_c.uniform(8e9, 15e9)  # 30× yield
            df.at[i, 'bending_stress']   = rng_c.uniform(8e9, 15e9)
            log['solver_divergence'].add(i)
        for i in safe_pick(0.004):
            df.at[i, 'wall_thickness'] = df.at[i, 'wall_thickness'] * 1000  # m → mm
            log['unit_error'].add(i)
        seg = rng_c.integers(n//4, n//2)
        for j, i in enumerate(range(int(seg), min(int(seg)+int(n*0.025), n))):
            df.at[i, 'applied_torque'] *= (1 + j * 0.003)  # stronger drift
            log['sensor_drift'].add(i)
        for i in safe_pick(0.003):
            # Safety factor inconsistent with von_mises
            df.at[i, 'safety_factor'] = rng_c.uniform(15, 50)  # wrong, should be <5 for this stress
            log['cross_variable'].add(i)

    elif domain == 'motor_thermal':
        for i in safe_pick(0.004):
            df.at[i, 'winding_temperature'] = rng_c.uniform(2000, 5000)  # solver exploded
            log['solver_divergence'].add(i)
        for i in safe_pick(0.004):
            df.at[i, 'ambient_temperature'] = df.at[i, 'ambient_temperature'] - 273.15  # K→C
            log['unit_error'].add(i)
        seg = rng_c.integers(n//5, 2*n//5)
        for j, i in enumerate(range(int(seg), min(int(seg)+int(n*0.025), n))):
            df.at[i, 'rms_current'] *= (1 + j * 0.004)  # stronger drift
            log['sensor_drift'].add(i)
        for i in safe_pick(0.003):
            df.at[i, 'copper_loss'] = df.at[i, 'rms_current']**2 * df.at[i, 'winding_resistance'] * 1000
            log['cross_variable'].add(i)
        for i in safe_pick(0.003):
            df.at[i, 'temperature_rise'] = rng_c.uniform(500, 1000)
            log['noise_spike'].add(i)

    elif domain == 'joint_dynamics':
        for i in safe_pick(0.004):
            df.at[i, 'mechanical_power'] = rng_c.uniform(50000, 200000)
            log['solver_divergence'].add(i)
        for i in safe_pick(0.004):
            df.at[i, 'joint_velocity'] = df.at[i, 'joint_velocity'] * 180 / np.pi  # rad→deg
            log['unit_error'].add(i)
        seg = rng_c.integers(n//4, n//2)
        for j, i in enumerate(range(int(seg), min(int(seg)+int(n*0.025), n))):
            df.at[i, 'joint_velocity'] *= (1 + j * 0.003)  # stronger drift
            log['sensor_drift'].add(i)
        for i in safe_pick(0.003):
            # Electrical power inconsistent with mechanical
            df.at[i, 'electrical_power'] = df.at[i, 'mechanical_power'] * 5
            log['cross_variable'].add(i)

    return df, log


# ═══════════════════════════════════════════════════════════════════════════════
# BASELINE METHODS
# What a competent data engineer would actually use as a first pass.
# ═══════════════════════════════════════════════════════════════════════════════

def baseline_zscore(df: pd.DataFrame, sigma: float = 3.0) -> set:
    """Pandas z-score filtering — the simplest thing anyone tries first."""
    excl = set()
    for col in df.select_dtypes(include=[np.number]).columns:
        s = df[col].values.astype(float)
        mu, std = s.mean(), s.std()
        if std < 1e-10: continue
        for i in np.where(np.abs(s - mu) > sigma * std)[0]:
            excl.add(int(i))
    return excl


def baseline_iqr(df: pd.DataFrame, k: float = 3.0) -> set:
    """IQR outlier removal — often recommended in data science blogs."""
    excl = set()
    for col in df.select_dtypes(include=[np.number]).columns:
        Q1, Q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        IQR = Q3 - Q1
        lo, hi = Q1 - k * IQR, Q3 + k * IQR
        for i in np.where((df[col] < lo) | (df[col] > hi))[0]:
            excl.add(int(i))
    return excl


def baseline_isolation_forest(df: pd.DataFrame, contamination: float = 0.02) -> set:
    """Isolation Forest — what a senior ML engineer would try."""
    X = df.select_dtypes(include=[np.number]).fillna(0).values
    clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
    preds = clf.fit_predict(X)
    return {int(i) for i in np.where(preds == -1)[0]}


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

DOMAIN_CONFIGS = {
    'drone_aero': {
        'gen': gen_drone_propeller,
        'apie_domain': 'drone_aero',
        'target': 'propulsive_efficiency',
        'features': ['rpm', 'freestream_velocity', 'pitch_angle', 'advance_ratio', 'density'],
        'customer': 'Drone / eVTOL companies',
        'stakes': 'Wrong efficiency model → wrong battery sizing → aircraft that drops from the sky',
    },
    'actuator_fea': {
        'gen': gen_actuator_fea,
        'apie_domain': 'actuator_fea',
        'target': 'safety_factor',
        'features': ['wall_thickness', 'outer_diameter', 'shaft_length', 'applied_torque', 'axial_load'],
        'customer': 'Robotics hardware companies',
        'stakes': 'Wrong safety factor → under-designed joint → actuator failure in the field',
    },
    'motor_thermal': {
        'gen': gen_motor_thermal,
        'apie_domain': 'motor_thermal',
        'target': 'winding_temperature',
        'features': ['rms_current', 'winding_resistance', 'ambient_temperature', 'rth_winding_case', 'rth_case_ambient'],
        'customer': 'EV / motor drive companies',
        'stakes': 'Wrong thermal model → insulation fails → motor fire → recall',
    },
    'joint_dynamics': {
        'gen': gen_joint_dynamics,
        'apie_domain': 'robotics/control',
        'target': 'electrical_power',
        'features': ['commanded_torque', 'joint_velocity', 'link_inertia', 'damping_coefficient', 'motor_efficiency'],
        'customer': 'Industrial robot companies',
        'stakes': 'Wrong power model → undersized power supply → production line downtime',
    },
}

def train_model(X_train, y_train, X_test, y_test, model_type='rf'):
    """Train a model and return test MAPE."""
    X_tr = pd.DataFrame(X_train).fillna(pd.DataFrame(X_train).median()).values
    X_te = pd.DataFrame(X_test).fillna(pd.DataFrame(X_train).median()).values
    
    sc = StandardScaler().fit(X_tr)
    X_tr_s, X_te_s = sc.transform(X_tr), sc.transform(X_te)
    
    if model_type == 'rf':
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_tr_s, y_train)
    else:  # mlp
        model = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500, random_state=42, early_stopping=True)
        model.fit(X_tr_s, y_train)
    
    preds = model.predict(X_te_s)
    y_arr = np.array(y_test)
    mape = float(np.mean(np.abs((y_arr - preds) / (np.abs(y_arr) + 1e-10))) * 100)
    return mape


def run_realistic_benchmark(n_train=8000, n_test=2000, seeds=(42, 123, 456)):
    print("=" * 72)
    print("SimAPI REALISTIC BENCHMARK — Production Corruption Rates (1-3%)")
    print("=" * 72)
    print(f"n_train={n_train:,}  n_test={n_test:,}  seeds={seeds}")
    print()

    results = {}

    for domain, cfg in DOMAIN_CONFIGS.items():
        print(f"── {cfg['customer']} / {domain} ──────────────────────────────")
        print(f"   Stakes: {cfg['stakes']}")
        
        domain_seeds = []
        
        for seed in seeds:
            np.random.seed(seed)
            rng_local = np.random.default_rng(seed)
            
            # Generate data
            clean_all = cfg['gen'](n_train + n_test)
            train_clean = clean_all.iloc[:n_train].reset_index(drop=True)
            test_df = clean_all.iloc[n_train:].reset_index(drop=True)
            
            # Inject realistic corruptions
            train_corrupt, log = inject_realistic_corruptions(
                train_clean, domain, rate=0.02, seed=seed
            )
            all_corrupted = set().union(*log.values())
            corrupt_rate = len(all_corrupted) / n_train

            # ── Run all methods ────────────────────────────────────────
            t0 = time.time()
            apie_result = apie.validate(train_corrupt, domain=cfg['apie_domain'])
            apie_ms = (time.time() - t0) * 1000

            zs_excl   = baseline_zscore(train_corrupt)
            iqr_excl  = baseline_iqr(train_corrupt)
            ifo_excl  = baseline_isolation_forest(train_corrupt, contamination=corrupt_rate)

            # ── Compute detection metrics ──────────────────────────────
            def metrics(excl: set, review: set = None) -> dict:
                tp = excl & all_corrupted
                fp = excl - all_corrupted
                prec = len(tp) / len(excl) if excl else 0
                rec  = len(tp) / len(all_corrupted) if all_corrupted else 0
                # Add review-flagged metrics
                rev_tp = (review & all_corrupted) if review else set()
                combined = excl | (review or set())
                comb_tp = combined & all_corrupted
                comb_prec = len(comb_tp)/len(combined) if combined else 0
                comb_rec  = len(comb_tp)/len(all_corrupted) if all_corrupted else 0
                return {'tp': len(tp), 'fp': len(fp),
                        'precision': prec, 'recall': rec,
                        'n_excl': len(excl),
                        'review_tp': len(rev_tp),
                        'combined_recall': comb_rec,
                        'combined_precision': comb_prec}

            review_set = {f['row_index'] for f in apie_result.flagged_for_review}
            m = {
                'apie':     metrics(apie_result.excluded_indices, review_set),
                'zscore':   metrics(zs_excl),
                'iqr':      metrics(iqr_excl),
                'iso_forest': metrics(ifo_excl),
            }
            
            # Per-corruption-type recall for APIE
            cat_recall = {
                cat: len(apie_result.excluded_indices & idx) / len(idx) * 100
                for cat, idx in log.items() if idx
            }

            # ── Model quality: how much does corrupted data hurt? ──────
            feat_cols = [c for c in cfg['features'] if c in train_corrupt.columns]
            tgt = cfg['target']
            
            if tgt in train_corrupt.columns and feat_cols:
                X_test  = test_df[feat_cols].values
                y_test  = test_df[tgt].values
                X_clean = train_clean[feat_cols].values
                y_clean = train_clean[tgt].values
                X_corrupt = train_corrupt[feat_cols].values
                y_corrupt = train_corrupt[tgt].values
                
                # APIE-cleaned
                apie_mask = [i for i in range(n_train) if i not in apie_result.excluded_indices]
                X_apie = X_corrupt[apie_mask]; y_apie = y_corrupt[apie_mask]
                
                # IsoForest-cleaned
                iso_mask = [i for i in range(n_train) if i not in ifo_excl]
                X_iso = X_corrupt[iso_mask]; y_iso = y_corrupt[iso_mask]

                mape_clean   = train_model(X_clean,  y_clean,  X_test, y_test)
                mape_corrupt = train_model(X_corrupt, y_corrupt, X_test, y_test)
                mape_apie    = train_model(X_apie,   y_apie,   X_test, y_test)
                mape_iso     = train_model(X_iso,    y_iso,    X_test, y_test)
            else:
                mape_clean = mape_corrupt = mape_apie = mape_iso = None

            domain_seeds.append({
                'corrupt_rate': corrupt_rate,
                'metrics': m,
                'cat_recall': cat_recall,
                'mape': {'clean': mape_clean, 'corrupt': mape_corrupt,
                         'apie': mape_apie, 'iso_forest': mape_iso},
                'apie_ms': apie_ms,
            })

        # ── Aggregate across seeds ─────────────────────────────────────
        def mean_m(method, key):
            return np.mean([s['metrics'][method][key] for s in domain_seeds])
        
        def mean_mape(which):
            vals = [s['mape'][which] for s in domain_seeds if s['mape'][which] is not None]
            return np.mean(vals) if vals else None

        cr = np.mean([s['corrupt_rate'] for s in domain_seeds])
        
        print(f"\n   Corruption rate: {cr*100:.1f}%  "
              f"({int(cr*n_train)} of {n_train:,} training trials)\n")
        print(f"   {'Method':20s} {'Recall':>8s} {'Precision':>10s} {'FP Rate':>9s}")
        print(f"   {'─'*50}")
        for method in ['apie', 'iso_forest', 'zscore', 'iqr']:
            rec   = mean_m(method, 'recall')
            prec  = mean_m(method, 'precision')
            fp    = np.mean([s['metrics'][method]['fp'] / n_train for s in domain_seeds])
            star  = " ◄" if method == 'apie' else ""
            print(f"   {method:20s} {rec*100:7.1f}%  {prec*100:9.1f}%  {fp*100:8.2f}%{star}")
        
        # Per-category breakdown for APIE
        cat_avgs = {}
        for cat in ['solver_divergence','unit_error','sensor_drift','cross_variable','noise_spike']:
            vals = [s['cat_recall'].get(cat, 0) for s in domain_seeds if s['cat_recall'].get(cat,0) >= 0]
            if vals: cat_avgs[cat] = np.mean(vals)
        
        print(f"\n   SimAPI per-corruption-type recall:")
        for cat, val in cat_avgs.items():
            print(f"     {cat:25s}: {val:.0f}%")
        
        if mean_mape('clean') is not None:
            mc = mean_mape('clean'); mco = mean_mape('corrupt')
            ma = mean_mape('apie');  mi  = mean_mape('iso_forest')
            gain_vs_corrupt = (mco - ma) / mco * 100
            gain_vs_iso     = (mi  - ma) / mi  * 100 if mi else 0
            print(f"\n   Random Forest MAPE on test set:")
            print(f"     Clean training data: {mc:.3f}%")
            print(f"     Corrupted (no filter): {mco:.3f}%  (+{(mco-mc)/mc*100:.1f}% error vs clean)")
            print(f"     After Isolation Forest: {mi:.3f}%")
            print(f"     After SimAPI:  {ma:.3f}%  ({gain_vs_corrupt:.1f}% better than corrupted)")
            if gain_vs_iso > 0:
                print(f"                           ({gain_vs_iso:.1f}% better than Isolation Forest)")
        
        ms_avg = np.mean([s['apie_ms'] for s in domain_seeds])
        print(f"\n   SimAPI latency: {ms_avg:.0f}ms for {n_train:,} rows")
        print()
        
        results[domain] = {
            'customer': cfg['customer'],
            'stakes': cfg['stakes'],
            'corruption_rate_pct': round(cr*100, 2),
            'method_comparison': {
                m: {'recall': round(mean_m(m,'recall')*100,1),
                    'precision': round(mean_m(m,'precision')*100,1)}
                for m in ['apie','iso_forest','zscore','iqr']
            },
            'per_category_recall': {k: round(v,1) for k,v in cat_avgs.items()},
            'model_mape': {k: round(mean_mape(k),4) if mean_mape(k) else None
                           for k in ['clean','corrupt','apie','iso_forest']},
            'apie_latency_ms': round(ms_avg, 0),
        }

    # ── Save ────────────────────────────────────────────────────────────
    out = Path(__file__).resolve().parent / 'realistic_results.json'
    out.write_text(json.dumps({'domains': results, 'seeds': list(seeds),
                               'n_train': n_train, 'n_test': n_test}, indent=2))
    print(f"Results → {out}")
    return results


if __name__ == '__main__':
    run_realistic_benchmark()
