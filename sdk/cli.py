"""
SimAPI command-line interface.

Runs the dimensional-analysis validation engine (core/dimensional/) locally
against a data file -- no server, no network, no API key. Until now this
engine only shipped through /v1/validate/dimensional; this brings it to the
same terminal that runs the simulation.

Usage:
    simapi dimensional path/to/output.csv
    simapi dimensional data.csv --conditions altitude_m=11000 velocity=45
    simapi dimensional data.json --json > report.json
    simapi dimensional data.csv --max-columns 25 --llm
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def _load_dataframe(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext == ".json":
        raw = json.loads(path.read_text())
        if isinstance(raw, dict) and "trials" in raw:
            raw = raw["trials"]
        if not isinstance(raw, list):
            raw = [raw]
        return pd.DataFrame(raw)
    if ext in (".npy", ".npz"):
        import numpy as np
        arr = np.load(path)
        return pd.DataFrame(arr)
    # Fall back to CSV: catches .tsv, .txt sniffed exports, and unknown
    # extensions that are really comma/tab-separated.
    return pd.read_csv(path)


def _parse_conditions(items: list[str]) -> dict:
    out: dict = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--conditions expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        try:
            out[k.strip()] = float(v)
        except ValueError:
            out[k.strip()] = v
    return out


def _law_to_dict(law) -> dict:
    return {
        "kind": law.kind,
        "label": law.label,
        "columns": list(law.columns),
        "expected_value": law.expected_value,
        "observed_median": law.observed_median,
        "coverage": round(law.coverage, 3),
        "weight": round(law.weight, 3),
        "n_violations": len(law.violated_rows),
        "note": law.note,
    }


def _report_to_dict(report) -> dict:
    return {
        "n_rows": report.n_rows,
        "impossible": sorted(report.impossible_rows),
        "inconsistent": sorted(report.inconsistent_rows),
        "unsuitable_for_training": sorted(report.unsuitable_rows),
        "n_impossible": len(report.impossible_rows),
        "n_inconsistent": len(report.inconsistent_rows),
        "n_unsuitable_for_training": len(report.unsuitable_rows),
        "training_ready": len(report.impossible_rows) == 0,
        "laws_discovered": [_law_to_dict(law) for law in report.laws],
        "row_findings": [
            {
                "row_index": f.row_id,
                "output_class": f.output_class,
                "reason": f.reason,
                "layer": f.layer,
                "weight": round(f.weight, 3),
                "factor": f.factor,
                "counterfactual_repair": f.counterfactual,
            }
            for f in report.row_findings
        ],
        "units_resolved": {
            c: {
                "confidence": round(u.confidence, 2),
                "source": u.source,
                "usable": u.usable,
                "unit_label": u.unit_label,
            }
            for c, u in report.units.columns.items()
        },
        "units_conflicts": [c.__dict__ for c in report.units_conflicts],
        "condition_assertions": [
            {"label": a.label, "declared": a.declared, "implied": a.implied,
             "rel_dev": round(a.rel_dev, 4), "columns": list(a.columns),
             "row_ids": a.row_ids}
            for a in report.condition_assertions
        ],
        "training_suitability": [
            {"kind": s.kind, "detail": s.detail, "columns": list(s.columns),
             "row_ids": s.row_ids, "severity": s.severity}
            for s in report.suitability
        ],
        "suppressions": list(report.suppressions),
    }


def _pretty_print(report, path: Path) -> None:
    n = report.n_rows
    imp = len(report.impossible_rows)
    inc = len(report.inconsistent_rows)
    uns = len(report.unsuitable_rows)
    status = "PASS" if imp == 0 and inc == 0 else "FAIL" if imp else "WARN"

    print(f"SimAPI dimensional validation -- {path}")
    print("-" * 60)
    print(f"Rows:                {n}")
    print(f"Impossible:          {imp}")
    print(f"Inconsistent:        {inc}")
    print(f"Unsuitable-training: {uns}")
    print(f"Training ready:      {'YES' if imp == 0 else 'NO'}")
    print(f"Status:              {status}")
    print()

    if report.laws:
        print(f"Laws discovered ({len(report.laws)}):")
        for law in report.laws:
            v = len(law.violated_rows)
            print(f"  [{law.kind:<18}] {law.label}   ({v} violation{'s' if v != 1 else ''})")
            if law.note:
                print(f"      {law.note}")
        print()

    if report.units_conflicts:
        print("Units conflicts:")
        for c in report.units_conflicts:
            print(f"  {c.column}: {c.note}")
        print()

    if report.condition_assertions:
        print("Declared-condition assertions:")
        for a in report.condition_assertions:
            print(f"  {a.label}: declared={a.declared:g}, implied={a.implied:g}, "
                  f"rel_dev={a.rel_dev:.3f}")
        print()

    if report.row_findings:
        print(f"Row findings ({len(report.row_findings)}), top 20:")
        top = sorted(report.row_findings, key=lambda f: -f.weight)[:20]
        for f in top:
            cf = f" | fix: {f.counterfactual}" if f.counterfactual else ""
            print(f"  row {f.row_id:>5} [{f.output_class}] {f.reason}{cf}")
        print()

    if report.suppressions:
        print("Suppressions (checks not run, with reason):")
        for s in report.suppressions:
            print(f"  - {s}")
        print()


def _cmd_dimensional(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 2

    df = _load_dataframe(path)
    conditions = _parse_conditions(args.conditions or [])

    # Import lazily so `simapi --help` doesn't drag pandas/scipy in when the
    # user just wants to see subcommands.
    from core.dimensional import validate
    resolver = None
    if args.llm:
        from core.dimensional.engine import openrouter_llm_resolver
        resolver = openrouter_llm_resolver

    report = validate(df, conditions=conditions, llm_resolver=resolver,
                       max_columns=args.max_columns)

    if args.json:
        print(json.dumps(_report_to_dict(report), indent=2, default=str))
    else:
        _pretty_print(report, path)

    if len(report.impossible_rows) > 0:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="simapi",
        description="SimAPI command-line -- local validation of simulation output.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser(
        "dimensional",
        help="Run the dimensional-analysis engine locally against a data file.",
        description="Local dimensional validation. No server, no API key.",
    )
    d.add_argument("file", help="Path to CSV / JSON / NPY / NPZ data file.")
    d.add_argument("--conditions", nargs="*", metavar="key=value", default=[],
                   help="Declared conditions, e.g. --conditions altitude_m=11000")
    d.add_argument("--max-columns", type=int, default=15,
                   help="Cap for Pi-basis enumeration (default 15).")
    d.add_argument("--llm", action="store_true",
                   help="Use the OpenRouter LLM fallback for unresolved column units "
                        "(requires OPENROUTER_API_KEY).")
    d.add_argument("--json", action="store_true",
                   help="Emit the full report as JSON on stdout.")
    d.set_defaults(func=_cmd_dimensional)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
