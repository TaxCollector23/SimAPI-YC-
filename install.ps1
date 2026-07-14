# SimAPI CLI installer (Windows PowerShell)
#   irm https://raw.githubusercontent.com/TaxCollector23/SimAPI-YC-/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$repo = "https://raw.githubusercontent.com/TaxCollector23/SimAPI-YC-/main"
$dest = "$env:USERPROFILE\.simapi"

Write-Host "`n  Installing the SimAPI CLI..."

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "  x Node.js 18+ is required. Install it from https://nodejs.org and re-run.`n"
  exit 1
}

New-Item -ItemType Directory -Force -Path "$dest\bin" | Out-Null
Invoke-WebRequest -UseBasicParsing "$repo/sdk-node/bin/simapi.js" -OutFile "$dest\bin\simapi.js"

# Shim so `simapi` resolves on PATH.
$cmd = "@echo off`r`nnode `"$dest\bin\simapi.js`" %*"
Set-Content -Path "$dest\bin\simapi.cmd" -Value $cmd -Encoding ASCII

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$dest\bin*") {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$dest\bin", "User")
  Write-Host "  -> Added $dest\bin to your PATH."
}

Write-Host "  + Installed to $dest\bin\simapi.cmd"
Write-Host "`n  Open a new terminal, then run:  simapi login`n"
