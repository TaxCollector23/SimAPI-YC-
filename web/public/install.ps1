# SimAPI CLI installer (Windows PowerShell)
#   irm https://sim-api.vercel.app/install.ps1 | iex
$ErrorActionPreference = "Stop"

$repo = "https://raw.githubusercontent.com/TaxCollector23/SimAPI-YC-/main"
$dest = "$env:USERPROFILE\.simapi\bin"

Write-Host "`n  Installing the SimAPI CLI..."

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "  x Node.js 18+ is required but was not found." -ForegroundColor Red
  Write-Host "    Install it from https://nodejs.org and re-run this installer.`n"
  exit 1
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null
Invoke-WebRequest -UseBasicParsing "$repo/sdk-node/bin/simapi.js" -OutFile "$dest\simapi.js"

# Shim so `simapi` resolves on PATH.
$cmd = "@echo off`r`nnode `"$dest\simapi.js`" %*"
Set-Content -Path "$dest\simapi.cmd" -Value $cmd -Encoding ASCII

# Add to the user's PATH if not already present.
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$dest*") {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$dest", "User")
  $env:Path = "$env:Path;$dest"   # current session too
  Write-Host "  + Added $dest to your PATH" -ForegroundColor Green
}

Write-Host "  + Installed to $dest\simapi.cmd" -ForegroundColor Green
Write-Host "`n  Open a NEW terminal, then run:  simapi login`n"
