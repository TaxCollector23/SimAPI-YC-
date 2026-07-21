# SimAPI Integration Guide

## Quick Start

```bash
# Validate a CSV
simapi validate output.csv --domain aerodynamics

# CI mode (exit 1 on corruptions)
simapi ci output.csv --domain motor_thermal

# Save full report + clean data
simapi validate output.csv --report report.md --export clean.csv

# Watch mode (re-validate on file change)
simapi watch output.csv
```

## GitHub Actions

The fastest path: add SimAPI to any existing workflow.

```yaml
- name: Validate simulation output
  uses: simapi/simapi-action@v1
  with:
    file: outputs/cfd_results.csv
    domain: aerodynamics
    fail-on: critical
    export-clean: outputs/clean.csv
    config-key: mesh-v3-sst-re1e6
```

Full example: see `github-actions/example-workflow.yml`

**What you get:**
- Build fails if critical corruptions found
- SARIF uploaded to GitHub code scanning (visible in Security tab)
- Markdown report uploaded as artifact
- Clean dataset exported for downstream use
- Cross-run history tracking (catches drift over time)

**Outputs you can use in subsequent steps:**
```yaml
steps:
  - id: sim-validation
    uses: simapi/simapi-action@v1
    with:
      file: output.csv

  - name: Train only if clean
    if: steps.sim-validation.outputs.n-removed == '0'
    run: python train.py --data outputs/clean.csv
```

## Pre-Commit Hook

Block commits that contain corrupted simulation data.

```bash
# Quick install
cp integrations/pre-commit/pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

**Configure with `.simapi-hook.json`:**
```json
{
  "domain": "aerodynamics",
  "fail_on": "critical",
  "config_key": "my-project-v1"
}
```

**With the pre-commit framework:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/simapi/simapi
    rev: v3.0.0
    hooks:
      - id: simapi-validate
```

## Docker

```bash
# Build
docker build -t simapi -f integrations/docker/Dockerfile .

# Validate a file
docker run --rm -v $(pwd):/data simapi validate /data/output.csv

# CI mode
docker run --rm -v $(pwd):/data simapi ci /data/output.csv --domain aerodynamics
```

## Jenkins / CircleCI / GitLab CI

**Jenkins:**
```groovy
stage('Validate Simulation Data') {
    steps {
        sh 'pip install simapi pandas numpy scikit-learn scipy'
        sh 'simapi ci outputs/cfd.csv --domain aerodynamics --json > simapi-result.json'
        archiveArtifacts 'simapi-result.json'
    }
}
```

**CircleCI:**
```yaml
- run:
    name: SimAPI Physics Validation
    command: |
      pip install simapi pandas numpy scikit-learn scipy
      simapi ci outputs/sim.csv --domain motor_thermal \
        --report validation.md --sarif results.sarif
- store_artifacts:
    path: validation.md
- store_artifacts:
    path: results.sarif
```

**GitLab CI:**
```yaml
validate-simulation:
  stage: test
  script:
    - pip install simapi pandas numpy scikit-learn scipy
    - simapi ci outputs/sim.csv --domain aerodynamics --sarif gl-sast-report.sarif
  artifacts:
    reports:
      sast: gl-sast-report.sarif
    paths:
      - simapi-report.md
```

## Python SDK

```python
import sys
sys.path.insert(0, 'python-pkg')
from simapi.cli import _run_apie, _build_report_text
import pandas as pd

# Load your data
df = pd.read_csv('output.csv')
data = df.to_dict('records')

# Run validation
result, cross_run, df_validated = _run_apie(
    data=data,
    domain='aerodynamics',
    conditions={},
    config_key='my-sim-v3'
)

# Get clean indices
clean_mask = [i for i in range(len(df)) if i not in result.excluded_indices]
df_clean = df.iloc[clean_mask]

# Access diagnosis
if result.diagnosis:
    print(result.diagnosis.primary_diagnosis)
    print(result.diagnosis.investigation_steps)

# Get cross-run analysis
if cross_run and cross_run.run_is_outlier:
    print(f"WARNING: This run is a historical outlier!")
    for anomaly in cross_run.anomalies:
        print(f"  {anomaly.sigma:.1f}σ: {anomaly.interpretation}")
```

## Environment Variables

All options can be set via environment variables:

| Variable | Description | Example |
|---|---|---|
| `SIMAPI_DOMAIN` | Default simulation domain | `aerodynamics` |
| `SIMAPI_FAIL_ON` | When to fail (critical/review/any/never) | `critical` |
| `SIMAPI_CONFIG_KEY` | Cross-run config identifier | `mesh-v3-sst` |
| `NO_COLOR` | Disable ANSI colors | `1` |

## Exit Codes

| Code | Meaning | When |
|---|---|---|
| 0 | Clean | No corruptions, no flags |
| 1 | Corruptions found | Auto-removed rows exist |
| 2 | Error | File not found, parse error |
| 3 | Physical law violation | Solver divergence detected |

## Supported Domains

| Domain string | Use for |
|---|---|
| `aerodynamics` | CFD, wing/airfoil, compressible flow |
| `drone_aero` | Propeller CFD, eVTOL, UAV |
| `motor_thermal` | Motor thermal simulation, EV drivetrains |
| `thermodynamics` | General heat transfer, thermal FEM |
| `structural` | FEA, stress/strain analysis |
| `actuator_fea` | Robot joint structural analysis |
| `robotics/control` | Robot joint dynamics, torque/power |
| `hydrodynamics` | Marine CFD, underwater vehicles |
| `electromagnetics` | EM field simulation, antenna |
| `combustion` | Reacting flow, combustion CFD |
| `chemical` | Chemical reactor simulation |
| `acoustics` | Acoustic wave simulation |
| `meteorology` | Weather/atmospheric simulation |
| `geomechanics` | Soil/rock mechanics |
| `plasma` | Plasma physics |
