#!/usr/bin/env node
/**
 * SimAPI CLI.
 *
 * Zero runtime dependencies (Node 18+ built-ins only). The hosted API is
 * open by default -- no account or sign-in required. An API key is only
 * relevant if you're running your own deployment with SIMAPI_API_KEYS set.
 *   init · validate · ci · watch · usage ·
 *   api-key {show,set,generate,delete} · config [set] · doctor · version · help
 */
import { readFile, writeFile, mkdir, stat } from "node:fs/promises";
import { watch as fsWatch, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline/promises";
import { stdin, stdout, platform, env } from "node:process";
import { exec } from "node:child_process";

const VERSION = "1.1.2";
const WEB_BASE = env.SIMAPI_WEB_URL || "https://sim-api.vercel.app";
const API_BASE = env.SIMAPI_BASE_URL || "https://sim-api.vercel.app/api";
const CONFIG_DIR = join(homedir(), ".simapi");
const CONFIG_PATH = join(CONFIG_DIR, "config.json");
const USAGE_PATH = join(CONFIG_DIR, "usage.json");
const LAST_RUN_PATH = join(CONFIG_DIR, "last_run.json");

// ── Colors ────────────────────────────────────────────────────────────────────
const COLOR = stdout.isTTY && !env.NO_COLOR && env.TERM !== "dumb";
const rgb = (r, g, b, s) => (COLOR ? `\x1b[38;2;${r};${g};${b}m${s}\x1b[0m` : s);
const c = {
  dim: (s) => (COLOR ? `\x1b[2m${s}\x1b[0m` : s),
  bold: (s) => (COLOR ? `\x1b[1m${s}\x1b[0m` : s),
  cyan: (s) => rgb(34, 211, 238, s),
  blue: (s) => rgb(59, 130, 246, s),
  green: (s) => rgb(52, 211, 153, s),
  red: (s) => rgb(248, 113, 113, s),
  amber: (s) => rgb(251, 191, 36, s),
  white: (s) => (COLOR ? `\x1b[97m${s}\x1b[0m` : s),
};

// ── Startup banner ──────────────────────────────────────────────────────────────
const ART = [
  "███████╗██╗███╗   ███╗ █████╗ ██████╗ ██╗",
  "██╔════╝██║████╗ ████║██╔══██╗██╔══██╗██║",
  "███████╗██║██╔████╔██║███████║██████╔╝██║",
  "╚════██║██║██║╚██╔╝██║██╔══██║██╔═══╝ ██║",
  "███████║██║██║ ╚═╝ ██║██║  ██║██║     ██║",
  "╚══════╝╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝",
];
// Subtle cyan → blue vertical gradient across the six rows.
const GRAD = [
  [34, 211, 238],
  [42, 190, 240],
  [50, 170, 243],
  [55, 150, 245],
  [58, 135, 246],
  [59, 130, 246],
];

function banner() {
  const width = stdout.columns || 80;
  const artWidth = Math.max(...ART.map((l) => [...l].length));
  const pad = width >= artWidth ? " ".repeat(Math.floor((width - artWidth) / 2)) : "";
  const line = (s) => (width >= artWidth ? pad + s : s); // never wrap; left-align when narrow

  stdout.write("\n");
  ART.forEach((row, i) => {
    const [r, g, b] = GRAD[i] ?? GRAD[GRAD.length - 1];
    stdout.write(line(rgb(r, g, b, row)) + "\n");
  });
  const title = `SimAPI CLI v${VERSION}`;
  const tag = "Validate simulation results before they reach production.";
  const centerText = (s) => (width >= s.length ? " ".repeat(Math.floor((width - s.length) / 2)) + s : s);
  stdout.write("\n" + centerText(c.bold(c.white(title))) + "\n");
  stdout.write(centerText(c.dim(tag)) + "\n\n");
}

// ── Config / usage stores ────────────────────────────────────────────────────────
async function readJson(path, fallback = {}) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return fallback;
  }
}
async function writeJson(path, obj) {
  // 0o700 on the dir, 0o600 on the file: the config carries the user's
  // API key in cleartext (see mask() -- that's for display only). Default
  // umask 022 would leave it world-readable, so any local user could
  // `cat ~otheruser/.simapi/config.json` and read the key.
  if (!existsSync(CONFIG_DIR)) await mkdir(CONFIG_DIR, { recursive: true, mode: 0o700 });
  await writeFile(path, JSON.stringify(obj, null, 2), { mode: 0o600 });
}
const readConfig = () => readJson(CONFIG_PATH);
const writeConfig = (o) => writeJson(CONFIG_PATH, o);
async function resolveKey() {
  return env.SIMAPI_API_KEY || (await readConfig()).apiKey || null;
}
function mask(key) {
  if (!key) return "—";
  return key.length <= 12 ? key : `${key.slice(0, 10)}${"•".repeat(6)}${key.slice(-4)}`;
}

async function trackUsage(ms) {
  const u = await readJson(USAGE_PATH, { events: [] });
  u.events = (u.events || []).filter((e) => Date.now() - e.t < 1000 * 60 * 60 * 24 * 31);
  u.events.push({ t: Date.now(), ms });
  await writeJson(USAGE_PATH, u);
}

// ── HTTP ──────────────────────────────────────────────────────────────────────
async function api(path, { method = "GET", body, key } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(key ? { "X-API-Key": key } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  // Non-JSON error bodies (Vercel/proxy HTML 5xx pages, plain-text
  // gateway errors) used to make JSON.parse throw, hiding the real HTTP
  // status behind "Unexpected token < ...". Return the raw text so
  // callers can surface it verbatim.
  let json = {};
  if (text) {
    try { json = JSON.parse(text); }
    catch { return { ok: res.ok, status: res.status, json: {}, text }; }
  }
  return { ok: res.ok, status: res.status, json, text };
}

function openBrowser(url) {
  const cmd = platform === "darwin" ? `open "${url}"` : platform === "win32" ? `start "" "${url}"` : `xdg-open "${url}"`;
  exec(cmd, () => {});
}

async function prompt(question) {
  const rl = createInterface({ input: stdin, output: stdout });
  const answer = await rl.question(question);
  rl.close();
  return answer.trim();
}

// ── Commands ────────────────────────────────────────────────────────────────────
const commands = {
  async init() {
    const file = "simapi.json";
    if (existsSync(file)) return fail(`${file} already exists.`);
    const config = {
      $schema: "https://sim-api.vercel.app/schema/simapi.json",
      simulation_type: "aerodynamics",
      conditions: { velocity: 15.0, altitude: 120.0 },
      files: ["simulation.json"],
      fail_on: "warning",
    };
    await writeFile(file, JSON.stringify(config, null, 2));
    ok(`Created ${file} — edit it, then run ${c.cyan("simapi validate simulation.json")}.`);
  },

  async validate(args) {
    const file = args._[0];
    if (!file) return fail(`Usage: ${c.cyan("simapi validate <file>")}`);
    const key = await resolveKey();
    await runValidation(file, key, args);
  },

  // CI gate: validate a file and exit non-zero when the gate fails, so a
  // pipeline step blocks a bad simulation from merging. `--json` prints a
  // compact machine-readable verdict for downstream tooling; otherwise a
  // terse pass/fail summary is printed. The file may be omitted when
  // simapi.json declares a "files" entry.
  async ci(args) {
    const cfg = await readConfig();
    const file = args._[0] || (Array.isArray(cfg.files) ? cfg.files[0] : cfg.files);
    if (!file) {
      return fail(`Usage: ${c.cyan("simapi ci <file>")} ${c.dim('(or set "files" in simapi.json)')}`);
    }
    const key = await resolveKey();
    // A CI gate is strict by default: any non-passing status blocks. Override
    // with --fail-on failed to allow warnings through, or set fail_on in config.
    const level = args["fail-on"] || cfg.fail_on || "warning";

    const out = await validateOnce(file, key, args);
    if (!out.ok) {
      if (args.json) {
        stdout.write(JSON.stringify({ ok: false, gate: "error", file, error: stripAnsi(out.error) }, null, 2) + "\n");
      } else {
        fail(out.error);
      }
      process.exitCode = 1;
      return;
    }

    const r = out.result;
    const failCount = (r.issues || []).filter((i) => i.status === "failed").length;
    const warnCount = (r.issues || []).filter((i) => i.status === "warning").length;
    const gateFails = level === "failed" ? r.status === "failed" : r.status !== "passed";

    // Write CI artifacts (SARIF/JUnit) if requested. Best-effort: a report
    // failure is surfaced but never changes the gate's exit code, so a pipeline
    // that only wants the gate is never broken by an export hiccup.
    let reports = [];
    let reportError = null;
    if (args.sarif || args.junit) {
      try { reports = await writeReports(out.body, key, args); }
      catch (e) { reportError = stripAnsi(e.message); }
    }

    if (args.json) {
      stdout.write(JSON.stringify({
        ok: !gateFails,
        gate: gateFails ? "fail" : "pass",
        file,
        status: r.status,
        fail_on: level,
        trials_submitted: r.trials_submitted ?? null,
        trials_valid: r.trials_valid ?? null,
        failed: failCount,
        warnings: warnCount,
        training_ready: !!r.training_ready,
        processing_ms: r.processing_ms ?? null,
        job_id: r.job_id ?? null,
        reports: reports.map((x) => ({ format: x.format, path: x.path })),
        report_error: reportError,
      }, null, 2) + "\n");
    } else {
      const tone = gateFails ? c.red : c.green;
      const mark = gateFails ? "✗" : "✓";
      const label = gateFails ? "GATE FAILED" : "GATE PASSED";
      stdout.write(`\n  ${tone(c.bold(`${mark} ${label}`))}  ${c.dim(file)}\n`);
      row("Status", (r.status || "unknown").toUpperCase());
      row("Trials", `${r.trials_valid ?? "—"} valid / ${r.trials_submitted ?? "—"}`);
      row("Findings", `${failCount ? c.red(failCount + " failed") : "0 failed"}   ${warnCount ? c.amber(warnCount + " warnings") : "0 warnings"}`);
      row("Fail-on", level);
      row("Training ready", r.training_ready ? c.green("yes") : c.red("no"));
      const blocking = (r.issues || []).filter((i) => (level === "failed" ? i.status === "failed" : true));
      if (gateFails && blocking.length) {
        stdout.write(`\n  ${c.bold("Blocking issues")}\n`);
        for (const i of blocking.slice(0, 10)) {
          const mk = i.status === "failed" ? c.red("✗") : c.amber("⚠");
          stdout.write(`   ${mk} ${i.human_name || i.name}\n`);
        }
        if (blocking.length > 10) stdout.write(`   ${c.dim(`… and ${blocking.length - 10} more`)}\n`);
      }
      for (const rep of reports) row(rep.format.toUpperCase() + " report", c.dim(rep.path));
      if (reportError) stdout.write(`   ${c.amber("⚠")} ${reportError}\n`);
      stdout.write("\n");
    }

    if (gateFails) process.exitCode = 1;
  },

  async dimensional(args) {
    const file = args._[0];
    if (!file) return fail(`Usage: ${c.cyan("simapi dimensional <file.csv|file.json>")}`);
    if (!existsSync(file)) return fail(`File not found: ${file}`);
    const key = await resolveKey();
    if (!key) return fail(`Not logged in. Run ${c.cyan("simapi login")} or set SIMAPI_API_KEY.`);

    let records;
    try { records = await readRecords(file); }
    catch (e) { return fail(`Could not read ${file}: ${e.message}`); }
    if (!records.length) return fail(`${file} contains no rows.`);

    const conditions = {};
    for (const kv of (args.conditions || "").split(",")) {
      if (!kv) continue;
      const [k, v] = kv.split("=");
      if (!k || v === undefined) continue;
      const n = Number(v);
      conditions[k.trim()] = Number.isNaN(n) ? v : n;
    }

    const t0 = Date.now();
    let res;
    try {
      res = await api("/v1/validate/dimensional", {
        method: "POST",
        body: { data: records, conditions },
        key,
      });
    } catch (e) {
      return fail(`Request failed: ${e.message} ${c.dim(`(is ${API_BASE} reachable?)`)}`);
    }
    await trackUsage(Date.now() - t0);
    if (!res.ok) {
      const err = res.json?.error || {};
      return fail(`[${err.code || res.status}] ${err.message || "dimensional validation error"}`);
    }
    const r = res.json;
    await writeJson(LAST_RUN_PATH, { file, t: Date.now(), result: r, engine: "dimensional" });
    if (args.json) return stdout.write(JSON.stringify(r, null, 2) + "\n");

    renderDimensionalReport(r, file);
    if (args["fail-on"] === "warning" && (r.n_impossible || r.n_inconsistent)) process.exitCode = 1;
    if (args["fail-on"] === "failed" && r.n_impossible) process.exitCode = 1;
    if (!args["fail-on"] && r.n_impossible) process.exitCode = 1;
  },

  async watch(args) {
    const file = args._[0];
    if (!file) return fail(`Usage: ${c.cyan("simapi watch <file>")}`);
    const key = await resolveKey();
    if (!existsSync(file)) return fail(`File not found: ${file}`);
    stdout.write(`\n  ${c.cyan("watching")} ${file} — re-validates on change. ${c.dim("Ctrl-C to stop.")}\n`);
    await runValidation(file, key, args);
    let busy = false;
    let timer = null;
    fsWatch(file, () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        if (busy) return;
        busy = true;
        stdout.write(`\n  ${c.dim(new Date().toLocaleTimeString())} change detected — re-validating…\n`);
        await runValidation(file, key, args);
        busy = false;
      }, 150);
    });
  },

  async usage() {
    const u = await readJson(USAGE_PATH, { events: [] });
    const events = u.events || [];
    const now = new Date();
    const startDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const startMonth = new Date(now.getFullYear(), now.getMonth(), 1).getTime();
    const today = events.filter((e) => e.t >= startDay).length;
    const month = events.filter((e) => e.t >= startMonth).length;
    const avg = events.length ? Math.round(events.reduce((a, e) => a + (e.ms || 0), 0) / events.length) : 0;
    const cfg = await readConfig();
    const quota = cfg.plan === "startup" ? 250000 : 5000;
    stdout.write(`\n  ${c.bold("Usage")} ${c.dim(`(${cfg.plan || "developer"} plan)`)}\n`);
    row("Requests today", String(today));
    row("Requests this month", String(month));
    row("Remaining quota", `${Math.max(0, quota - month).toLocaleString()} / ${quota.toLocaleString()}`);
    row("Avg validation time", avg ? `${avg}ms` : "—");
    stdout.write("\n");
  },

  async "api-key"(args) {
    const sub = args._[0];
    const key = await resolveKey();
    if (sub === "show") {
      if (!key) return info("No API key configured. The hosted API doesn't require one.");
      return info(`Active key: ${c.cyan(mask(key))}`);
    }
    if (sub === "generate") {
      const { ok: good, json } = await api("/v1/keys/generate", { method: "POST", body: { label: args._[1] || "CLI" } });
      if (!good) return fail(`Key generation failed: ${json?.error || "server error"}`);
      const cfg = await readConfig();
      await writeConfig({ ...cfg, apiKey: json.api_key });
      return ok(`New key issued and saved: ${c.cyan(mask(json.api_key))}`);
    }
    if (sub === "set") {
      const value = args._[1];
      if (!value) return fail(`Usage: ${c.cyan("simapi api-key set <key>")}`);
      const cfg = await readConfig();
      await writeConfig({ ...cfg, apiKey: value });
      return ok(`API key saved: ${c.cyan(mask(value))}`);
    }
    if (sub === "delete") {
      const cfg = await readConfig();
      delete cfg.apiKey;
      await writeConfig(cfg);
      return ok("API key deleted from this machine.");
    }
    return fail(`Usage: ${c.cyan("simapi api-key <show|generate|set|delete>")}`);
  },

  async config(args) {
    if (args._[0] === "set") {
      const [, k, ...rest] = args._;
      const v = rest.join(" ");
      if (!k) return fail(`Usage: ${c.cyan("simapi config set <key> <value>")}`);
      const cfg = await readConfig();
      cfg[k] = v === "true" ? true : v === "false" ? false : /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : v;
      await writeConfig(cfg);
      return ok(`Set ${c.bold(k)} = ${cfg[k]}`);
    }
    const cfg = await readConfig();
    const shown = { ...cfg };
    if (shown.apiKey) shown.apiKey = mask(shown.apiKey);
    stdout.write(`\n  ${c.bold("Configuration")} ${c.dim(`(${CONFIG_PATH})`)}\n`);
    const keys = Object.keys(shown);
    if (keys.length === 0) stdout.write(c.dim("  (empty — nothing configured yet)\n"));
    for (const k of keys) row(k, String(shown[k]));
    stdout.write("\n");
  },

  async domains() {
    const list = [
      "aerodynamics", "fluid_dynamics", "structural", "thermodynamics", "robotics",
      "combustion", "acoustics", "electromagnetics", "geomechanics", "biomechanics",
      "nuclear", "plasma", "chemical", "hydrodynamics", "meteorology", "astrophysics",
      "materials", "tribology", "aeroelasticity", "cryogenics", "multiphysics",
    ];
    stdout.write(`\n  ${c.bold("Supported simulation types")} ${c.dim(`(${list.length})`)}\n`);
    for (const d of list) stdout.write(`   ${c.cyan("•")} ${d}\n`);
    stdout.write(`\n  Use with: ${c.cyan("simapi validate run.json --type <domain>")}\n\n`);
  },

  async doctor(args) {
    const fix = !!args["fix"] || args._.includes("--fix");
    stdout.write(`\n  ${c.bold("SimAPI doctor")}\n`);
    stdout.write("  " + "─".repeat(46) + "\n");
    let problems = 0;

    if (existsSync(CONFIG_DIR)) {
      ok(`Config directory writable (${CONFIG_DIR})`);
    } else if (fix) {
      await mkdir(CONFIG_DIR, { recursive: true });
      ok(`Created config directory (${CONFIG_DIR})`);
    } else {
      stdout.write(`  ${c.red("✗")} Config directory missing (${CONFIG_DIR})\n    ${c.dim("fix: simapi doctor --fix")}\n`);
      problems++;
    }

    const nodeMajor = Number(process.versions.node.split(".")[0]);
    if (nodeMajor >= 18) ok(`Node ${process.version} (>= 18 required)`);
    else {
      stdout.write(`  ${c.red("✗")} Node ${process.version} is below the minimum supported version (18)\n`);
      problems++;
    }

    const key = await resolveKey();
    if (key) ok(`API key configured (${mask(key)})`);
    else stdout.write(`  ${c.dim("·")} No API key configured — not required for the hosted API. ${c.dim("(simapi api-key generate)")}\n`);

    try {
      const t = Date.now();
      const res = await api("/v1/health");
      if (res.ok) ok(`API reachable at ${API_BASE} (${Date.now() - t}ms, engine=${res.json.engine || "unknown"})`);
      else {
        stdout.write(`  ${c.red("✗")} API returned HTTP ${res.status} at ${API_BASE}\n`);
        problems++;
      }
    } catch (e) {
      stdout.write(`  ${c.red("✗")} API unreachable at ${API_BASE}: ${e.message}\n`);
      problems++;
    }

    if (existsSync("simapi.json")) {
      try {
        JSON.parse(await readFile("simapi.json", "utf8"));
        ok("simapi.json found and valid");
      } catch (e) {
        stdout.write(`  ${c.red("✗")} simapi.json exists but is not valid JSON: ${e.message}\n`);
        problems++;
      }
    } else {
      stdout.write(`  ${c.dim("·")} No simapi.json in this directory ${c.dim("(optional — run simapi init)")}\n`);
    }

    stdout.write("  " + "─".repeat(46) + "\n");
    if (problems === 0) stdout.write(`  ${c.green("All checks passed.")}\n\n`);
    else stdout.write(`  ${c.amber(`${problems} issue(s) found`)}${fix ? "" : ` — run ${c.cyan("simapi doctor --fix")} to auto-fix what's fixable`}\n\n`);
  },

  async repair(args) {
    const file = args._[0];
    if (!file) return fail(`Usage: ${c.cyan("simapi repair <file> [--apply]")}`);
    if (!existsSync(file)) return fail(`File not found: ${file}`);
    let payload;
    try {
      payload = JSON.parse(await readFile(file, "utf8"));
    } catch (e) {
      return fail(`Could not read ${file}: ${e.message}`);
    }
    const data = Array.isArray(payload) ? payload : payload.data || payload.trials || [];
    if (!data.length) return fail("No trial records found in file.");
    const key = await resolveKey();
    const apply = !!args.apply;
    const res = await api("/v1/repair", { method: "POST", body: { data, apply }, key });
    if (!res.ok) {
      const err = res.json?.error || {};
      return fail(`[${err.code || res.status}] ${err.message || "repair failed"}`);
    }
    const r = res.json;
    const proposals = r.proposals || [];
    stdout.write(`\n  ${c.bold("Repair preview")}  ${c.dim(file)}\n`);
    stdout.write("  " + "─".repeat(46) + "\n");
    if (!proposals.length) {
      stdout.write(`  ${c.green("No structural issues found — nothing to repair.")}\n\n`);
      return;
    }
    for (const prop of proposals) {
      stdout.write(`\n  ${c.amber("⚠")} ${c.bold(prop.kind)} ${c.dim(`(${prop.affected_row_count} row(s))`)}\n`);
      stdout.write(`    ${prop.description}\n`);
      for (const ch of (prop.changes || []).slice(0, 5)) {
        stdout.write(`    ${c.dim(`row ${ch.row}`)}  ${ch.column}: ${ch.before} → ${c.green(String(ch.after))}\n`);
      }
      if (prop.rows_dropped && prop.rows_dropped.length) {
        stdout.write(`    ${c.dim("drops rows:")} ${prop.rows_dropped.slice(0, 10).join(", ")}\n`);
      }
    }
    if (r.unrepairable && r.unrepairable.length) {
      stdout.write(`\n  ${c.bold("Needs manual review")}\n`);
      for (const u of r.unrepairable) stdout.write(`    ${c.red("✗")} ${u.reason}\n`);
    }
    stdout.write("\n");
    if (apply && r.repaired_data) {
      const dot = file.lastIndexOf(".");
      const outPath = dot > -1 ? `${file.slice(0, dot)}.repaired${file.slice(dot)}` : `${file}.repaired`;
      const outPayload = Array.isArray(payload) ? r.repaired_data : { ...payload, data: r.repaired_data };
      await writeFile(outPath, JSON.stringify(outPayload, null, 2));
      ok(`Repaired data written to ${outPath}`);
    } else if (!apply && proposals.length) {
      stdout.write(`  ${c.dim("Run")} ${c.cyan(`simapi repair ${file} --apply`)} ${c.dim("to write a repaired copy.")}\n\n`);
    }
  },

  async explain() {
    const cached = await readJson(LAST_RUN_PATH, null);
    if (!cached) return fail(`No cached validation run. Run ${c.cyan("simapi validate <file>")} first.`);
    const r = cached.result;
    const ageS = Math.round((Date.now() - cached.t) / 1000);
    stdout.write(`\n  ${c.bold("Explaining")} ${c.dim(cached.file)} ${c.dim(`(validated ${ageS}s ago)`)}\n`);
    stdout.write("  " + "─".repeat(46) + "\n");
    const issues = r.issues || [];
    if (!issues.length) {
      stdout.write(`  ${c.green("No issues were found in this run.")}\n\n`);
      return;
    }
    issues.forEach((issue, idx) => {
      const mk = issue.status === "failed" ? c.red("✗") : c.amber("⚠");
      const name = issue.human_name || issue.name || "unnamed check";
      stdout.write(`\n  ${mk} ${c.bold(`${idx + 1}. ${name}`)}\n`);
      if (issue.category) row("Category", issue.category);
      if (issue.detail) row("Detail", issue.detail);
      if (issue.value !== undefined && issue.value !== null) row("Value", String(issue.value));
    });
    const exclusions = r.exclusions || [];
    if (exclusions.length) {
      stdout.write(`\n  ${c.bold(`Excluded trials (${exclusions.length})`)}\n`);
      for (const e of exclusions.slice(0, 10)) row(`Trial ${e.trial_number ?? e.trial_index}`, e.reason || "");
      if (exclusions.length > 10) stdout.write(`  ${c.dim(`… and ${exclusions.length - 10} more`)}\n`);
    }
    stdout.write("\n");
  },

  async open() {
    const url = `${WEB_BASE}/dashboard`;
    ok(`Opening ${c.cyan(url)}`);
    openBrowser(url);
  },

  // Open the browser setup page to generate and copy an API key. The hosted API
  // is open by default, so this is optional — needed only for higher limits,
  // gated/private deployments, or the dimensional engine.
  async login() {
    const url = `${WEB_BASE}/auth?cli=true`;
    ok(`Opening ${c.cyan(url)}`);
    stdout.write(`  ${c.dim("Generate a key there, then run:")}  ${c.cyan("simapi config set api_key <key>")}\n`);
    stdout.write(`  ${c.dim("The API is open by default — a key is only needed for gated deployments or higher limits.")}\n\n`);
    openBrowser(url);
  },

  version() {
    banner();
    stdout.write(`  ${c.bold(`v${VERSION}`)}  ${c.dim(`node ${process.version}`)}\n\n`);
  },

  help() {
    printHelp();
  },
};

// Minimal CSV → array-of-objects. Handles double-quoted fields (with escaped
// "" inside), commas inside quotes, and CRLF. Not a full RFC 4180 parser, but
// enough for the simulation-output CSVs the dimensional engine sees.
function parseCsv(text) {
  const rows = [];
  let field = "";
  let row = [];
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else inQuotes = false;
      } else field += ch;
    } else {
      if (ch === '"') inQuotes = true;
      else if (ch === ",") { row.push(field); field = ""; }
      else if (ch === "\n" || ch === "\r") {
        if (ch === "\r" && text[i + 1] === "\n") i++;
        row.push(field); field = "";
        if (row.some((v) => v !== "")) rows.push(row);
        row = [];
      } else field += ch;
    }
  }
  if (field !== "" || row.length) { row.push(field); if (row.some((v) => v !== "")) rows.push(row); }
  if (!rows.length) return [];
  const header = rows[0].map((h) => h.trim());
  return rows.slice(1).map((r) => {
    const obj = {};
    for (let j = 0; j < header.length; j++) {
      const raw = r[j] ?? "";
      const num = raw === "" ? null : Number(raw);
      obj[header[j]] = raw !== "" && !Number.isNaN(num) ? num : raw;
    }
    return obj;
  });
}

async function readRecords(file) {
  const raw = await readFile(file, "utf8");
  const ext = file.toLowerCase().split(".").pop();
  if (ext === "csv" || ext === "tsv") return parseCsv(raw);
  const parsed = JSON.parse(raw);
  if (Array.isArray(parsed)) return parsed;
  if (parsed && Array.isArray(parsed.data)) return parsed.data;
  if (parsed && Array.isArray(parsed.trials)) return parsed.trials;
  return [parsed];
}

async function loadPayload(file, key, args) {
  const ext = file.toLowerCase().split(".").pop();
  // CSV/TSV are parsed locally into a rows array — no server round-trip and
  // no dependency on the AI text-parse endpoint, which the hosted API may
  // not expose. The array is sent straight to /v1/validate as `data`.
  if (ext === "csv" || ext === "tsv") return readRecords(file);
  const raw = await readFile(file, "utf8");
  try {
    return JSON.parse(raw);
  } catch {
    // Not JSON (e.g. simulations.txt / a log dump) → convert with AI.
    stdout.write(`  ${c.dim(`Parsing ${file} with AI…`)}\n`);
    const pr = await api("/v1/parse", { method: "POST", body: { text: raw, simulation_type: args.type }, key });
    if (!pr.ok) {
      if (pr.json && pr.json.enabled === false)
        throw new Error("AI text parsing isn't enabled yet (server needs OPENROUTER_API_KEY). Use a .json file for now.");
      throw new Error(`Could not parse ${file}: ${(pr.json && pr.json.error) || pr.status}`);
    }
    return pr.json; // { simulation_type, conditions, data }
  }
}

// Load a file, POST it to /v1/validate, and return the parsed result without
// printing anything. Shared by `validate`, `watch`, and `ci` so they stay in
// lock-step. Returns { ok:true, result, simType } or { ok:false, error }.
async function validateOnce(file, key, args) {
  if (!existsSync(file)) return { ok: false, error: `File not found: ${file}` };
  const cfg = await readConfig();
  let payload;
  try {
    payload = await loadPayload(file, key, args);
  } catch (e) {
    return { ok: false, error: e.message };
  }
  const body = Array.isArray(payload)
    ? { data: payload, simulation_type: args.type || cfg.simulation_type || "aerodynamics" }
    : {
        simulation_type: args.type || payload.simulation_type || cfg.simulation_type || "aerodynamics",
        conditions: payload.conditions || {},
        data: payload.data || payload.trials || [],
      };
  if (args["no-ai"]) body.run_ai = false;

  const t0 = Date.now();
  let res;
  try {
    res = await api("/v1/validate", { method: "POST", body, key });
  } catch (e) {
    return { ok: false, error: `Request failed: ${e.message} ${c.dim(`(is ${API_BASE} reachable?)`)}` };
  }
  await trackUsage(Date.now() - t0);

  if (!res.ok) {
    const err = res.json?.error || {};
    return { ok: false, error: `[${err.code || res.status}] ${err.message || "validation error"}` };
  }
  const r = res.json;
  await writeJson(LAST_RUN_PATH, { file, t: Date.now(), result: r });
  return { ok: true, result: r, simType: body.simulation_type, body };
}

// Fetch a deterministic CI report (JUnit XML or SARIF 2.1.0) for the same
// payload and write it to disk. Used by `ci` so a pipeline can upload the
// artifact (e.g. github/codeql-action/upload-sarif). Returns a list of
// { format, path } written, or throws with a helpful message. Never blocks the
// gate: callers decide how to treat a report failure.
async function writeReports(body, key, args) {
  const wanted = [];
  if (args.sarif) wanted.push({ format: "sarif", path: args.sarif });
  if (args.junit) wanted.push({ format: "junit", path: args.junit });
  const written = [];
  for (const w of wanted) {
    const res = await api(`/v1/validate/report?format=${w.format}`, { method: "POST", body, key });
    if (!res.ok || !res.text) {
      const err = res.json?.error;
      throw new Error(
        `${w.format.toUpperCase()} report failed: ${err ? `[${err.code}] ${err.message}` : `HTTP ${res.status}`}. ` +
        `Report export requires the Python backend on the target deployment.`,
      );
    }
    await writeFile(w.path, res.text);
    written.push({ format: w.format, path: w.path });
  }
  return written;
}

async function runValidation(file, key, args) {
  const out = await validateOnce(file, key, args);
  if (!out.ok) return fail(out.error);
  const r = out.result;
  if (args.json) return stdout.write(JSON.stringify(r, null, 2) + "\n");

  renderReport(r, file, out.simType);

  if (args["fail-on"] === "warning" && r.status !== "passed") process.exitCode = 1;
  if (args["fail-on"] === "failed" && r.status === "failed") process.exitCode = 1;
}

function renderReport(r, file, simType) {
  const status = (r.status || "").toUpperCase();
  const tone = r.status === "passed" ? c.green : r.status === "warning" ? c.amber : c.red;
  const mark = r.status === "passed" ? "✓" : r.status === "warning" ? "⚠" : "✗";
  const failures = (r.issues || []).filter((i) => i.status === "failed").length;
  const warns = (r.issues || []).filter((i) => i.status === "warning").length;

  // Status banner
  const title = ` ${mark}  ${status}`;
  const right = file;
  const width = Math.max(48, title.length + right.length + 6);
  stdout.write("\n  " + c.dim("╭" + "─".repeat(width) + "╮") + "\n");
  const pad = width - title.length - right.length - 2;
  stdout.write("  " + c.dim("│") + tone(c.bold(title)) + " ".repeat(Math.max(1, pad)) + c.dim(right) + " " + c.dim("│") + "\n");
  stdout.write("  " + c.dim("╰" + "─".repeat(width) + "╯") + "\n\n");

  // Summary
  const excl = r.trials_excluded ?? 0;
  row("Simulation", simType);
  row("Trials", `${c.bold(String(r.trials_valid ?? "—"))} valid / ${r.trials_submitted ?? "—"}` + (excl ? c.dim(`   (${excl} excluded)`) : ""));
  row("Rules", `${r.unique_checks ?? r.all_checks ?? "—"} unique` + c.dim(`   ·  ${(r.all_checks ?? 0).toLocaleString()} evaluations`));
  row("Findings", `${failures ? c.red(failures + " failed") : "0 failed"}   ${warns ? c.amber(warns + " warnings") : "0 warnings"}`);
  row("Training ready", r.training_ready ? c.green("yes") : c.red("no"));
  row("Time", `${r.processing_ms ?? "—"}ms`);

  const issues = r.issues || [];
  if (issues.length) {
    stdout.write(`\n  ${c.bold(`Issues (${issues.length})`)}\n`);
    for (const i of issues.slice(0, 12)) {
      const mk = i.status === "failed" ? c.red("✗") : c.amber("⚠");
      stdout.write(`   ${mk} ${i.human_name || i.name}\n`);
      if (i.detail && i.detail !== i.human_name) stdout.write(`     ${c.dim(i.detail)}\n`);
    }
    if (issues.length > 12) stdout.write(`   ${c.dim(`… and ${issues.length - 12} more`)}\n`);
  }

  const ex = r.exclusions || [];
  if (ex.length) {
    stdout.write(`\n  ${c.bold(`Excluded trials (${excl})`)}\n`);
    for (const e of ex.slice(0, 6)) stdout.write(`   ${c.dim("#" + (e.trial_index + 1))}  ${e.reason}\n`);
    if (ex.length > 6) stdout.write(`   ${c.dim(`… and ${ex.length - 6} more`)}\n`);
  }

  const recs = r.ai?.recommendations || r.recommendations || [];
  if (recs.length) {
    stdout.write(`\n  ${c.bold("Recommendations")}\n`);
    for (const rec of recs.slice(0, 6)) stdout.write(`   ${c.cyan("→")} ${rec}\n`);
  }
  if (r.ai && r.ai.dataset_summary) {
    stdout.write(`\n  ${c.bold("AI review")}  ${c.dim(r.ai.model ? r.ai.model.split("/").pop() : "")}\n   ${c.dim(r.ai.dataset_summary)}\n`);
  }
  stdout.write("\n");
}

function renderDimensionalReport(r, file) {
  const imp = r.n_impossible ?? 0;
  const inc = r.n_inconsistent ?? 0;
  const uns = r.n_unsuitable_for_training ?? 0;
  const status = imp ? "FAIL" : inc || uns ? "WARN" : "PASS";
  const tone = imp ? c.red : (inc || uns) ? c.amber : c.green;
  const mark = imp ? "✗" : (inc || uns) ? "⚠" : "✓";

  const title = ` ${mark}  ${status}  ${c.dim("dimensional")}`;
  const right = file;
  const width = Math.max(52, title.length + right.length + 6);
  stdout.write("\n  " + c.dim("╭" + "─".repeat(width) + "╮") + "\n");
  const pad = width - title.length - right.length - 2;
  stdout.write("  " + c.dim("│") + tone(c.bold(title)) + " ".repeat(Math.max(1, pad)) + c.dim(right) + " " + c.dim("│") + "\n");
  stdout.write("  " + c.dim("╰" + "─".repeat(width) + "╯") + "\n\n");

  row("Rows", String(r.n_rows ?? "—"));
  row("Impossible", imp ? c.red(String(imp)) : "0");
  row("Inconsistent", inc ? c.amber(String(inc)) : "0");
  row("Unsuitable for training", uns ? c.amber(String(uns)) : "0");
  row("Training ready", r.training_ready ? c.green("yes") : c.red("no"));
  row("Laws discovered", String((r.laws_discovered || []).length));
  row("Anchored constants", String(r.n_anchored_constants ?? 0));

  const laws = r.laws_discovered || [];
  if (laws.length) {
    stdout.write(`\n  ${c.bold(`Laws (${laws.length})`)}\n`);
    for (const law of laws.slice(0, 8)) {
      const v = law.n_violations || 0;
      const vt = v ? c.red(`${v} violation${v === 1 ? "" : "s"}`) : c.dim("no violations");
      stdout.write(`   ${c.cyan("•")} ${c.dim("[" + law.kind + "]")} ${law.label}   ${vt}\n`);
      if (law.note) stdout.write(`     ${c.dim(law.note)}\n`);
    }
    if (laws.length > 8) stdout.write(`   ${c.dim(`… and ${laws.length - 8} more`)}\n`);
  }

  const rf = r.row_findings || [];
  if (rf.length) {
    const shown = rf.slice().sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0)).slice(0, 10);
    stdout.write(`\n  ${c.bold(`Row findings (${rf.length}), top ${shown.length}`)}\n`);
    for (const f of shown) {
      const mk = f.output_class === "impossible" ? c.red("✗") : c.amber("⚠");
      stdout.write(`   ${mk} row ${String(f.row_index).padStart(5)} ${c.dim("[" + f.output_class + "]")} ${f.reason}\n`);
      if (f.counterfactual_repair) stdout.write(`     ${c.cyan("fix:")} ${c.dim(f.counterfactual_repair)}\n`);
    }
    if (rf.length > shown.length) stdout.write(`   ${c.dim(`… and ${rf.length - shown.length} more`)}\n`);
  }

  const ca = r.condition_assertions || [];
  if (ca.length) {
    stdout.write(`\n  ${c.bold("Declared-condition assertions")}\n`);
    for (const a of ca) stdout.write(`   ${c.cyan("•")} ${a.label}: declared=${a.declared}, implied=${a.implied}, rel_dev=${a.rel_dev}\n`);
  }
  const uc = r.units_conflicts || [];
  if (uc.length) {
    stdout.write(`\n  ${c.bold("Units conflicts")}\n`);
    for (const u of uc) stdout.write(`   ${c.amber("⚠")} ${u.column}: ${c.dim(u.note)}\n`);
  }
  const sup = r.suppressions || [];
  if (sup.length) {
    stdout.write(`\n  ${c.bold("Suppressions")} ${c.dim("(checks not run, with reason)")}\n`);
    for (const s of sup) stdout.write(`   ${c.dim("• " + s)}\n`);
  }
  stdout.write("\n");
}

// ── Help ──────────────────────────────────────────────────────────────────────
const HELP = {
  init: { usage: "simapi init", desc: "Create a simapi.json config in the current project." },
  validate: { usage: "simapi validate <file>", desc: "Validate a .json, .csv/.tsv, or .txt simulation file and print the report. CSV/TSV are parsed locally; plain-text/log files are converted to JSON with AI.", opts: [["--type <domain>", "simulation domain"], ["--json", "raw JSON output"], ["--no-ai", "skip the AI second pass"], ["--fail-on <level>", "exit non-zero on warning|failed"]], ex: ["simapi validate simulation.json", "simapi validate simulation.csv --type aerodynamics", "simapi validate run.json --fail-on warning"] },
  ci: { usage: "simapi ci [file]", desc: "CI gate: validate a file and exit non-zero when the gate fails. Reads the file from simapi.json \"files\" when omitted. Strict by default (any non-passing status blocks).", opts: [["--json", "machine-readable verdict (ok, gate, status, counts)"], ["--fail-on <level>", "warning (default) blocks warnings+failures; failed blocks only failures"], ["--type <domain>", "simulation domain"], ["--sarif <path>", "also write a SARIF 2.1.0 report (upload to code scanning)"], ["--junit <path>", "also write a JUnit XML report"], ["--no-ai", "skip the AI second pass"]], ex: ["simapi ci simulation.json", "simapi ci run.csv --fail-on failed", "simapi ci run.json --sarif simapi.sarif", "simapi ci --json"] },
  dimensional: { usage: "simapi dimensional <file.csv|file.json>", desc: "Run the dimensional-analysis engine (Buckingham-π groups, anchored physical constants, bimodal-split detection, temporal drift, semantic bounds). Prints laws discovered and row-level findings.", opts: [["--conditions k=v,k=v", "declared conditions (e.g. altitude_m=11000,velocity=45)"], ["--json", "raw JSON output"], ["--fail-on <level>", "exit non-zero on warning|failed (default: exit 1 on any impossible row)"]], ex: ["simapi dimensional simulation.csv", "simapi dimensional run.csv --conditions altitude_m=11000", "simapi dimensional data.json --json > report.json"] },
  domains: { usage: "simapi domains", desc: "List the supported simulation types." },
  doctor: { usage: "simapi doctor [--fix]", desc: "Diagnose config, connectivity, and project setup." },
  explain: { usage: "simapi explain", desc: "Explain the issues from the most recent validation run in detail." },
  repair: { usage: "simapi repair <file> [--apply]", desc: "Preview or apply automatic structural repairs to a data file.", ex: ["simapi repair simulation.json", "simapi repair simulation.json --apply"] },
  login: { usage: "simapi login", desc: "Open the browser setup page to generate and save an API key (optional — the API is open by default)." },
  open: { usage: "simapi open", desc: "Open the SimAPI dashboard in your browser." },
  watch: { usage: "simapi watch <file>", desc: "Re-run validation automatically whenever the file changes.", ex: ["simapi watch simulation.json"] },
  usage: { usage: "simapi usage", desc: "Show requests today/this month, remaining quota, and average time." },
  "api-key": { usage: "simapi api-key <show|generate|set|delete>", desc: "The hosted API needs no key. Only relevant for your own deployment.", ex: ["simapi api-key generate", "simapi api-key set <key>", "simapi api-key show"] },
  config: { usage: "simapi config [set <key> <value>]", desc: "Show or update CLI configuration.", ex: ["simapi config", "simapi config set fail_on warning"] },
  version: { usage: "simapi version", desc: "Print the installed CLI version." },
  help: { usage: "simapi help", desc: "Show all commands." },
};

function printHelp() {
  banner();
  stdout.write(`  ${c.bold("Usage")}\n    simapi ${c.dim("<command> [options]")}\n\n`);
  stdout.write(`  ${c.bold("Commands")}\n`);
  const items = [
    ["init", "Create a simapi.json config"],
    ["validate <file>", "Validate a .json/.csv/.txt simulation file"],
    ["ci [file]", "CI gate — non-zero exit when validation fails"],
    ["dimensional <file>", "Run the dimensional-analysis engine on a CSV/JSON"],
    ["watch <file>", "Re-validate on file change"],
    ["domains", "List supported simulation types"],
    ["usage", "Show API usage statistics"],
    ["api-key <cmd>", "show · generate · set · delete (optional -- no account needed)"],
    ["config [set]", "Show or update configuration"],
    ["doctor [--fix]", "Diagnose config and connectivity"],
    ["explain", "Explain the last validation run in detail"],
    ["repair <file> [--apply]", "Preview or apply automatic repairs"],
    ["open", "Open the dashboard in your browser"],
    ["version", "Show the CLI version"],
    ["help", "Show this help"],
  ];
  for (const [name, desc] of items) stdout.write(`    ${c.cyan(name.padEnd(18))} ${c.dim(desc)}\n`);
  stdout.write(`\n  ${c.dim("Run")} ${c.cyan("simapi <command> --help")} ${c.dim("for details on a command.")}\n\n`);
}

function printCommandHelp(name) {
  const h = HELP[name];
  if (!h) return printHelp();
  stdout.write(`\n  ${c.bold(name)} — ${h.desc}\n\n`);
  stdout.write(`  ${c.bold("Usage")}\n    ${c.cyan(h.usage)}\n`);
  if (h.opts) {
    stdout.write(`\n  ${c.bold("Options")}\n`);
    for (const [o, d] of h.opts) stdout.write(`    ${c.cyan(o.padEnd(20))} ${c.dim(d)}\n`);
  }
  if (h.ex) {
    stdout.write(`\n  ${c.bold("Examples")}\n`);
    for (const e of h.ex) stdout.write(`    ${c.dim("$")} ${e}\n`);
  }
  stdout.write("\n");
}

// ── Output helpers ──────────────────────────────────────────────────────────────
function row(label, value) {
  stdout.write(`  ${label.padEnd(22)} ${value}\n`);
}
function ok(msg) {
  stdout.write(`  ${c.green("✓")} ${msg}\n`);
}
function info(msg) {
  stdout.write(`  ${msg}\n`);
}
function fail(msg) {
  stdout.write(`  ${c.red("✗")} ${msg}\n`);
  process.exitCode = 1;
}
// Strip ANSI color codes so error strings are clean inside --json output.
function stripAnsi(s) {
  return String(s).replace(/\x1b\[[0-9;]*m/g, "");
}

// ── Arg parsing ─────────────────────────────────────────────────────────────────
function parse(argv) {
  const out = { _: [], type: undefined, json: false, "fail-on": undefined, help: false, fix: false, apply: false, conditions: undefined, sarif: undefined, junit: undefined };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") out.help = true;
    else if (a === "--json") out.json = true;
    else if (a === "--fix") out.fix = true;
    else if (a === "--apply") out.apply = true;
    else if (a === "--type") out.type = argv[++i];
    else if (a === "--fail-on") out["fail-on"] = argv[++i];
    // CI artifacts: write a JUnit XML or SARIF 2.1.0 report the pipeline can
    // upload (e.g. to GitHub code scanning). Both take a destination path.
    else if (a === "--sarif") out.sarif = argv[++i];
    else if (a === "--junit") out.junit = argv[++i];
    // Was missing: `--conditions` used by `simapi dimensional`. The
    // command site referenced args.conditions but the parser dropped
    // the token into args._ as a positional, so `--conditions altitude_m=11000`
    // was silently ignored and dimensional ran with empty conditions.
    else if (a === "--conditions") out.conditions = argv[++i];
    else out._.push(a);
  }
  return out;
}

async function main() {
  const [, , cmd, ...rest] = process.argv;
  const args = parse(rest);

  if (!cmd || cmd === "--help" || cmd === "-h") return printHelp();
  if (cmd === "--version" || cmd === "-v") return commands.version();
  const name = cmd === "apikey" ? "api-key" : cmd;
  if (!(name in commands)) {
    fail(`Unknown command: ${cmd}`);
    return printHelp();
  }
  if (args.help) return printCommandHelp(name);
  await commands[name](args);
}

main().catch((e) => fail(e.message));
