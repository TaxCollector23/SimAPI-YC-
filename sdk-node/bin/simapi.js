#!/usr/bin/env node
/**
 * SimAPI CLI.
 *
 * Zero runtime dependencies (Node 18+ built-ins only). Professional startup
 * banner, browser-based login, and a full command surface:
 *   login · logout · whoami · init · validate · watch · usage ·
 *   api-key {show,rotate,delete} · config [set] · version · help
 */
import { readFile, writeFile, mkdir, stat } from "node:fs/promises";
import { watch as fsWatch, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline/promises";
import { stdin, stdout, platform, env } from "node:process";
import { exec } from "node:child_process";

const VERSION = "1.0.0";
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
  if (!existsSync(CONFIG_DIR)) await mkdir(CONFIG_DIR, { recursive: true });
  await writeFile(path, JSON.stringify(obj, null, 2));
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
  const json = text ? JSON.parse(text) : {};
  return { ok: res.ok, status: res.status, json };
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
  async login() {
    banner();
    const url = `${WEB_BASE}/auth?cli=true`;
    stdout.write(`  Opening your browser to sign in…\n  ${c.cyan(url)}\n\n`);
    openBrowser(url);
    stdout.write(c.dim("  Sign in, copy your API key, then paste it below.\n\n"));
    const key = await prompt("  Paste your SimAPI API key: ");
    if (!key) return fail("No key entered.");
    stdout.write("\n  Verifying…\n");
    const { ok, json } = await api("/auth/verify", { method: "POST", body: { api_key: key } });
    if (!ok) return fail(`Verification failed: ${json?.error || "invalid key"}`);
    const cfg = await readConfig();
    await writeConfig({ ...cfg, apiKey: key, plan: json.plan || "developer", email: json.email || null, verifiedAt: Date.now() });
    stdout.write(`\n  ${c.green("✓")} Authentication successful.\n  ${c.green("✓")} API key saved securely. ${c.dim(`(${CONFIG_PATH})`)}\n\n`);
    stdout.write(`  You can now run: ${c.cyan("simapi validate simulation.json")}\n\n`);
  },

  async logout() {
    const cfg = await readConfig();
    delete cfg.apiKey;
    delete cfg.plan;
    delete cfg.email;
    await writeConfig(cfg);
    ok("Logged out. Local credentials removed.");
  },

  async whoami() {
    const cfg = await readConfig();
    const key = env.SIMAPI_API_KEY || cfg.apiKey;
    if (!key) return info(`Not logged in. Run ${c.cyan("simapi login")}.`);
    stdout.write(`\n  ${c.bold("Account")}   ${cfg.email || c.dim("(browser session)")}\n`);
    stdout.write(`  ${c.bold("Plan")}      ${cfg.plan || "developer"}\n`);
    stdout.write(`  ${c.bold("API key")}   ${c.cyan(mask(key))}\n\n`);
  },

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
    if (!key) return fail(`Not logged in. Run ${c.cyan("simapi login")} or set SIMAPI_API_KEY.`);
    await runValidation(file, key, args);
  },

  async watch(args) {
    const file = args._[0];
    if (!file) return fail(`Usage: ${c.cyan("simapi watch <file>")}`);
    const key = await resolveKey();
    if (!key) return fail(`Not logged in. Run ${c.cyan("simapi login")} first.`);
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
      if (!key) return info("No API key configured. Run simapi login.");
      return info(`Active key: ${c.cyan(mask(key))}`);
    }
    if (sub === "rotate") {
      if (!key) return fail("Nothing to rotate — run simapi login first.");
      const { ok: good, json } = await api("/auth/rotate", { method: "POST", body: { api_key: key } });
      if (!good) return fail(`Rotate failed: ${json?.error || "server error"}`);
      const cfg = await readConfig();
      await writeConfig({ ...cfg, apiKey: json.api_key });
      return ok(`New key issued: ${c.cyan(mask(json.api_key))} ${c.dim("(previous key invalidated)")}`);
    }
    if (sub === "delete") {
      const cfg = await readConfig();
      delete cfg.apiKey;
      await writeConfig(cfg);
      return ok("API key deleted from this machine.");
    }
    return fail(`Usage: ${c.cyan("simapi api-key <show|rotate|delete>")}`);
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
    if (keys.length === 0) stdout.write(c.dim("  (empty — run simapi login)\n"));
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
    else {
      stdout.write(`  ${c.amber("⚠")} No API key configured\n    ${c.dim("fix: simapi login")}\n`);
      problems++;
    }

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

  version() {
    banner();
    stdout.write(`  ${c.bold(`v${VERSION}`)}  ${c.dim(`node ${process.version}`)}\n\n`);
  },

  help() {
    printHelp();
  },
};

async function loadPayload(file, key, args) {
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

async function runValidation(file, key, args) {
  if (!existsSync(file)) return fail(`File not found: ${file}`);
  const cfg = await readConfig();
  let payload;
  try {
    payload = await loadPayload(file, key, args);
  } catch (e) {
    return fail(e.message);
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
    return fail(`Request failed: ${e.message} ${c.dim(`(is ${API_BASE} reachable?)`)}`);
  }
  await trackUsage(Date.now() - t0);

  if (!res.ok) {
    const err = res.json?.error || {};
    return fail(`[${err.code || res.status}] ${err.message || "validation error"}`);
  }
  const r = res.json;
  await writeJson(LAST_RUN_PATH, { file, t: Date.now(), result: r });
  if (args.json) return stdout.write(JSON.stringify(r, null, 2) + "\n");

  renderReport(r, file, body.simulation_type);

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

// ── Help ──────────────────────────────────────────────────────────────────────
const HELP = {
  login: { usage: "simapi login", desc: "Authenticate via the browser and save your API key.", ex: ["simapi login"] },
  logout: { usage: "simapi logout", desc: "Remove locally stored credentials." },
  whoami: { usage: "simapi whoami", desc: "Show the authenticated account, plan, and masked API key." },
  init: { usage: "simapi init", desc: "Create a simapi.json config in the current project." },
  validate: { usage: "simapi validate <file>", desc: "Validate a .json or .txt simulation file and print the report. Plain-text/log files are converted to JSON with AI.", opts: [["--type <domain>", "simulation domain"], ["--json", "raw JSON output"], ["--no-ai", "skip the AI second pass"], ["--fail-on <level>", "exit non-zero on warning|failed"]], ex: ["simapi validate simulation.json", "simapi validate simulations.txt --type aerodynamics", "simapi validate run.json --fail-on warning"] },
  domains: { usage: "simapi domains", desc: "List the supported simulation types." },
  doctor: { usage: "simapi doctor [--fix]", desc: "Diagnose config, credentials, connectivity, and project setup." },
  explain: { usage: "simapi explain", desc: "Explain the issues from the most recent validation run in detail." },
  repair: { usage: "simapi repair <file> [--apply]", desc: "Preview or apply automatic structural repairs to a data file.", ex: ["simapi repair simulation.json", "simapi repair simulation.json --apply"] },
  open: { usage: "simapi open", desc: "Open the SimAPI dashboard in your browser." },
  watch: { usage: "simapi watch <file>", desc: "Re-run validation automatically whenever the file changes.", ex: ["simapi watch simulation.json"] },
  usage: { usage: "simapi usage", desc: "Show requests today/this month, remaining quota, and average time." },
  "api-key": { usage: "simapi api-key <show|rotate|delete>", desc: "Manage your API key.", ex: ["simapi api-key show", "simapi api-key rotate", "simapi api-key delete"] },
  config: { usage: "simapi config [set <key> <value>]", desc: "Show or update CLI configuration.", ex: ["simapi config", "simapi config set fail_on warning"] },
  version: { usage: "simapi version", desc: "Print the installed CLI version." },
  help: { usage: "simapi help", desc: "Show all commands." },
};

function printHelp() {
  banner();
  stdout.write(`  ${c.bold("Usage")}\n    simapi ${c.dim("<command> [options]")}\n\n`);
  stdout.write(`  ${c.bold("Commands")}\n`);
  const items = [
    ["login", "Authenticate and save your API key"],
    ["logout", "Remove stored credentials"],
    ["whoami", "Show account, plan, and masked key"],
    ["init", "Create a simapi.json config"],
    ["validate <file>", "Validate a .json or .txt simulation file"],
    ["watch <file>", "Re-validate on file change"],
    ["domains", "List supported simulation types"],
    ["usage", "Show API usage statistics"],
    ["api-key <cmd>", "show · rotate · delete"],
    ["config [set]", "Show or update configuration"],
    ["doctor [--fix]", "Diagnose config, auth, and connectivity"],
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

// ── Arg parsing ─────────────────────────────────────────────────────────────────
function parse(argv) {
  const out = { _: [], type: undefined, json: false, "fail-on": undefined, help: false, fix: false, apply: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") out.help = true;
    else if (a === "--json") out.json = true;
    else if (a === "--fix") out.fix = true;
    else if (a === "--apply") out.apply = true;
    else if (a === "--type") out.type = argv[++i];
    else if (a === "--fail-on") out["fail-on"] = argv[++i];
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
