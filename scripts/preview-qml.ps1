#Requires -Version 5.1
<#
.SYNOPSIS
    Live preview of a single QML screen — no engine boot, no DI container.

.DESCRIPTION
    Thin wrapper around preview_qml.py. Activates the same venv
    ci-local.ps1 uses (repo-root .venv, falling back to Binace_Bot/.venv on
    Linux) and forwards the screen name.

.PARAMETER Screen
    One of: sidebar, settings, database, devboard

.EXAMPLE
    .\scripts\preview-qml.ps1 devboard
    .\scripts\preview-qml.ps1 database
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("sidebar", "settings", "database", "devboard")]
    [string]$Screen
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$botRoot   = Split-Path -Parent $scriptDir
$repoRoot  = Split-Path -Parent $botRoot

$env:PYTHONPATH = $repoRoot

$venvActivateWin = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
$venvActivateLin = Join-Path $botRoot ".venv/bin/activate"

if (Test-Path $venvActivateWin) {
    & $venvActivateWin
} elseif (Test-Path $venvActivateLin) {
    $env:PATH = "$(Join-Path $botRoot '.venv/bin'):$env:PATH"
} else {
    Write-Warning "Virtual environment not found. Using system Python."
}

python (Join-Path $scriptDir "preview_qml.py") $Screen
