#!/usr/bin/env node
/**
 * SimAPI CLI.
 *
 * Commands: login, logout, whoami, validate, init, version, help.
 * Config is stored at ~/.simapi/config.json; SIMAPI_API_KEY overrides it.
 * Requires Node 18+ (global fetch).
 */
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";

const CONFIG_DIR = join(homedir(), ".simapi");
const CONFIG_PATH = join(CONFIG_DIR, "config.json");
const DEFAULT_BASE = process.env.SIMAPI_BASE_URL || "https://sim-api.vercel.app/api";
const VERSION = "3.1.0";

const c = {
  dim: (s) => `\x1b[2m${s}\x1b[0m`,
  bold: (s) => `\x1b[1m${s}\x1b[0m`,
  green: (s) => `\x1b[32m${s}\x1b[0m`,
  red: (s) => `\x1b[31m${s}\x1b[0m`,
  yellow: (s) => `\x1b[33m${s}\x1b[0m`,
  cyan: (s) => `\x1b[36m${s}\x1b[0m`,
};

async function readConfig() {
  try {
    return JSON.parse(await readFile(CONFIG_PATH, "utf8"));
  } catch {
    return {};
  }
}
async function writeConfig(cfg) {
  if (!existsSync(CONFIG_DIR)) await mkdir(CONFIG_DIR, { recursive: true });
  await writeFile(CONFIG_PATH, JSON.stringify(cfg, null, 2));
}
async function resolveKey() {
  if (process.env.SIMAPI_API_KEY) return process.env.SIMAPI_API_KEY;
  return (await readConfig()).apiKey;
}

async function cmdLogin() {
  const rl = createInterface({ input: stdin, output: stdout });
  const key = (await rl.question("Paste your API key: ")).trim();
  rl.close();
  if (!key.startsWith("sk_")) {
    console.error(c.red("That doesn't look like a SimAPI key (expected sk_...)."));
    process.exit(1);
  }
  const cfg = await readConfig();
  cfg.apiKey = key;
  cfg.baseUrl = cfg.baseUrl || DEFAULT_BASE;
  await writeConfig(cfg);
  console.log(c.green("Saved.") + c.dim(` (${CONFIG_PATH})`));
}

async function cmdLogout() {
  const cfg = await readConfig();
  delete cfg.apiKey;
  await writeConfig(cfg);
  console.log(c.green("Logged out."));
}

async function cmdWhoami() {
  const key = await resolveKey();
  if (!key) {
    console.log(c.yellow("Not logged in.") + " Run " + c.cyan("simapi login") + ".");
    return;
  }
  console.log(`Authenticated with key ${c.bold(key.slice(0, 14) + "…")}`);
}

async function cmdInit() {
  const sample = {
    simulation_type: "aerodynamics",
    conditions: { velocity: 15.0, altitude: 120.0 },
    data: [
      { cd: 0.312, cl: 0.847, re: 415000, ma: 0.044 },
      { cd: 0.315, cl: 0.851, re: 418000, ma: 0.044 },
    ],
  };
  await writeFile("simulation.json", JSON.stringify(sample, null, 2));
  console.log(c.green("Created simulation.json") + c.dim(" — edit it, then run: simapi validate simulation.json"));
}

async function cmdValidate(file, flags) {
  if (!file) {
    console.error(c.red("Usage: simapi validate <file.json>"));
    process.exit(1);
  }
  const key = await resolveKey();
  if (!key) {
    console.error(c.red("Not logged in.") + " Run " + c.cyan("simapi login") + " or set SIMAPI_API_KEY.");
    process.exit(1);
  }
  const cfg = await readConfig();
  const baseUrl = (cfg.baseUrl || DEFAULT_BASE).replace(/\/$/, "");

  let payload;
  try {
    payload = JSON.parse(await readFile(file, "utf8"));
  } catch (e) {
    console.error(c.red(`Could not read ${file}: ${e.message}`));
    process.exit(1);
  }
  const body = Array.isArray(payload)
    ? { data: payload, simulation_type: flags.type || "aerodynamics" }
    : { simulation_type: flags.type || payload.simulation_type || "aerodynamics", conditions: payload.conditions || {}, data: payload.data || payload.trials || [] };
  if (flags.noAi) body.run_ai = false;

  let res, json;
  try {
    res = await fetch(`${baseUrl}/v1/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": key },
      body: JSON.stringify(body),
    });
    json = await res.json();
  } catch (e) {
    console.error(c.red(`Request failed: ${e.message}`));
    console.error(c.dim(`Is the API reachable at ${baseUrl}?`));
    process.exit(2);
  }

  if (!res.ok) {
    const err = json.error || {};
    console.error(c.red(`Error [${err.code || res.status}]: ${err.message || res.statusText}`));
    process.exit(2);
  }

  if (flags.json) {
    console.log(JSON.stringify(json, null, 2));
  } else {
    const color = json.status === "passed" ? c.green : json.status === "warning" ? c.yellow : c.red;
    console.log("");
    console.log(`  Status:     ${color(json.status.toUpperCase())}`);
    console.log(`  Confidence: ${json.confidence}`);
    console.log(`  Trials:     ${json.trials_valid}/${json.trials_submitted} valid`);
    console.log(`  Checks:     ${json.all_checks} (${json.failed} failed, ${json.warnings} warnings)`);
    console.log(`  Time:       ${json.processing_ms}ms`);
    if (json.issues?.length) {
      console.log(c.dim("\n  Issues:"));
      for (const i of json.issues.slice(0, 8)) console.log(`   - ${i.name}: ${i.detail}`);
    }
    console.log("");
  }

  // Exit code gate for CI.
  const failOn = flags.failOn;
  if (failOn === "warning" && json.status !== "passed") process.exit(1);
  if (failOn === "failed" && json.status === "failed") process.exit(1);
}

function cmdHelp() {
  console.log(`
${c.bold("simapi")} ${c.dim(`v${VERSION}`)} — validate simulation results

${c.bold("Usage")}
  simapi <command> [options]

${c.bold("Commands")}
  login                 Save an API key (${c.dim("prompts for the key")})
  logout                Remove the saved API key
  whoami                Show the authenticated key
  init                  Write a sample simulation.json
  validate <file>       Validate a simulation JSON file
  version               Print the CLI version
  help                  Show this help

${c.bold("Validate options")}
  --type <domain>       Simulation type (default: aerodynamics)
  --json                Print the raw JSON response
  --no-ai               Skip the async AI layer
  --fail-on <level>     Exit non-zero on 'warning' or 'failed' (for CI)

${c.bold("Environment")}
  SIMAPI_API_KEY        Overrides the saved key
  SIMAPI_BASE_URL       API base URL (default: https://api.simapi.dev)
`);
}

function parseFlags(args) {
  const flags = {};
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--json") flags.json = true;
    else if (a === "--no-ai") flags.noAi = true;
    else if (a === "--type") flags.type = args[++i];
    else if (a === "--fail-on") flags.failOn = args[++i];
    else positional.push(a);
  }
  return { flags, positional };
}

async function main() {
  const [, , command, ...rest] = process.argv;
  const { flags, positional } = parseFlags(rest);
  switch (command) {
    case "login": return cmdLogin();
    case "logout": return cmdLogout();
    case "whoami": return cmdWhoami();
    case "init": return cmdInit();
    case "validate": return cmdValidate(positional[0], flags);
    case "version":
    case "--version":
    case "-v": return console.log(VERSION);
    case "help":
    case "--help":
    case "-h":
    case undefined: return cmdHelp();
    default:
      console.error(c.red(`Unknown command: ${command}`));
      cmdHelp();
      process.exit(1);
  }
}

main().catch((e) => {
  console.error(c.red(e.message));
  process.exit(1);
});
