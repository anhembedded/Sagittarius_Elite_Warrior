#Requires -Version 5.1
<#
.SYNOPSIS
    Live preview of one QML widget component, addressed by directory.

.DESCRIPTION
    Thin wrapper around preview_qml.py's `--dir` mode (same script `preview-qml.ps1`
    already wraps) — loads `<dir>/preview.py`'s `build_preview()` directly by path,
    instead of by a name already registered in the auto-discovered list. Useful for a
    widget under `src/presentation/ui/qml/<Widget>/` that is still being built, or to
    point at an exact directory without relying on `discover_previews()`'s
    basename-keyed registry.

    `.\scripts\preview-qml.ps1 <name>` already works for anything `discover_previews()`
    finds (any `preview.py` under `src/presentation/ui/`, including
    `src/presentation/ui/qml/<Widget>/`) — this script is for addressing one
    explicitly by path instead.

.PARAMETER Dir
    Path to the directory containing the `preview.py` to load (e.g.
    `src/presentation/ui/qml/Capital`). Aliased to `-dir` for exact-name matching.

.EXAMPLE
    .\scripts\uml_preview.ps1 -dir src/presentation/ui/qml/Capital
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [Alias("dir")]
    [string]$Dir,

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

& $pythonExe (Join-Path $scriptDir "preview_qml.py") --dir $Dir @ScriptArgs
