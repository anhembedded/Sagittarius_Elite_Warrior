#Requires -Version 5.1
<#
.SYNOPSIS
    Live preview of a single QML screen or component — no engine boot, no DI container.

.DESCRIPTION
    Thin wrapper around preview_qml.py (BOT-031). Activates the local virtual environment
    and forwards arguments to Python with auto-discovery support.

.EXAMPLE
    .\scripts\preview-qml.ps1 --list
    .\scripts\preview-qml.ps1 backtest
    .\scripts\preview-qml.ps1 dashboard
    .\scripts\preview-qml.ps1 data_management
    .\scripts\preview-qml.ps1 settings
    .\scripts\preview-qml.ps1 sidebar
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$botRoot   = Split-Path -Parent $scriptDir
$repoRoot  = Split-Path -Parent $botRoot

# The repo directory's own name matches the Python package name
# (Sagittarius_Elite_Warrior), so $repoRoot alone resolves
# `import Sagittarius_Elite_Warrior` -- no .venv_alias symlink needed.
$env:PYTHONPATH = "$repoRoot;$botRoot"

$venvRoot = $null
if (Test-Path (Join-Path $botRoot ".venv")) {
    $venvRoot = Join-Path $botRoot ".venv"
} elseif (Test-Path (Join-Path $repoRoot ".venv")) {
    $venvRoot = Join-Path $repoRoot ".venv"
}

$pythonExe = if ($venvRoot) { Join-Path $venvRoot "Scripts\python.exe" } else { "python" }

& $pythonExe (Join-Path $scriptDir "preview_qml.py") @ScriptArgs
