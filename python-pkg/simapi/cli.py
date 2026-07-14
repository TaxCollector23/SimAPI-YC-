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


def cmd_validate(args):
    file = args["_"][0] if args["_"] else None
    if not file:
        _fail(f"Usage: {C['cyan']('simapi validate <file>')}")
    key = _resolve_key()
    if not key:
        _fail(f"Not logged in. Run {C['cyan']('simapi login')} or set SIMAPI_API_KEY.")
    _run_validation(file, key, args)


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


COMMANDS = {
    "login": cmd_login, "logout": cmd_logout, "whoami": cmd_whoami, "init": cmd_init,
    "validate": cmd_validate, "watch": cmd_watch, "usage": cmd_usage,
    "api-key": cmd_api_key, "config": cmd_config, "version": cmd_version,
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
    args = {"_": [], "type": None, "json": False, "fail_on": None, "help": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--help", "-h"):
            args["help"] = True
        elif a == "--json":
            args["json"] = True
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
