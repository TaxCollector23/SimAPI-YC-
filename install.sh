#!/bin/sh
# SimAPI CLI installer (macOS / Linux)
#   curl -fsSL https://sim-api.vercel.app/install.sh | sh
#
# This is a thin wrapper around npm — the canonical install is:
#   npm install -g simapi-cli
set -e

PKG="simapi-cli"

red()   { printf '\033[31m%s\033[0m' "$1"; }
green() { printf '\033[32m%s\033[0m' "$1"; }
cyan()  { printf '\033[36m%s\033[0m' "$1"; }

printf '\n  Installing the SimAPI CLI…\n\n'

# ── Require Node.js 18+ ─────────────────────────────────────────────────────
if ! command -v node >/dev/null 2>&1; then
  printf '  %s Node.js 18+ is required but was not found.\n' "$(red '✗')"
  printf '    Install it, then re-run this installer:\n'
  printf '      macOS:  brew install node\n'
  printf '      Linux:  use your package manager, or https://nodejs.org\n\n'
  exit 1
fi

NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)
if [ "$NODE_MAJOR" -lt 18 ]; then
  printf '  %s Node 18+ is required (found %s).\n' "$(red '✗')" "$(node -v)"
  printf '    Upgrade Node from https://nodejs.org and re-run this installer.\n\n'
  exit 1
fi

# ── Require npm ─────────────────────────────────────────────────────────────
if ! command -v npm >/dev/null 2>&1; then
  printf '  %s npm was not found (it normally ships with Node.js).\n' "$(red '✗')"
  printf '    Reinstall Node.js from https://nodejs.org, then re-run this installer.\n\n'
  exit 1
fi

# ── Install via npm ─────────────────────────────────────────────────────────
printf '  Running: %s\n\n' "$(cyan "npm install -g $PKG")"
if npm install -g "$PKG"; then
  :
else
  printf '\n  %s Global install failed — this is usually a permissions issue.\n' "$(red '✗')"
  printf '    Try one of:\n'
  printf '      • A Node version manager (nvm, fnm, volta) so npm -g needs no root\n'
  printf '      • %s\n' "$(cyan "sudo npm install -g $PKG")"
  printf '      • Run it on demand without installing: %s\n\n' "$(cyan "npx $PKG <command>")"
  exit 1
fi

printf '\n  %s Installed the %s command.\n\n' "$(green '✓')" "$(cyan simapi)"
printf '  Get started:\n'
printf '    %s   %s\n' "$(cyan 'simapi doctor')" "check connectivity"
printf '    %s   %s\n\n' "$(cyan 'simapi validate simulation.json')" "validate a file"
