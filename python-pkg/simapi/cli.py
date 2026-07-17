"""
SimAPI CLI (Python). Stdlib-only, mirrors the Node CLI:
  login · logout · whoami · init · validate · watch · usage ·
  api-key {show,rotate,delete} · config [set] · version · help
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

VERSION = "1.0.0"
WEB_BASE = os.environ.get("SIMAPI_WEB_URL", "https://sim-api.vercel.app")
API_BASE = os.environ.get("SIMAPI_BASE_URL", "https://sim-api.vercel.app/api")
CONFIG_DIR = Path.home() / ".simapi"
CONFIG_PATH = CONFIG_DIR / "config.json"
USAGE_PATH = CONFIG_DIR / "usage.json"

_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"


def _rgb(r, g, b, s):
    return f"\x1b[38;2;{r};{g};{b}m{s}\x1b[0m" if _COLOR else s


def _sty(code, s):
    return f"\x1b[{code}m{s}\x1b[0m" if _COLOR else s


C = {
    "dim": lambda s: _sty("2", s),
    "bold": lambda s: _sty("1", s),
    "white": lambda s: _sty("97", s),
    "cyan": lambda s: _rgb(34, 211, 238, s),
    "green": lambda s: _rgb(52, 211, 153, s),
    "red": lambda s: _rgb(248, 113, 113, s),
    "amber": lambda s: _rgb(251, 191, 36, s),
}

ART = [
    "███████╗██╗███╗   ███╗ █████╗ ██████╗ ██╗",
    "██╔════╝██║████╗ ████║██╔══██╗██╔══██╗██║",
    "███████╗██║██╔████╔██║███████║██████╔╝██║",
    "╚════██║██║██║╚██╔╝██║██╔══██║██╔═══╝ ██║",
    "███████║██║██║ ╚═╝ ██║██║  ██║██║     ██║",
    "╚══════╝╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝",
]
GRAD = [(34, 211, 238), (42, 190, 240), (50, 170, 243), (55, 150, 245), (58, 135, 246), (59, 130, 246)]


def banner():
    width = shutil.get_terminal_size((80, 24)).columns
    art_w = max(len(line) for line in ART)
    pad = " " * ((width - art_w) // 2) if width >= art_w else ""
    print()
    for i, row in enumerate(ART):
        r, g, b = GRAD[i] if i < len(GRAD) else GRAD[-1]
        print(pad + _rgb(r, g, b, row))
    title = f"SimAPI CLI v{VERSION}"
    tag = "Validate simulation results before they reach production."
    center = lambda s: (" " * ((width - len(s)) // 2) + s) if width >= len(s) else s
    print("\n" + center(C["bold"](C["white"](title))))
    print(center(C["dim"](tag)) + "\n")


def _read_json(path: Path, fallback=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {} if fallback is None else fallback


def _write_json(path: Path, obj):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


def _resolve_key():
    return os.environ.get("SIMAPI_API_KEY") or _read_json(CONFIG_PATH).get("apiKey")


def _mask(key):
    if not key:
        return "—"
    return key if len(key) <= 12 else f"{key[:10]}{'•' * 6}{key[-4:]}"


def _api(path, method="GET", body=None, key=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-API-Key"] = key
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return True, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode())
        except Exception:
            return False, {"error": {"message": str(e)}}
    except urllib.error.URLError as e:
        return False, {"error": {"message": str(e.reason)}}


def _track_usage(ms):
    u = _read_json(USAGE_PATH, {"events": []})
    events = [e for e in u.get("events", []) if time.time() * 1000 - e["t"] < 1000 * 60 * 60 * 24 * 31]
    events.append({"t": time.time() * 1000, "ms": ms})
    _write_json(USAGE_PATH, {"events": events})


def _row(label, value):
    print(f"  {label.ljust(22)} {value}")


def _ok(msg):
    print(f"  {C['green']('✓')} {msg}")


def _fail(msg):
    print(f"  {C['red']('✗')} {msg}")
    sys.exit(1)


# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_login(args):
    banner()
    url = f"{WEB_BASE}/auth?cli=true"
    print(f"  Opening your browser to sign in…\n  {C['cyan'](url)}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print(C["dim"]("  Sign in, copy your API key, then paste it below.\n"))
    key = input("  Paste your SimAPI API key: ").strip()
    if not key:
        _fail("No key entered.")
    print("\n  Verifying…")
    good, resp = _api("/auth/verify", "POST", {"api_key": key})
    if not good:
        _fail(f"Verification failed: {resp.get('error', 'invalid key')}")
    cfg = _read_json(CONFIG_PATH)
    cfg.update({"apiKey": key, "plan": resp.get("plan", "developer"), "email": resp.get("email")})
    _write_json(CONFIG_PATH, cfg)
    print(f"\n  {C['green']('✓')} Authentication successful.")
    print(f"  {C['green']('✓')} API key saved securely. {C['dim'](f'({CONFIG_PATH})')}\n")
    print(f"  You can now run: {C['cyan']('simapi validate simulation.json')}\n")


def cmd_logout(args):
    cfg = _read_json(CONFIG_PATH)
    for k in ("apiKey", "plan", "email"):
        cfg.pop(k, None)
    _write_json(CONFIG_PATH, cfg)
    _ok("Logged out. Local credentials removed.")


def cmd_whoami(args):
    cfg = _read_json(CONFIG_PATH)
    key = os.environ.get("SIMAPI_API_KEY") or cfg.get("apiKey")
    if not key:
        print(f"  Not logged in. Run {C['cyan']('simapi login')}.")
        return
    print(f"\n  {C['bold']('Account')}   {cfg.get('email') or C['dim']('(browser session)')}")
    print(f"  {C['bold']('Plan')}      {cfg.get('plan', 'developer')}")
    print(f"  {C['bold']('API key')}   {C['cyan'](_mask(key))}\n")


def cmd_init(args):
    path = Path("simapi.json")
    if path.exists():
        _fail("simapi.json already exists.")
    path.write_text(json.dumps({
        "$schema": "https://sim-api.vercel.app/schema/simapi.json",
        "simulation_type": "aerodynamics",
        "conditions": {"velocity": 15.0, "altitude": 120.0},
        "files": ["simulation.json"],
        "fail_on": "warning",
    }, indent=2))
    _ok(f"Created simapi.json — edit it, then run {C['cyan']('simapi validate simulation.json')}.")


def _run_validation(file, key, args):
    p = Path(file)
    if not p.exists():
        _fail(f"File not found: {file}")
    try:
        payload = json.loads(p.read_text())
    except Exception as e:
        _fail(f"Could not read {file}: {e}")
    cfg = _read_json(CONFIG_PATH)
    if isinstance(payload, list):
        body = {"data": payload, "simulation_type": args.get("type") or cfg.get("simulation_type", "aerodynamics")}
    else:
        body = {
            "simulation_type": args.get("type") or payload.get("simulation_type") or cfg.get("simulation_type", "aerodynamics"),
            "conditions": payload.get("conditions", {}),
            "data": payload.get("data") or payload.get("trials") or [],
        }
    t0 = time.time()
    good, r = _api("/v1/validate", "POST", body, key)
    _track_usage(int((time.time() - t0) * 1000))
    if not good:
        err = r.get("error", {})
        _fail(f"[{err.get('code', 'error')}] {err.get('message', 'validation error')}")
    if args.get("json"):
        print(json.dumps(r, indent=2))
        return r
    tone = C["green"] if r["status"] == "passed" else C["amber"] if r["status"] == "warning" else C["red"]
    issues = r.get("issues", [])
    physics = [i for i in issues if any(w in (i.get("category") or "") for w in ("physic", "bound", "conserv", "dimension", "cross", "plausib"))]
    constraints = [i for i in issues if i not in physics]
    score = r.get("validation_score", 100 if r["status"] == "passed" else 70 if r["status"] == "warning" else 35)
    print(f"\n  {C['bold']('Validation report')}  {C['dim'](file)}")
    print("  " + "─" * 46)
    _row("Validation score", tone(str(score)))
    _row("Status", tone(r["status"].upper()))
    _row("Warnings", str(r.get("warnings", 0)))
    _row("Constraint violations", str(len(constraints)))
    _row("Physics violations", str(len(physics)))
    _row("Execution time", f"{r.get('processing_ms', '—')}ms")
    if issues:
        print(f"\n  {C['bold']('Issues')}")
        for i in issues[:10]:
            mk = C["red"]("✗") if i["status"] == "failed" else C["amber"]("⚠")
            print(f"   {mk} {i.get('human_name') or i.get('detail') or i['name']}")
    recs = (r.get("ai") or {}).get("recommendations") or []
    if recs:
        print(f"\n  {C['bold']('Recommendations')}")
        for rec in recs[:6]:
            print(f"   {C['cyan']('→')} {rec}")
    print()
    if args.get("fail_on") == "warning" and r["status"] != "passed":
        sys.exit(1)
    if args.get("fail_on") == "failed" and r["status"] == "failed":
        sys.exit(1)
    return r


LAST_RUN_PATH = CONFIG_DIR / "last_run.json"


def cmd_repair(args):
    """Preview (default) or apply automatic structural repairs to a data file."""
    file = args["_"][0] if args["_"] else None
    if not file:
        _fail(f"Usage: {C['cyan']('simapi repair <file> [--apply]')}")
    p = Path(file)
    if not p.exists():
        _fail(f"File not found: {file}")
    try:
        payload = json.loads(p.read_text())
    except Exception as e:
        _fail(f"Could not read {file}: {e}")
    data = payload if isinstance(payload, list) else (payload.get("data") or payload.get("trials") or [])
    if not data:
        _fail("No trial records found in file.")
    key = _resolve_key()
    apply = bool(args.get("apply"))
    good, r = _api("/v1/repair", "POST", {"data": data, "apply": apply}, key)
    if not good:
        _fail(f"[{r.get('error', {}).get('code', 'error')}] {r.get('error', {}).get('message', 'repair failed')}")
    proposals = r.get("proposals", [])
    print(f"\n  {C['bold']('Repair preview')}  {C['dim'](file)}")
    print("  " + "─" * 46)
    if not proposals:
        print(f"  {C['green']('No structural issues found — nothing to repair.')}\n")
        return
    for prop in proposals:
        row_count_label = f"({prop['affected_row_count']} row(s))"
        print(f"\n  {C['amber']('⚠')} {C['bold'](prop['kind'])} {C['dim'](row_count_label)}")
        print(f"    {prop['description']}")
        for ch in prop.get("changes", [])[:5]:
            row_label = f"row {ch['row']}"
            print(f"    {C['dim'](row_label)}  {ch['column']}: {ch['before']} → {C['green'](str(ch['after']))}")
        if prop.get("rows_dropped"):
            print(f"    {C['dim']('drops rows:')} {prop['rows_dropped'][:10]}")
    if r.get("unrepairable"):
        print(f"\n  {C['bold']('Needs manual review')}")
        for u in r["unrepairable"]:
            print(f"    {C['red']('✗')} {u['reason']}")
    print()
    if apply and r.get("repaired_data") is not None:
        out_path = p.with_name(p.stem + ".repaired" + p.suffix)
        out_payload = dict(payload) if isinstance(payload, dict) else {}
        if isinstance(payload, list):
            out_path.write_text(json.dumps(r["repaired_data"], indent=2))
        else:
            out_payload["data"] = r["repaired_data"]
            out_path.write_text(json.dumps(out_payload, indent=2))
        _ok(f"Repaired data written to {out_path}")
    elif not apply and proposals:
        print(f"  {C['dim']('Run')} {C['cyan'](f'simapi repair {file} --apply')} {C['dim']('to write a repaired copy.')}\n")


def cmd_validate(args):
    file = args["_"][0] if args["_"] else None
    if not file:
        _fail(f"Usage: {C['cyan']('simapi validate <file>')}")
    key = _resolve_key()
    if not key:
        _fail(f"Not logged in. Run {C['cyan']('simapi login')} or set SIMAPI_API_KEY.")
    r = _run_validation(file, key, args)
    if r is not None:
        _write_json(LAST_RUN_PATH, {"file": file, "t": time.time() * 1000, "result": r})


def cmd_watch(args):
    file = args["_"][0] if args["_"] else None
    if not file:
        _fail(f"Usage: {C['cyan']('simapi watch <file>')}")
    key = _resolve_key()
    if not key:
        _fail(f"Not logged in. Run {C['cyan']('simapi login')} first.")
    p = Path(file)
    if not p.exists():
        _fail(f"File not found: {file}")
    print(f"\n  {C['cyan']('watching')} {file} — re-validates on change. {C['dim']('Ctrl-C to stop.')}")
    _run_validation(file, key, args)
    last = p.stat().st_mtime
    try:
        while True:
            time.sleep(0.5)
            m = p.stat().st_mtime
            if m != last:
                last = m
                print(f"\n  {C['dim'](time.strftime('%H:%M:%S'))} change detected — re-validating…")
                _run_validation(file, key, args)
    except KeyboardInterrupt:
        print("\n  stopped.\n")


def cmd_usage(args):
    u = _read_json(USAGE_PATH, {"events": []})
    events = u.get("events", [])
    now = time.localtime()
    start_day = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1)) * 1000
    start_month = time.mktime((now.tm_year, now.tm_mon, 1, 0, 0, 0, 0, 0, -1)) * 1000
    today = len([e for e in events if e["t"] >= start_day])
    month = len([e for e in events if e["t"] >= start_month])
    avg = int(sum(e.get("ms", 0) for e in events) / len(events)) if events else 0
    cfg = _read_json(CONFIG_PATH)
    quota = 250000 if cfg.get("plan") == "startup" else 5000
    plan = cfg.get("plan", "developer")
    print(f"\n  {C['bold']('Usage')} {C['dim']('(' + plan + ' plan)')}")
    _row("Requests today", str(today))
    _row("Requests this month", str(month))
    _row("Remaining quota", f"{max(0, quota - month):,} / {quota:,}")
    _row("Avg validation time", f"{avg}ms" if avg else "—")
    print()


def cmd_api_key(args):
    sub = args["_"][0] if args["_"] else None
    key = _resolve_key()
    if sub == "show":
        if not key:
            print("  No API key configured. Run simapi login.")
            return
        print(f"  Active key: {C['cyan'](_mask(key))}")
    elif sub == "rotate":
        if not key:
            _fail("Nothing to rotate — run simapi login first.")
        good, resp = _api("/auth/rotate", "POST", {"api_key": key})
        if not good:
            _fail("Rotate failed.")
        cfg = _read_json(CONFIG_PATH)
        cfg["apiKey"] = resp["api_key"]
        _write_json(CONFIG_PATH, cfg)
        _ok(f"New key issued: {C['cyan'](_mask(resp['api_key']))} {C['dim']('(previous key invalidated)')}")
    elif sub == "delete":
        cfg = _read_json(CONFIG_PATH)
        cfg.pop("apiKey", None)
        _write_json(CONFIG_PATH, cfg)
        _ok("API key deleted from this machine.")
    else:
        _fail(f"Usage: {C['cyan']('simapi api-key <show|rotate|delete>')}")


def cmd_config(args):
    if args["_"] and args["_"][0] == "set":
        rest = args["_"][1:]
        if len(rest) < 2:
            _fail(f"Usage: {C['cyan']('simapi config set <key> <value>')}")
        k, v = rest[0], " ".join(rest[1:])
        cfg = _read_json(CONFIG_PATH)
        cfg[k] = True if v == "true" else False if v == "false" else v
        _write_json(CONFIG_PATH, cfg)
        _ok(f"Set {C['bold'](k)} = {cfg[k]}")
        return
    cfg = _read_json(CONFIG_PATH)
    if cfg.get("apiKey"):
        cfg = {**cfg, "apiKey": _mask(cfg["apiKey"])}
    print(f"\n  {C['bold']('Configuration')} {C['dim'](f'({CONFIG_PATH})')}")
    if not cfg:
        print(C["dim"]("  (empty — run simapi login)"))
    for k, v in cfg.items():
        _row(k, str(v))
    print()


def cmd_version(args):
    banner()
    print(f"  {C['bold'](f'v{VERSION}')}  {C['dim'](f'python {sys.version.split()[0]}')}\n")


def cmd_doctor(args):
    """Diagnose the local CLI environment: config, credentials, connectivity, project file."""
    fix = "--fix" in args["_"] or args.get("fix")
    print(f"\n  {C['bold']('SimAPI doctor')}")
    print("  " + "─" * 46)
    problems = 0

    if CONFIG_DIR.exists() and os.access(CONFIG_DIR, os.W_OK):
        _ok(f"Config directory writable ({CONFIG_DIR})")
    else:
        if fix:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            _ok(f"Created config directory ({CONFIG_DIR})")
        else:
            print(f"  {C['red']('✗')} Config directory missing or not writable ({CONFIG_DIR})")
            print(f"    {C['dim']('fix: simapi doctor --fix')}")
            problems += 1

    key = _resolve_key()
    if key:
        _ok(f"API key configured ({_mask(key)})")
    else:
        print(f"  {C['amber']('⚠')} No API key configured")
        print(f"    {C['dim']('fix: simapi login')}")
        problems += 1

    py_ok = sys.version_info >= (3, 8)
    if py_ok:
        _ok(f"Python {sys.version.split()[0]} (>= 3.8 required)")
    else:
        print(f"  {C['red']('✗')} Python {sys.version.split()[0]} is below the minimum supported version (3.8)")
        problems += 1

    t0 = time.time()
    good, resp = _api("/v1/health", "GET")
    latency_ms = int((time.time() - t0) * 1000)
    if good:
        engine = resp.get("engine", "unknown")
        _ok(f"API reachable at {API_BASE} ({latency_ms}ms, engine={engine})")
    else:
        print(f"  {C['red']('✗')} API unreachable at {API_BASE}: {resp.get('error', {}).get('message', 'connection failed')}")
        problems += 1

    cfg_path = Path("simapi.json")
    if cfg_path.exists():
        try:
            json.loads(cfg_path.read_text())
            _ok("simapi.json found and valid")
        except Exception as e:
            print(f"  {C['red']('✗')} simapi.json exists but is not valid JSON: {e}")
            problems += 1
    else:
        print(f"  {C['dim']('·')} No simapi.json in this directory {C['dim']('(optional — run simapi init)')}")

    print("  " + "─" * 46)
    if problems == 0:
        print(f"  {C['green']('All checks passed.')}\n")
    else:
        suffix = "" if fix else f" — run {C['cyan']('simapi doctor --fix')} to auto-fix what's fixable"
        print(f"  {C['amber'](f'{problems} issue(s) found')}{suffix}\n")


def cmd_explain(args):
    """Explain the issues from the most recent `simapi validate` run in detail."""
    cached = _read_json(LAST_RUN_PATH, None)
    if not cached:
        _fail(f"No cached validation run. Run {C['cyan']('simapi validate <file>')} first.")
    r = cached["result"]
    age_s = time.time() - cached["t"] / 1000
    print(f"\n  {C['bold']('Explaining')} {C['dim'](cached['file'])} {C['dim'](f'(validated {int(age_s)}s ago)')}")
    print("  " + "─" * 46)
    issues = r.get("issues", [])
    if not issues:
        print(f"  {C['green']('No issues were found in this run.')}\n")
        return
    for i, issue in enumerate(issues, 1):
        mk = C["red"]("✗") if issue.get("status") == "failed" else C["amber"]("⚠")
        name = issue.get("human_name") or issue.get("name", "unnamed check")
        print(f"\n  {mk} {C['bold'](f'{i}. {name}')}")
        if issue.get("category"):
            _row("Category", issue["category"])
        if issue.get("detail"):
            _row("Detail", issue["detail"])
        if issue.get("value") is not None:
            _row("Value", str(issue["value"]))
    exclusions = r.get("exclusions", [])
    if exclusions:
        print(f"\n  {C['bold']('Excluded trials')} {C['dim'](f'({len(exclusions)})')}")
        for e in exclusions[:10]:
            _row(f"Trial {e.get('trial_number', e.get('trial_index'))}", e.get("reason", ""))
        if len(exclusions) > 10:
            print(f"  {C['dim'](f'… and {len(exclusions) - 10} more')}")
    print()


COMMANDS = {
    "login": cmd_login, "logout": cmd_logout, "whoami": cmd_whoami, "init": cmd_init,
    "validate": cmd_validate, "watch": cmd_watch, "usage": cmd_usage,
    "api-key": cmd_api_key, "config": cmd_config, "version": cmd_version,
    "doctor": cmd_doctor, "explain": cmd_explain, "repair": cmd_repair,
}

HELP = {
    "login": ("simapi login", "Authenticate via the browser and save your API key."),
    "logout": ("simapi logout", "Remove locally stored credentials."),
    "whoami": ("simapi whoami", "Show the authenticated account, plan, and masked API key."),
    "init": ("simapi init", "Create a simapi.json config in the current project."),
    "validate": ("simapi validate <file>", "Validate a simulation file and print the report."),
    "watch": ("simapi watch <file>", "Re-run validation whenever the file changes."),
    "usage": ("simapi usage", "Show requests today/month, remaining quota, and average time."),
    "api-key": ("simapi api-key <show|rotate|delete>", "Manage your API key."),
    "config": ("simapi config [set <key> <value>]", "Show or update CLI configuration."),
    "version": ("simapi version", "Print the installed CLI version."),
    "doctor": ("simapi doctor [--fix]", "Diagnose config, credentials, connectivity, and project setup."),
    "explain": ("simapi explain", "Explain the issues from the most recent validation run in detail."),
    "repair": ("simapi repair <file> [--apply]", "Preview or apply automatic structural repairs to a data file."),
}


def print_help():
    banner()
    print(f"  {C['bold']('Usage')}\n    simapi {C['dim']('<command> [options]')}\n")
    print(f"  {C['bold']('Commands')}")
    items = [
        ("login", "Authenticate and save your API key"),
        ("logout", "Remove stored credentials"),
        ("whoami", "Show account, plan, and masked key"),
        ("init", "Create a simapi.json config"),
        ("validate <file>", "Validate a simulation file"),
        ("watch <file>", "Re-validate on file change"),
        ("usage", "Show API usage statistics"),
        ("api-key <cmd>", "show · rotate · delete"),
        ("config [set]", "Show or update configuration"),
        ("doctor [--fix]", "Diagnose config, auth, and connectivity"),
        ("explain", "Explain the last validation run in detail"),
        ("repair <file> [--apply]", "Preview or apply automatic repairs"),
        ("version", "Show the CLI version"),
        ("help", "Show this help"),
    ]
    for name, desc in items:
        print(f"    {C['cyan'](name.ljust(18))} {C['dim'](desc)}")
    print(f"\n  {C['dim']('Run')} {C['cyan']('simapi <command> --help')} {C['dim']('for details.')}\n")


def print_command_help(name):
    if name not in HELP:
        return print_help()
    usage, desc = HELP[name]
    print(f"\n  {C['bold'](name)} — {desc}\n")
    print(f"  {C['bold']('Usage')}\n    {C['cyan'](usage)}\n")


def parse(argv):
    args = {"_": [], "type": None, "json": False, "fail_on": None, "help": False, "fix": False, "apply": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--help", "-h"):
            args["help"] = True
        elif a == "--json":
            args["json"] = True
        elif a == "--fix":
            args["fix"] = True
        elif a == "--apply":
            args["apply"] = True
        elif a == "--type":
            i += 1
            args["type"] = argv[i] if i < len(argv) else None
        elif a == "--fail-on":
            i += 1
            args["fail_on"] = argv[i] if i < len(argv) else None
        else:
            args["_"].append(a)
        i += 1
    return args


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("help", "--help", "-h"):
        return print_help()
    cmd, rest = argv[0], argv[1:]
    if cmd in ("--version", "-v"):
        return cmd_version({})
    name = "api-key" if cmd in ("api-key", "apikey") else cmd
    if name not in COMMANDS:
        _fail(f"Unknown command: {cmd}")
    args = parse(rest)
    if args["help"]:
        return print_command_help(name)
    COMMANDS[name](args)


if __name__ == "__main__":
    main()
