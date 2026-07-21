"""
SimAPI CLI v3.0 — Physics-Informed Simulation Validator

The full APIE engine runs locally. No data leaves your machine unless you
explicitly use --upload. Every validation produces a detailed forensic report.

Commands:
  validate   Run the full physics engine on a CSV/JSON file
  watch      Re-validate whenever the file changes (dev mode)
  compare    Compare two validation runs (before/after a fix)
  report     Generate a full forensic PDF/Markdown report
  history    Show cross-run trend analysis
  ci         CI/CD mode — validates and exits with code based on findings
  preflight  Mesh/solver preflight check before running a simulation
  init       Create a simapi.json config for this project
  doctor     Diagnose the local environment
  version    Print version

Integration:
  simapi ci --domain aerodynamics output.csv       # GitHub Actions / Jenkins
  SIMAPI_DOMAIN=aerodynamics simapi ci output.csv  # env-var config
  simapi validate output.csv --report report.md    # save Markdown report
  simapi validate output.csv --sarif sarif.json    # GitHub code scanning

Exit codes:
  0   Clean or only review flags (with --fail-on=review: exits 1)
  1   Critical corruptions auto-removed  
  2   Validation error (file not found, parse error)
  3   Physical law violations detected
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import time
import hashlib
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ── Version & paths ───────────────────────────────────────────────────────────

VERSION = "3.0.0"
CONFIG_DIR = Path.home() / ".simapi"
CONFIG_PATH = CONFIG_DIR / "config.json"
HISTORY_PATH = CONFIG_DIR / "run_history.json"

# ── Color/styling ─────────────────────────────────────────────────────────────

_COLOR = (
    sys.stdout.isatty()
    and not os.environ.get("NO_COLOR")
    and os.environ.get("TERM") != "dumb"
    and not os.environ.get("CI")  # clean output in CI by default
)

def _c(code: str, s: str) -> str:
    return f"\x1b[{code}m{s}\x1b[0m" if _COLOR else s

def _rgb(r: int, g: int, b: int, s: str) -> str:
    return f"\x1b[38;2;{r};{g};{b}m{s}\x1b[0m" if _COLOR else s

C = {
    "dim":   lambda s: _c("2", s),
    "bold":  lambda s: _c("1", s),
    "white": lambda s: _c("97", s),
    "cyan":  lambda s: _rgb(34, 211, 238, s),
    "green": lambda s: _rgb(52, 211, 153, s),
    "red":   lambda s: _rgb(248, 113, 113, s),
    "amber": lambda s: _rgb(251, 191, 36, s),
    "blue":  lambda s: _rgb(96, 165, 250, s),
    "purple":lambda s: _rgb(167, 139, 250, s),
}

ART = [
    "███████╗██╗███╗   ███╗ █████╗ ██████╗ ██╗",
    "██╔════╝██║████╗ ████║██╔══██╗██╔══██╗██║",
    "███████╗██║██╔████╔██║███████║██████╔╝██║",
    "╚════██║██║██║╚██╔╝██║██╔══██║██╔═══╝ ██║",
    "███████║██║██║ ╚═╝ ██║██║  ██║██║     ██║",
    "╚══════╝╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝",
]
GRAD = [(34,211,238),(42,190,240),(50,170,243),(55,150,245),(58,135,246),(59,130,246)]


def banner():
    width = shutil.get_terminal_size((80, 24)).columns
    art_w = max(len(line) for line in ART)
    pad = " " * ((width - art_w) // 2) if width >= art_w else ""
    print()
    for i, row in enumerate(ART):
        r, g, b = GRAD[i] if i < len(GRAD) else GRAD[-1]
        print(pad + _rgb(r, g, b, row))
    center = lambda s: (" " * ((width - len(s)) // 2) + s) if width >= len(s) else s
    print("\n" + center(C["bold"](C["white"](f"SimAPI CLI v{VERSION}"))))
    print(center(C["dim"]("Physics-Informed Simulation Validator — local engine, no data leaves your machine")) + "\n")


# ── Utilities ─────────────────────────────────────────────────────────────────

def _read_json(path: Path, fallback=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {} if fallback is None else fallback


def _write_json(path: Path, obj):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


def _fail(msg: str, code: int = 2):
    print(f"\n  {C['red']('✗')} {msg}\n", file=sys.stderr)
    sys.exit(code)


def _ok(msg: str):
    print(f"  {C['green']('✓')} {msg}")


def _warn(msg: str):
    print(f"  {C['amber']('⚠')} {msg}")


def _info(msg: str):
    print(f"  {C['cyan']('·')} {msg}")


def _section(title: str):
    width = min(shutil.get_terminal_size((80, 24)).columns, 72)
    print(f"\n  {C['bold'](title)}")
    print("  " + C["dim"]("─" * (width - 2)))


def _load_data(file: str) -> tuple:
    """Load CSV or JSON into (list_of_dicts, raw_text). Returns (None, error_msg) on failure."""
    p = Path(file)
    if not p.exists():
        return None, f"File not found: {file}"
    try:
        text = p.read_text(encoding="utf-8")
    except Exception as e:
        return None, f"Could not read {file}: {e}"

    if p.suffix.lower() == ".csv":
        try:
            reader = csv.DictReader(text.splitlines())
            rows = []
            for row in reader:
                parsed = {}
                for k, v in row.items():
                    if k is None:
                        continue
                    k = k.strip()
                    try:
                        parsed[k] = float(v)
                    except (ValueError, TypeError):
                        parsed[k] = v
                rows.append(parsed)
            return rows, text
        except Exception as e:
            return None, f"CSV parse error: {e}"

    elif p.suffix.lower() in (".json", ".jsonl"):
        try:
            obj = json.loads(text)
            if isinstance(obj, list):
                return obj, text
            elif isinstance(obj, dict):
                for key in ("data", "trials", "results", "rows"):
                    if isinstance(obj.get(key), list):
                        return obj[key], text
                return [obj], text
            return None, "JSON file must be an array or contain a 'data' key"
        except Exception as e:
            return None, f"JSON parse error: {e}"

    else:
        # Try JSON first, then CSV
        try:
            obj = json.loads(text)
            if isinstance(obj, list):
                return obj, text
        except Exception:
            pass
        try:
            reader = csv.DictReader(text.splitlines())
            rows = [{k.strip(): (float(v) if v else v) for k, v in row.items() if k}
                    for row in reader]
            return rows, text
        except Exception:
            pass
        return None, f"Unknown file format: {p.suffix}"


def _resolve_domain(args: dict, file: str) -> str:
    """Domain from: --domain flag > env var > simapi.json > guess from filename > aerodynamics."""
    if args.get("domain"):
        return args["domain"]
    if os.environ.get("SIMAPI_DOMAIN"):
        return os.environ["SIMAPI_DOMAIN"]
    cfg_path = Path("simapi.json")
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
            if cfg.get("simulation_type"):
                return cfg["simulation_type"]
        except Exception:
            pass
    # Guess from filename
    name = Path(file).stem.lower()
    guesses = {
        "aero": "aerodynamics", "cfd": "cfd", "drone": "drone_aero", "prop": "drone_aero",
        "thermal": "motor_thermal", "therm": "thermodynamics", "motor": "motor_thermal",
        "struct": "structural", "fea": "actuator_fea", "joint": "robotics/control",
        "robot": "robotics/control", "em": "electromagnetics", "plasma": "plasma",
        "chem": "chemical", "combustion": "combustion", "acoustic": "acoustics",
        "hydro": "hydrodynamics", "meteor": "meteorology", "geo": "geomechanics",
    }
    for key, domain in guesses.items():
        if key in name:
            return domain
    return "aerodynamics"


# ── Core engine runner ────────────────────────────────────────────────────────

def _run_apie(data: list, domain: str, conditions: dict, config_key: Optional[str] = None):
    """Run the full local APIE engine. Returns (apie_result, cross_run_result)."""
    import sys, os
    # Add project root to path
    cli_dir = Path(__file__).resolve().parent
    project_root = cli_dir.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import pandas as pd
    from core.apie import AdaptivePhysicsIntelligenceEngine
    from core.run_history import RunHistoryTracker

    apie = AdaptivePhysicsIntelligenceEngine()
    df = pd.DataFrame(data)
    result = apie.validate(df, domain=domain, conditions=conditions or {})

    cross_run = None
    if config_key:
        try:
            tracker = RunHistoryTracker(storage_path=str(HISTORY_PATH))
            cross_run = tracker.check_and_update(
                fingerprint=result.fingerprint,
                config_key=config_key,
                n_excluded=len(result.excluded_indices),
                n_flagged=len(result.flagged_for_review),
                corruption_types=list(result.test_plan.suspected_corruption_types.keys()),
            )
        except Exception:
            pass

    return result, cross_run, df


# ── Report builder ────────────────────────────────────────────────────────────

def _build_report_text(
    result,
    cross_run,
    df,
    file: str,
    domain: str,
    elapsed_ms: float,
    format: str = "terminal",  # "terminal" | "markdown" | "json"
) -> str:
    """
    Build the full forensic report. This is the centerpiece of the new CLI.
    """
    n = len(df)
    n_auto = len(result.excluded_indices)
    n_review = len(result.flagged_for_review)
    n_clean = n - n_auto
    cr_pct = n_auto / n * 100 if n > 0 else 0

    dx = result.diagnosis
    mfd = result.manifold

    # Derive status
    if n_auto == 0 and n_review == 0:
        status = "CLEAN"
    elif n_auto == 0:
        status = "REVIEW_ONLY"
    elif cr_pct < 2:
        status = "MINOR_CORRUPTIONS"
    elif cr_pct < 10:
        status = "SIGNIFICANT_CORRUPTIONS"
    else:
        status = "SEVERE_CORRUPTIONS"

    if format == "json":
        return _build_json_report(result, cross_run, df, file, domain, elapsed_ms, status)

    if format == "markdown":
        return _build_markdown_report(result, cross_run, df, file, domain, elapsed_ms, status, dx, mfd)

    # Terminal format (most detailed)
    return _build_terminal_report(result, cross_run, df, file, domain, elapsed_ms, status, dx, mfd, n, n_auto, n_review, n_clean, cr_pct)


def _build_terminal_report(result, cross_run, df, file, domain, elapsed_ms, status, dx, mfd, n, n_auto, n_review, n_clean, cr_pct):
    """Build the detailed terminal report."""
    lines = []
    W = min(shutil.get_terminal_size((80, 24)).columns, 78)

    def add(s=""):
        lines.append(s)

    def section(title):
        add(f"\n  {C['bold'](title)}")
        add("  " + C["dim"]("─" * (W - 4)))

    def row(label, value, color=None):
        lbl = C["dim"](f"{label}:")
        val = color(str(value)) if color else str(value)
        add(f"  {lbl.ljust(30 + 9 if _COLOR else 30)} {val}")

    # ── Header ─────────────────────────────────────────────────────────────
    status_colors = {
        "CLEAN": C["green"],
        "REVIEW_ONLY": C["cyan"],
        "MINOR_CORRUPTIONS": C["amber"],
        "SIGNIFICANT_CORRUPTIONS": C["amber"],
        "SEVERE_CORRUPTIONS": C["red"],
    }
    status_icons = {
        "CLEAN": "✅",
        "REVIEW_ONLY": "🔍",
        "MINOR_CORRUPTIONS": "⚠️",
        "SIGNIFICANT_CORRUPTIONS": "⚠️",
        "SEVERE_CORRUPTIONS": "🚨",
    }
    sc = status_colors.get(status, C["white"])

    add()
    add(f"  {C['bold']('SimAPI Validation Report')}")
    add(f"  {'─' * (W - 4)}")
    row("File", file)
    row("Domain", domain)
    row("Status", f"{status_icons.get(status,'')} {status.replace('_',' ')}", sc)
    row("Rows analyzed", f"{n:,}")
    row("Auto-removed", f"{n_auto} ({cr_pct:.1f}%)", C["red"] if n_auto > 0 else None)
    row("Flagged for review", f"{n_review}", C["amber"] if n_review > 0 else None)
    row("Clean rows", f"{n_clean:,} ({100-cr_pct:.1f}%)", C["green"])
    row("Validation time", f"{elapsed_ms:.0f}ms")
    row("APIE version", "5.6 (local engine)")
    if result.domain_profile:
        row("Domain profile", result.domain_profile)

    # ── Discovered invariants ───────────────────────────────────────────────
    if result.discovered_invariants:
        section("DISCOVERED PHYSICAL INVARIANTS")
        for pair, val in list(result.discovered_invariants.items())[:6]:
            add(f"  {C['cyan']('·')} {pair} = {val:.6g}")
        if len(result.discovered_invariants) > 6:
            add(C["dim"](f"  … and {len(result.discovered_invariants)-6} more"))

    # ── Checks run ──────────────────────────────────────────────────────────
    if result.test_plan and result.test_plan.checks:
        section("CHECKS EXECUTED")
        checks = result.test_plan.checks
        check_names = list(dict.fromkeys(c["check"] for c in checks))
        cols = 3
        for i in range(0, len(check_names), cols):
            chunk = check_names[i:i+cols]
            add("  " + "   ".join(C["dim"](f"[{c}]") for c in chunk))

    # ── Corrupted rows detail ───────────────────────────────────────────────
    if n_auto > 0:
        section(f"AUTO-REMOVED ROWS ({n_auto} rows — high confidence corruptions)")
        add(f"  {C['dim']('These rows violate physical laws or have unambiguous data errors.')}")
        add(f"  {C['dim']('They have been removed from the training-ready dataset.')}")
        add()

        # Group by corruption type
        type_groups: Dict[str, List] = {}
        for s in result.row_scores:
            if s.row_index in result.excluded_indices:
                ctype = s.corruption_type or "unknown"
                type_groups.setdefault(ctype, []).append(s)

        for ctype, scores in sorted(type_groups.items()):
            icon = {"unit_conversion": "📐", "solver_divergence": "💥",
                    "sensor_drift": "📉", "cross_variable": "🔗",
                    "copy_paste": "📋", "measurement_noise": "📊",
                    "physics_manifold": "🌐"}.get(ctype, "⚠️")
            add(f"\n  {icon} {C['bold'](ctype.upper().replace('_',' '))} — {len(scores)} rows")

            # Show sample corrupted rows with details
            for s in scores[:5]:
                sigma_str = f"{s.max_sigma:.1f}σ" if s.max_sigma < 1000 else f">1000σ"
                sev_color = C["red"] if s.severity == "critical" else C["amber"]
                add(f"    {sev_color('→')} Row {s.row_index:>5d}  [{sigma_str}]  {s.diagnosis[:80] if s.diagnosis else ''}")
                # Show the check that caught it
                if s.check_scores:
                    check_name = list(s.check_scores.keys())[0]
                    add(f"           {C['dim']('Detected by:')} {check_name}")

            if len(scores) > 5:
                add(f"    {C['dim'](f'… and {len(scores)-5} more rows of this type')}")

    # ── Manifold analysis ────────────────────────────────────────────────────
    if mfd and (mfd.n_components > 0):
        section("PHYSICS MANIFOLD ANALYSIS")
        add(f"  The simulation data lies on a {mfd.n_components}-dimensional physics manifold")
        add(f"  ({mfd.explained_variance*100:.1f}% of variance explained — mode: {mfd.manifold_mode})")
        if mfd.component_interpretation:
            add()
            add(f"  {C['dim']('Physical dimensions identified:')}")
            for interp in mfd.component_interpretation[:4]:
                add(f"  {C['cyan']('·')} {interp}")
        if mfd.auto_remove:
            add(f"\n  {C['amber']('⚠')} {len(mfd.auto_remove)} rows are 10×+ off the physics manifold")
            add(f"  {C['dim']('These violate the multivariate structure of the simulation data')}")
            add(f"  {C['dim']('even when individual column values look normal.')}")

    # ── Review flags ────────────────────────────────────────────────────────
    if n_review > 0:
        section(f"FLAGGED FOR HUMAN REVIEW ({n_review} rows — lower confidence)")
        add(f"  {C['dim']('Not auto-removed. Warrant engineer inspection before training.')}")
        add()
        for flag in result.flagged_for_review[:8]:
            add(f"  {C['amber']('→')} Row {flag['row_index']:>5d}  [{flag['max_sigma']:.1f}σ]  "
                f"{', '.join(flag['checks'][:2])}")
            if flag.get("diagnosis"):
                add(f"           {C['dim'](flag['diagnosis'][:90])}")
            if flag.get("reconstructed_values"):
                rv = flag["reconstructed_values"]
                top_cols = list(rv.keys())[:2]
                recon_str = "  ".join(f"{c}→{rv[c]:.4g}" for c in top_cols)
                add(f"           {C['dim']('Expected:')} {recon_str}")
        if n_review > 8:
            add(f"\n  {C['dim'](f'… and {n_review - 8} more. Run with --report to see all.')}")

    # ── Causal diagnosis ────────────────────────────────────────────────────
    if dx and dx.matched_failure_modes:
        section("CAUSAL DIAGNOSIS")
        top = dx.matched_failure_modes[0]
        add(f"  {C['bold']('Primary finding:')} {C['amber'](top['failure_mode'])}")
        add(f"  {C['dim']('Confidence:')} {dx.confidence*100:.0f}%  "
            f"{C['dim']('Pipeline stage:')} {dx.pipeline_stage.replace('_',' ')}")

        if top.get("evidence"):
            add(f"\n  {C['bold']('Evidence supporting this diagnosis:')}")
            for ev in top["evidence"]:
                add(f"  {C['cyan']('·')} {ev}")

        add(f"\n  {C['bold']('Most likely causal chain:')}")
        for i, step in enumerate(dx.causal_chain[:5], 1):
            add(f"  {C['dim'](str(i)+'.')} {step}")

        add(f"\n  {C['bold']('Recommended investigation steps:')}")
        for step in (dx.investigation_steps or [])[:4]:
            add(f"  {C['cyan']('→')} {step}")

        if dx.counterfactual_impact and "undetected" in dx.counterfactual_impact.lower()[:50]:
            add(f"\n  {C['bold']('If this had gone undetected:')}")
            add(f"  {C['red'](dx.counterfactual_impact[:300])}")

        if len(dx.matched_failure_modes) > 1:
            add(f"\n  {C['dim']('Other possible explanations:')}")
            for alt in dx.matched_failure_modes[1:3]:
                add(f"  {C['dim']('·')} {alt['failure_mode']} ({alt['match_score']*100:.0f}% match)")

    # ── Cross-run analysis ──────────────────────────────────────────────────
    if cross_run and cross_run.n_historical_runs > 0:
        section(f"CROSS-RUN ANALYSIS ({cross_run.n_historical_runs} historical runs)")
        if cross_run.run_is_outlier:
            add(f"  {C['red']('🚨 THIS RUN IS A HISTORICAL OUTLIER')}")
            add(f"  {C['dim']('Config match score:')} {cross_run.config_match_score*100:.0f}%")
            add()
        else:
            add(f"  {C['green']('✅ Within historical baseline')}  "
                f"(config match: {cross_run.config_match_score*100:.0f}%)")
        if cross_run.anomalies:
            add(f"\n  {C['bold']('Cross-run anomalies detected:')}")
            for a in cross_run.anomalies[:4]:
                icon = C["red"] if a.severity == "critical" else C["amber"]
                add(f"  {icon('→')} [{a.sigma:.1f}σ] {a.interpretation[:100]}")

    # ── Suspected corruption types ──────────────────────────────────────────
    suspected = result.test_plan.suspected_corruption_types if result.test_plan else {}
    if suspected:
        section("CORRUPTION TYPE PROBABILITIES")
        for ctype, conf in sorted(suspected.items(), key=lambda x: -x[1]):
            bar_len = int(conf * 20)
            bar = C["amber"]("█" * bar_len) + C["dim"]("░" * (20 - bar_len))
            add(f"  {ctype:25s} [{bar}] {conf*100:.0f}%")

    # ── What to do next ─────────────────────────────────────────────────────
    section("WHAT TO DO NEXT")
    if n_auto == 0 and n_review == 0:
        add(f"  {C['green']('Dataset is clean. Ready for training.')}")
        add()
        add(f"  {C['dim']('Tip: Run')} simapi history {C['dim']('to track this run in your cross-run baseline.')}")
    else:
        if n_auto > 0 and dx:
            add(f"  {C['bold']('1. Investigate the root cause')}")
            add(f"     {C['dim']('Diagnosed as:')} {dx.pipeline_stage.replace('_',' ')}")
            if dx.investigation_steps:
                add(f"     {C['cyan']('→')} {dx.investigation_steps[0]}")

        add(f"\n  {C['bold']('2. Get the clean dataset')}")
        add(f"     {C['dim']('Run with')} --export clean.csv {C['dim'](f'to save the {n_clean:,} clean rows.')}")
        add(f"     Clean rows: {n_clean:,} / {n:,} ({100-cr_pct:.1f}%)")

        if n_review > 0:
            add(f"\n  {C['bold']('3. Review flagged rows')}")
            add(f"     {n_review} rows need engineer inspection before training.")
            add(f"     {C['dim']('Run')} simapi validate --report report.md {C['dim']('for full details.')}")

        add(f"\n  {C['bold']('4. Fix the source data')}") 
        add(f"     {C['dim']('After fixing your simulation pipeline, re-run:')}")
        _fname = Path(file).name if file else "<file>"
        add(f"     {C['cyan']('simapi validate ' + _fname + ' --domain ' + domain)}")

    # ── Footer ──────────────────────────────────────────────────────────────
    add()
    add("  " + C["dim"]("─" * (W - 4)))
    add(f"  {C['dim'](f'SimAPI v{VERSION} · local engine · {elapsed_ms:.0f}ms')}")
    add()

    return "\n".join(lines)


def _build_markdown_report(result, cross_run, df, file, domain, elapsed_ms, status, dx, mfd):
    """Full Markdown forensic report."""
    n = len(df)
    n_auto = len(result.excluded_indices)
    n_review = len(result.flagged_for_review)
    n_clean = n - n_auto
    cr_pct = n_auto / n * 100 if n > 0 else 0

    status_icons = {
        "CLEAN": "✅", "REVIEW_ONLY": "🔍",
        "MINOR_CORRUPTIONS": "⚠️", "SIGNIFICANT_CORRUPTIONS": "⚠️", "SEVERE_CORRUPTIONS": "🚨",
    }

    import datetime
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    sha = hashlib.sha256(json.dumps(df.to_dict("records"), default=str, sort_keys=True).encode()).hexdigest()[:16]

    lines = [
        f"# SimAPI Validation Report",
        f"",
        f"> **Generated:** {ts}  ",
        f"> **File:** `{file}`  ",
        f"> **Domain:** `{domain}`  ",
        f"> **Dataset SHA-256:** `{sha}...`  ",
        f"> **SimAPI Version:** v{VERSION} (local engine)  ",
        f"",
        f"## {status_icons.get(status, '⚠️')} Status: {status.replace('_', ' ')}",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total rows | {n:,} |",
        f"| Auto-removed (corrupted) | **{n_auto}** ({cr_pct:.1f}%) |",
        f"| Flagged for review | {n_review} |",
        f"| Clean rows | {n_clean:,} ({100-cr_pct:.1f}%) |",
        f"| Validation time | {elapsed_ms:.0f}ms |",
        f"",
    ]

    # Discovered invariants
    if result.discovered_invariants:
        lines += [
            "## Discovered Physical Invariants",
            "",
            "These relationships were found in your data and used for validation:",
            "",
        ]
        for pair, val in result.discovered_invariants.items():
            lines.append(f"- `{pair}` = **{val:.6g}**")
        lines.append("")

    # Auto-removed rows
    if n_auto > 0:
        lines += [
            f"## Auto-Removed Rows ({n_auto} rows)",
            "",
            "These rows violate physical laws or contain unambiguous data errors. "
            "They have been removed from the training-ready dataset.",
            "",
        ]
        type_groups: Dict[str, List] = {}
        for s in result.row_scores:
            if s.row_index in result.excluded_indices:
                ctype = s.corruption_type or "unknown"
                type_groups.setdefault(ctype, []).append(s)

        for ctype, scores in sorted(type_groups.items()):
            lines += [
                f"### {ctype.replace('_', ' ').title()} ({len(scores)} rows)",
                "",
                f"| Row | Sigma | Severity | Check | Diagnosis |",
                f"|---|---|---|---|---|",
            ]
            for s in scores[:20]:
                sigma_str = f"{s.max_sigma:.1f}σ" if s.max_sigma < 1e6 else ">1e6σ"
                check = list(s.check_scores.keys())[0] if s.check_scores else "—"
                diag = (s.diagnosis or "")[:80].replace("|", "\\|")
                lines.append(f"| {s.row_index} | {sigma_str} | {s.severity} | `{check}` | {diag} |")
            if len(scores) > 20:
                lines.append(f"\n*…and {len(scores)-20} more rows.*")
            lines.append("")

    # Flagged for review
    if n_review > 0:
        lines += [
            f"## Flagged for Human Review ({n_review} rows)",
            "",
            "Not auto-removed. These rows warrant engineer inspection before training.",
            "",
            "| Row | Sigma | Checks | Diagnosis | Reconstructed Values |",
            "|---|---|---|---|---|",
        ]
        for flag in result.flagged_for_review[:30]:
            checks = ", ".join(f"`{c}`" for c in flag["checks"][:2])
            diag = (flag.get("diagnosis") or "")[:80].replace("|", "\\|")
            rv = flag.get("reconstructed_values") or {}
            recon = "; ".join(f"{k}→{v:.4g}" for k, v in list(rv.items())[:2])
            lines.append(f"| {flag['row_index']} | {flag['max_sigma']:.1f}σ | {checks} | {diag} | {recon} |")
        if n_review > 30:
            lines.append(f"\n*…and {n_review-30} more flagged rows.*")
        lines.append("")

    # Causal diagnosis
    if dx and dx.matched_failure_modes:
        top = dx.matched_failure_modes[0]
        lines += [
            "## Causal Diagnosis",
            "",
            f"**Primary finding:** {top['failure_mode']}  ",
            f"**Confidence:** {dx.confidence*100:.0f}%  ",
            f"**Pipeline stage:** {dx.pipeline_stage.replace('_', ' ')}  ",
            "",
        ]
        if top.get("evidence"):
            lines += ["**Evidence:**", ""]
            for ev in top["evidence"]:
                lines.append(f"- {ev}")
            lines.append("")

        lines += ["**Causal chain:**", ""]
        for i, step in enumerate(dx.causal_chain, 1):
            lines.append(f"{i}. {step}")
        lines.append("")

        lines += ["**Recommended investigation steps:**", ""]
        for step in (dx.investigation_steps or []):
            lines.append(f"- {step}")
        lines.append("")

        if dx.counterfactual_impact:
            lines += [
                "**If undetected:**",
                "",
                f"> {dx.counterfactual_impact}",
                "",
            ]

    # Cross-run
    if cross_run and cross_run.n_historical_runs > 0:
        lines += [
            f"## Cross-Run Analysis ({cross_run.n_historical_runs} historical runs)",
            "",
            f"**Outlier status:** {'🚨 OUTLIER' if cross_run.run_is_outlier else '✅ Within baseline'}  ",
            f"**Config match score:** {cross_run.config_match_score*100:.0f}%  ",
            "",
        ]
        if cross_run.anomalies:
            lines += ["**Cross-run anomalies:**", ""]
            for a in cross_run.anomalies:
                lines.append(f"- **[{a.sigma:.1f}σ]** {a.interpretation}")
            lines.append("")

    # Manifold
    if mfd and mfd.n_components > 0:
        lines += [
            "## Physics Manifold Analysis",
            "",
            f"Your simulation data lies on a **{mfd.n_components}-dimensional** physics manifold  ",
            f"({mfd.explained_variance*100:.1f}% of variance explained, mode: {mfd.manifold_mode})  ",
            "",
        ]
        if mfd.component_interpretation:
            lines += ["**Physical dimensions:**", ""]
            for interp in mfd.component_interpretation:
                lines.append(f"- {interp}")
            lines.append("")

    # Next steps
    lines += [
        "## What To Do Next",
        "",
    ]
    if n_auto == 0 and n_review == 0:
        lines.append("✅ **Dataset is clean.** Ready for model training.")
    else:
        if n_auto > 0:
            lines += [
                "### 1. Investigate the root cause",
                "",
                f"Diagnosed as: **{dx.pipeline_stage.replace('_',' ') if dx else 'unknown'}**",
            ]
            if dx and dx.investigation_steps:
                lines.append("")
                for step in dx.investigation_steps[:3]:
                    lines.append(f"- {step}")
            lines.append("")

        lines += [
            "### 2. Get the clean dataset",
            "",
            f"Run `simapi validate {file} --export clean.csv` to save the {n_clean:,} clean rows.",
            f"",
            f"- Clean rows: **{n_clean:,}** / {n:,} ({100-cr_pct:.1f}%)",
            "",
        ]

        if n_review > 0:
            lines += [
                "### 3. Review flagged rows",
                "",
                f"{n_review} rows need engineer inspection. See the **Flagged for Human Review** section above.",
                "",
            ]

    lines += [
        "---",
        "",
        f"*SimAPI v{VERSION} · Physics-Informed Simulation Validator · {elapsed_ms:.0f}ms*",
        "",
    ]

    return "\n".join(lines)


def _build_json_report(result, cross_run, df, file, domain, elapsed_ms, status):
    """Machine-readable JSON report."""
    n = len(df)
    return json.dumps({
        "version": VERSION,
        "file": file,
        "domain": domain,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 1),
        "n_rows": n,
        "n_auto_removed": len(result.excluded_indices),
        "n_flagged_review": len(result.flagged_for_review),
        "n_clean": n - len(result.excluded_indices),
        "auto_removed_indices": sorted(result.excluded_indices),
        "flagged_for_review": result.flagged_for_review[:100],
        "domain_profile": result.domain_profile,
        "discovered_invariants": result.discovered_invariants,
        "suspected_corruption": result.test_plan.suspected_corruption_types if result.test_plan else {},
        "diagnosis": {
            "primary": result.diagnosis.primary_diagnosis if result.diagnosis else None,
            "pipeline_stage": result.diagnosis.pipeline_stage if result.diagnosis else None,
            "causal_chain": result.diagnosis.causal_chain if result.diagnosis else [],
            "investigation_steps": result.diagnosis.investigation_steps if result.diagnosis else [],
            "counterfactual": result.diagnosis.counterfactual_impact if result.diagnosis else None,
            "confidence": result.diagnosis.confidence if result.diagnosis else 0,
        },
        "cross_run": {
            "n_historical_runs": cross_run.n_historical_runs if cross_run else 0,
            "is_outlier": cross_run.run_is_outlier if cross_run else False,
            "config_match": cross_run.config_match_score if cross_run else 1.0,
            "anomalies": [
                {"kind": a.kind, "subject": a.subject, "sigma": a.sigma,
                 "severity": a.severity, "interpretation": a.interpretation}
                for a in (cross_run.anomalies if cross_run else [])
            ],
        } if cross_run else None,
        "manifold": {
            "n_components": result.manifold.n_components if result.manifold else 0,
            "explained_variance": result.manifold.explained_variance if result.manifold else 0,
            "mode": result.manifold.manifold_mode if result.manifold else None,
            "components": result.manifold.component_interpretation if result.manifold else [],
        } if result.manifold else None,
        "checks_run": [c["check"] for c in result.test_plan.checks] if result.test_plan else [],
    }, indent=2)


def _build_sarif_report(result, file: str, domain: str) -> str:
    """GitHub code scanning SARIF format."""
    results = []
    for s in result.row_scores:
        if s.row_index in result.excluded_indices:
            check = list(s.check_scores.keys())[0] if s.check_scores else "unknown"
            results.append({
                "ruleId": f"simapi/{s.corruption_type or check}",
                "level": "error" if s.severity == "critical" else "warning",
                "message": {"text": s.diagnosis or f"Row {s.row_index}: {check} ({s.max_sigma:.1f}σ)"},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": file},
                        "region": {"startLine": s.row_index + 2}  # +2: 1-based + header
                    }
                }]
            })
    for flag in result.flagged_for_review:
        results.append({
            "ruleId": f"simapi/review_required",
            "level": "note",
            "message": {"text": flag.get("diagnosis") or f"Row {flag['row_index']} flagged for review"},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": file},
                    "region": {"startLine": flag["row_index"] + 2}
                }
            }]
        })
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "SimAPI",
                    "version": VERSION,
                    "informationUri": "https://sim-api.vercel.app",
                    "rules": [
                        {"id": "simapi/solver_divergence", "name": "SolverDivergence",
                         "shortDescription": {"text": "Solver divergence detected"}},
                        {"id": "simapi/unit_conversion", "name": "UnitConversionError",
                         "shortDescription": {"text": "Unit conversion error detected"}},
                        {"id": "simapi/sensor_drift", "name": "SensorDrift",
                         "shortDescription": {"text": "Sensor/gauge drift detected"}},
                        {"id": "simapi/cross_variable", "name": "CrossVariableInconsistency",
                         "shortDescription": {"text": "Cross-variable inconsistency"}},
                        {"id": "simapi/review_required", "name": "ReviewRequired",
                         "shortDescription": {"text": "Row requires human review"}},
                    ]
                }
            },
            "results": results,
            "artifacts": [{"location": {"uri": file}}]
        }]
    }
    return json.dumps(sarif, indent=2)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_validate(args):
    """
    Full validation with detailed forensic report.
    
    Usage: simapi validate <file> [options]
    
    Options:
      --domain <domain>    Simulation domain (auto-detected if omitted)
      --report <file.md>   Save full Markdown report
      --export <file.csv>  Save clean rows to CSV
      --json               Output as JSON (machine-readable)
      --sarif <file>       Output SARIF for GitHub code scanning
      --config-key <key>   Cross-run config key (enables history tracking)
      --fail-on <level>    Exit 1 on: critical, review, any
      --quiet              Suppress banner and extra output
    """
    files = args.get("_", [])
    if not files:
        _fail("Usage: simapi validate <file> [--domain <domain>]")

    file = files[0]
    if not args.get("quiet"):
        banner()

    # Load data
    print(f"  {C['dim']('Loading')} {file}…")
    data, err = _load_data(file)
    if data is None:
        _fail(f"Failed to load file: {err}")

    print(f"  {C['dim']('Loaded')} {len(data):,} rows")

    domain = _resolve_domain(args, file)
    conditions = {}
    config_key = args.get("config_key") or os.environ.get("SIMAPI_CONFIG_KEY") or f"{domain}:{Path(file).stem}"

    # Run engine
    print(f"  {C['dim']('Running APIE engine')} [{domain}]…")
    t0 = time.time()
    try:
        result, cross_run, df = _run_apie(data, domain, conditions, config_key)
    except ImportError as e:
        _fail(f"Engine not available: {e}\n"
              f"  Make sure you're running from the SimAPI project directory.")
    except Exception as e:
        _fail(f"Validation engine error: {e}\n  {traceback.format_exc()[-400:]}")
    elapsed_ms = (time.time() - t0) * 1000

    # Determine format
    fmt = "json" if args.get("json") else "terminal"

    # Build report
    report_text = _build_report_text(result, cross_run, df, file, domain, elapsed_ms, fmt)
    print(report_text)

    # Save Markdown report
    if args.get("report"):
        md = _build_report_text(result, cross_run, df, file, domain, elapsed_ms, "markdown")
        Path(args["report"]).write_text(md)
        _ok(f"Report saved → {args['report']}")

    # Save SARIF
    if args.get("sarif"):
        sarif = _build_sarif_report(result, file, domain)
        Path(args["sarif"]).write_text(sarif)
        _ok(f"SARIF saved → {args['sarif']}")

    # Export clean CSV
    if args.get("export"):
        clean_rows = [data[i] for i in range(len(data)) if i not in result.excluded_indices]
        out_path = Path(args["export"])
        if clean_rows:
            with open(out_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=clean_rows[0].keys())
                writer.writeheader()
                writer.writerows(clean_rows)
        _ok(f"Clean data exported → {out_path} ({len(clean_rows):,} rows)")

    # Exit code
    n_auto = len(result.excluded_indices)
    n_review = len(result.flagged_for_review)
    fail_on = args.get("fail_on") or os.environ.get("SIMAPI_FAIL_ON", "critical")

    if fail_on == "any" and (n_auto > 0 or n_review > 0):
        sys.exit(1)
    elif fail_on in ("critical", "error") and n_auto > 0:
        sys.exit(1)
    elif fail_on == "review" and n_review > 0:
        sys.exit(1)


def cmd_ci(args):
    """
    CI/CD mode — minimal output, structured exit codes, SARIF support.
    
    Usage: simapi ci <file> [options]
    
    This command is designed for use in GitHub Actions, Jenkins, CircleCI, etc.
    Outputs minimal text by default, exits non-zero when corruptions found.
    
    Exit codes:
      0  Clean (no corruptions, no review flags)
      1  Corruptions detected
      3  Physical law violations
    
    Examples:
      simapi ci output.csv --domain aerodynamics --sarif results.sarif
      simapi ci output.csv --json > result.json
    """
    args["quiet"] = True
    args["fail_on"] = args.get("fail_on") or os.environ.get("SIMAPI_FAIL_ON", "critical")

    files = args.get("_", [])
    if not files:
        _fail("Usage: simapi ci <file>")

    file = files[0]
    data, err = _load_data(file)
    if data is None:
        print(json.dumps({"status": "error", "message": err}))
        sys.exit(2)

    domain = _resolve_domain(args, file)
    config_key = args.get("config_key") or os.environ.get("SIMAPI_CONFIG_KEY") or f"{domain}:{Path(file).stem}"

    t0 = time.time()
    try:
        result, cross_run, df = _run_apie(data, domain, {}, config_key)
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(2)
    elapsed_ms = (time.time() - t0) * 1000

    n_auto = len(result.excluded_indices)
    n_review = len(result.flagged_for_review)
    n = len(df)

    status = "clean" if n_auto == 0 and n_review == 0 else \
             "review_only" if n_auto == 0 else "corruptions_found"

    # SARIF output
    if args.get("sarif"):
        sarif = _build_sarif_report(result, file, domain)
        Path(args["sarif"]).write_text(sarif)

    # JSON output
    if args.get("json"):
        print(_build_json_report(result, cross_run, df, file, domain, elapsed_ms,
                                  status.upper()))
    else:
        # Compact CI output
        icon = "✅" if status == "clean" else "⚠️" if status == "review_only" else "❌"
        print(f"{icon} SimAPI [{domain}] {file}: {n_auto} removed, {n_review} flagged, {n-n_auto:,} clean ({elapsed_ms:.0f}ms)")
        if n_auto > 0 and result.diagnosis:
            print(f"   Diagnosis: {result.diagnosis.primary_diagnosis}")
        if cross_run and cross_run.run_is_outlier:
            print(f"   ⚠️  Cross-run outlier (config match: {cross_run.config_match_score*100:.0f}%)")

    # Exit codes
    fail_on = args.get("fail_on", "critical")
    if fail_on == "any" and (n_auto > 0 or n_review > 0):
        sys.exit(1)
    elif fail_on == "review" and n_review > 0:
        sys.exit(1)
    elif n_auto > 0:
        # Check if physical law violations
        if result.diagnosis and result.diagnosis.pipeline_stage in ("solver_iteration", "solver_coupling"):
            sys.exit(3)
        sys.exit(1)


def cmd_watch(args):
    """Re-validate whenever the file changes."""
    files = args.get("_", [])
    if not files:
        _fail("Usage: simapi watch <file>")
    file = files[0]
    p = Path(file)
    if not p.exists():
        _fail(f"File not found: {file}")
    banner()
    print(f"  {C['cyan']('watching')} {file} — re-validates on change. {C['dim']('Ctrl-C to stop.')}\n")
    args["quiet"] = True
    cmd_validate({**args, "quiet": False})
    last = p.stat().st_mtime
    try:
        while True:
            time.sleep(0.5)
            m = p.stat().st_mtime
            if m != last:
                last = m
                print(f"\n  {C['dim'](time.strftime('%H:%M:%S'))} change detected — re-validating…\n")
                cmd_validate({**args, "quiet": True})
    except KeyboardInterrupt:
        print("\n  stopped.\n")


def cmd_compare(args):
    """
    Compare two validation runs side-by-side.
    
    Usage: simapi compare <before.csv> <after.csv> [--domain <domain>]
    
    Shows: which rows changed status, improvement in corruption rate, MAPE delta.
    """
    files = args.get("_", [])
    if len(files) < 2:
        _fail("Usage: simapi compare <before.csv> <after.csv>")

    banner()
    before_file, after_file = files[0], files[1]
    domain = _resolve_domain(args, before_file)

    print(f"  Validating BEFORE: {before_file}…")
    data_b, err = _load_data(before_file)
    if data_b is None:
        _fail(f"Before file: {err}")
    r_before, _, df_b = _run_apie(data_b, domain, {})

    print(f"  Validating AFTER:  {after_file}…")
    data_a, err = _load_data(after_file)
    if data_a is None:
        _fail(f"After file: {err}")
    r_after, _, df_a = _run_apie(data_a, domain, {})

    n_b, n_a = len(df_b), len(df_a)
    auto_b, auto_a = len(r_before.excluded_indices), len(r_after.excluded_indices)
    rev_b, rev_a = len(r_before.flagged_for_review), len(r_after.flagged_for_review)

    _section("COMPARISON: Before vs After")
    print(f"  {'Metric':30s} {'Before':>12s} {'After':>12s} {'Change':>12s}")
    print("  " + "─" * 68)

    def compare_row(label, vb, va, higher_is_better=True):
        delta = va - vb
        sign = "+" if delta > 0 else ""
        color = C["green"] if (delta > 0) == higher_is_better else C["red"]
        delta_str = color(f"{sign}{delta:.1f}") if delta != 0 else C["dim"]("—")
        print(f"  {label:30s} {vb:>12.1f} {va:>12.1f} {delta_str:>12s}")

    compare_row("Rows analyzed", n_b, n_a, True)
    compare_row("Auto-removed", auto_b, auto_a, False)
    compare_row("Flagged for review", rev_b, rev_a, False)
    compare_row("Clean rows", n_b-auto_b, n_a-auto_a, True)
    compare_row("Corruption rate %", auto_b/n_b*100 if n_b else 0, auto_a/n_a*100 if n_a else 0, False)

    # Rows that changed status
    newly_clean = r_before.excluded_indices - r_after.excluded_indices
    newly_corrupt = r_after.excluded_indices - r_before.excluded_indices

    if newly_clean:
        _section(f"NEWLY CLEAN ROWS ({len(newly_clean)} rows fixed)")
        for idx in sorted(newly_clean)[:10]:
            print(f"  {C['green']('✓')} Row {idx} — no longer flagged")

    if newly_corrupt:
        _section(f"NEWLY CORRUPTED ROWS ({len(newly_corrupt)} rows introduced)")
        for idx in sorted(newly_corrupt)[:10]:
            print(f"  {C['red']('✗')} Row {idx} — new corruption introduced")
    print()


def cmd_history(args):
    """
    Show cross-run trend analysis for a domain/config.
    
    Usage: simapi history [--domain <domain>] [--config-key <key>] [--last <n>]
    """
    banner()
    try:
        import sys as _sys
        cli_dir = Path(__file__).resolve().parent
        project_root = cli_dir.parent.parent
        if str(project_root) not in _sys.path:
            _sys.path.insert(0, str(project_root))
        from core.run_history import RunHistoryTracker
    except ImportError:
        _fail("RunHistoryTracker not available. Run from SimAPI project directory.")

    tracker = RunHistoryTracker(storage_path=str(HISTORY_PATH))
    domain = args.get("domain") or _resolve_domain(args, "")
    config_key = args.get("config_key") or f"{domain}:"
    last_n = int(args.get("last", 20))
    n_hist = tracker.n_runs(config_key)

    _section(f"CROSS-RUN HISTORY — {config_key}")
    if n_hist == 0:
        print(f"  {C['dim']('No history yet. Run simapi validate with --config-key to start tracking.')}\n")
        return
    print(f"  {n_hist} runs recorded")
    trend = tracker.get_trend(config_key, "velocity", last_n)
    if trend["means"] and any(v is not None for v in trend["means"]):
        print(f"\n  {C['bold']('Recent run IDs:')}")
        for rid in trend["run_ids"][-5:]:
            print(f"  {C['dim']('·')} {rid}")
    print()


def cmd_preflight(args):
    """
    Pre-flight mesh and solver check before running a simulation.
    
    Usage: simapi preflight [--domain <domain>] [--mesh-stats <json>]
    
    Reads mesh quality metrics and solver settings and predicts which types
    of output corruption are most likely before you run the simulation.
    """
    banner()
    try:
        import sys as _sys
        cli_dir = Path(__file__).resolve().parent
        project_root = cli_dir.parent.parent
        if str(project_root) not in _sys.path:
            _sys.path.insert(0, str(project_root))
        from core.mesh_validator import predict_output_corruption
    except ImportError:
        _fail("Mesh validator not available. Run from SimAPI project directory.")

    domain = _resolve_domain(args, "")
    mesh_stats = {}
    solver_settings = {}

    # Read from file or args
    files = args.get("_", [])
    if files:
        cfg, err = _load_data(files[0])
        if cfg and isinstance(cfg, list) and len(cfg) > 0:
            cfg = cfg[0]
        if isinstance(cfg, dict):
            mesh_stats = cfg.get("mesh_stats", cfg.get("mesh", {}))
            solver_settings = cfg.get("solver", cfg.get("solver_settings", {}))

    # Interactive prompts if no file
    if not mesh_stats and sys.stdin.isatty():
        print(f"  {C['dim']('Enter mesh quality metrics (or press Enter to skip):')}\n")
        for key, prompt, default in [
            ("max_skewness", "Max cell skewness [0-1]", "0.0"),
            ("max_aspect_ratio", "Max aspect ratio", "1.0"),
            ("max_non_orthogonality", "Max non-orthogonality [deg]", "0.0"),
        ]:
            val = input(f"  {prompt} [{default}]: ").strip() or default
            try:
                mesh_stats[key] = float(val)
            except ValueError:
                pass
        print()
        for key, prompt, default in [
            ("cfl_number", "CFL number", "0.5"),
            ("relative_tolerance", "Solver tolerance (e.g. 1e-6)", "1e-6"),
        ]:
            val = input(f"  {prompt} [{default}]: ").strip() or default
            try:
                solver_settings[key] = float(val)
            except ValueError:
                pass

    result = predict_output_corruption(domain, mesh_stats, solver_settings)

    _section(f"PREFLIGHT REPORT — {domain}")

    if result.get("error"):
        _warn(f"Preflight error: {result['error']}")
    else:
        suspected = result.get("suspected_corruption_types", {})
        if not suspected:
            print(f"  {C['green']('✅ No specific corruption risks predicted.')}")
        else:
            print(f"  {C['bold']('Predicted output corruption risks:')}\n")
            for ctype, conf in sorted(suspected.items(), key=lambda x: -x[1]):
                bar = C["amber"]("█" * int(conf*20)) + C["dim"]("░" * (20-int(conf*20)))
                print(f"  {ctype:25s} [{bar}] {conf*100:.0f}%")

        risks = result.get("risk_factors", [])
        if risks:
            _section("RISK FACTORS IDENTIFIED")
            for rf in risks:
                print(f"  {C['amber']('⚠')} {rf}")

        checks = result.get("recommended_checks", [])
        if checks:
            _section("RECOMMENDED VALIDATION CHECKS")
            print(f"  {C['dim']('Run these checks on your output with extra attention:')}\n")
            for c in checks:
                print(f"  {C['cyan']('→')} {c}")

    print()


def cmd_init(args):
    """Create a simapi.json configuration file in the current directory."""
    path = Path("simapi.json")
    if path.exists() and "--force" not in (args.get("_") or []):
        _fail(f"simapi.json already exists. Use --force to overwrite.")
    cfg = {
        "$schema": "https://sim-api.vercel.app/schema/simapi.json",
        "simulation_type": args.get("domain") or "aerodynamics",
        "conditions": {},
        "fail_on": "critical",
        "config_key": f"my-sim-{Path.cwd().name}",
        "report": "simapi-report.md",
    }
    path.write_text(json.dumps(cfg, indent=2))
    _ok("Created simapi.json")
    print(f"\n  {C['dim']('Edit simulation_type and then run:')}")
    print(f"  {C['cyan']('simapi validate your-output.csv')}\n")


def cmd_doctor(args):
    """Diagnose the local environment."""
    banner()
    _section("ENVIRONMENT DIAGNOSTICS")
    problems = 0

    # Python version
    if sys.version_info >= (3, 8):
        _ok(f"Python {sys.version.split()[0]}")
    else:
        _warn(f"Python {sys.version.split()[0]} — 3.8+ required")
        problems += 1

    # Core modules
    for mod, desc in [
        ("pandas", "Data loading"),
        ("numpy", "Numerical engine"),
        ("sklearn", "ML components"),
        ("scipy", "Statistical analysis"),
    ]:
        try:
            __import__(mod)
            _ok(f"{mod} ({desc})")
        except ImportError:
            print(f"  {C['red']('✗')} {mod} not installed — {C['dim']('pip install ' + mod)}")
            problems += 1

    # APIE engine
    try:
        import sys as _sys
        cli_dir = Path(__file__).resolve().parent
        project_root = cli_dir.parent.parent
        if str(project_root) not in _sys.path:
            _sys.path.insert(0, str(project_root))
        from core.apie import AdaptivePhysicsIntelligenceEngine, DOMAIN_LIBRARY
        _ok(f"APIE engine ({len(DOMAIN_LIBRARY)} domain profiles)")
    except ImportError as e:
        print(f"  {C['red']('✗')} APIE engine not found: {e}")
        print(f"    {C['dim']('Run from the SimAPI project root directory')}")
        problems += 1

    # Config
    if CONFIG_DIR.exists():
        _ok(f"Config directory ({CONFIG_DIR})")
    else:
        _warn(f"Config directory not created yet ({CONFIG_DIR})")

    # simapi.json
    if Path("simapi.json").exists():
        _ok("simapi.json found")
    else:
        print(f"  {C['dim']('·')} No simapi.json (optional — run simapi init)")

    print()
    if problems == 0:
        _ok("All checks passed. Ready to validate.\n")
    else:
        _warn(f"{problems} issue(s) found.\n")


def cmd_version(args):
    banner()
    print(f"  v{VERSION}  •  local engine  •  Python {sys.version.split()[0]}\n")


# ── Argument parser ────────────────────────────────────────────────────────────

def _parse(argv: List[str]) -> dict:
    args: Dict[str, Any] = {
        "_": [], "domain": None, "json": False, "quiet": False,
        "fail_on": None, "report": None, "export": None, "sarif": None,
        "config_key": None, "last": 20, "force": False, "apply": False,
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--json", "-j"):
            args["json"] = True
        elif a in ("--quiet", "-q"):
            args["quiet"] = True
        elif a == "--force":
            args["force"] = True
        elif a == "--apply":
            args["apply"] = True
        elif a in ("--domain", "-d") and i+1 < len(argv):
            i += 1; args["domain"] = argv[i]
        elif a in ("--fail-on", "--fail_on") and i+1 < len(argv):
            i += 1; args["fail_on"] = argv[i]
        elif a == "--report" and i+1 < len(argv):
            i += 1; args["report"] = argv[i]
        elif a == "--export" and i+1 < len(argv):
            i += 1; args["export"] = argv[i]
        elif a == "--sarif" and i+1 < len(argv):
            i += 1; args["sarif"] = argv[i]
        elif a in ("--config-key", "--config_key") and i+1 < len(argv):
            i += 1; args["config_key"] = argv[i]
        elif a == "--last" and i+1 < len(argv):
            i += 1
            try: args["last"] = int(argv[i])
            except: pass
        elif not a.startswith("--"):
            args["_"].append(a)
        i += 1
    return args


COMMANDS = {
    "validate": cmd_validate,
    "ci": cmd_ci,
    "watch": cmd_watch,
    "compare": cmd_compare,
    "history": cmd_history,
    "preflight": cmd_preflight,
    "init": cmd_init,
    "doctor": cmd_doctor,
    "version": cmd_version,
}

HELP_TEXT = """
  Commands:
    validate <file>     Full validation with forensic report
    ci <file>           CI/CD mode — minimal output, structured exit codes
    watch <file>        Re-validate on file change
    compare <a> <b>     Compare two validation runs
    history             Cross-run trend analysis
    preflight           Mesh/solver pre-flight check
    init                Create simapi.json config
    doctor              Diagnose local environment
    version             Print version

  Options (validate/ci):
    --domain <d>        Simulation domain (auto-detected from filename)
    --report <file.md>  Save full Markdown report
    --export <file.csv> Export clean rows to CSV
    --sarif <file>      Export SARIF for GitHub code scanning
    --json              Machine-readable JSON output
    --fail-on <level>   Exit 1 on: critical (default), review, any
    --config-key <k>    Enable cross-run history tracking

  Integration:
    # GitHub Actions
    simapi ci output.csv --domain aerodynamics --sarif results.sarif

    # Save report
    simapi validate data.csv --report report.md --export clean.csv

    # Watch mode (dev)
    simapi watch output.csv --domain motor_thermal

    # Environment variables
    SIMAPI_DOMAIN=aerodynamics
    SIMAPI_FAIL_ON=critical
    SIMAPI_CONFIG_KEY=my-sim-v2
"""


def print_help():
    banner()
    print(HELP_TEXT)


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("help", "--help", "-h"):
        return print_help()
    cmd, rest = argv[0], argv[1:]
    if cmd in ("--version", "-v", "version"):
        return cmd_version({})
    if cmd not in COMMANDS:
        print(f"\n  {C['red']('✗')} Unknown command: {cmd}")
        print(f"  Run {C['cyan']('simapi help')} for available commands.\n")
        sys.exit(2)
    args = _parse(rest)
    COMMANDS[cmd](args)


if __name__ == "__main__":
    main()
