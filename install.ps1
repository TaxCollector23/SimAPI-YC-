# SimAPI CLI installer (Windows PowerShell)
#   irm https://sim-api.vercel.app/install.ps1 | iex
#
# This is a thin wrapper around npm — the canonical install is:
#   npm install -g simapi-cli
$ErrorActionPreference = "Stop"

$pkg = "simapi-cli"

Write-Host ""
Write-Host "  Installing the SimAPI CLI..."
Write-Host ""

# --- Require Node.js 18+ ---------------------------------------------------
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
  Write-Host "  x Node.js 18+ is required but was not found." -ForegroundColor Red
  Write-Host "    Install it, then re-run this installer:"
  Write-Host "      winget install OpenJS.NodeJS   (or download from https://nodejs.org)"
  Write-Host ""
  exit 1
}

$nodeMajor = 0
try { $nodeMajor = [int](& node -p "process.versions.node.split('.')[0]") } catch { $nodeMajor = 0 }
if ($nodeMajor -lt 18) {
  $ver = (& node -v)
  Write-Host "  x Node 18+ is required (found $ver)." -ForegroundColor Red
  Write-Host "    Upgrade Node from https://nodejs.org and re-run this installer."
  Write-Host ""
  exit 1
}

# --- Require npm -----------------------------------------------------------
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
  Write-Host "  x npm was not found (it normally ships with Node.js)." -ForegroundColor Red
  Write-Host "    Reinstall Node.js from https://nodejs.org, then re-run this installer."
  Write-Host ""
  exit 1
}

# --- Install via npm -------------------------------------------------------
Write-Host "  Running: npm install -g $pkg" -ForegroundColor Cyan
Write-Host ""
& npm install -g $pkg
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "  x Global install failed." -ForegroundColor Red
  Write-Host "    Try running the command in an elevated terminal, or run it on demand:"
  Write-Host "      npx $pkg <command>" -ForegroundColor Cyan
  Write-Host ""
  exit 1
}

Write-Host ""
Write-Host "  + Installed the 'simapi' command." -ForegroundColor Green
Write-Host ""
Write-Host "  Open a NEW terminal (so PATH refreshes), then run:"
Write-Host "    simapi doctor" -ForegroundColor Cyan
Write-Host "    simapi validate simulation.json" -ForegroundColor Cyan
Write-Host ""
