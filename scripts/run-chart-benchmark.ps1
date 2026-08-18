#Requires -Version 5.1
<#
.SYNOPSIS
    One-command chart benchmark — wraps chart_migration_benchmark for BOT-098F5.

.DESCRIPTION
    Runs the same standard-profile workload (6,420 candles + 5 indicators +
    1,112 markers, 1,600x900, warmup 20 + measured 120) through both renderers.
    CI contract is portable: offscreen, median/p95/updates naming, crosshair
    truth preserved and Qt warning-free. Desktop contract additionally asserts
    actual pixel color evidence visible under a Windows RHI backend.

    This is the ergonomic front-end for local usage:
      - ci-local.ps1 -Full already runs --ci-contract behind the scenes.
      - run-chart-benchmark.ps1 is for ad-hoc execution that also writes a
        benchmark results artifact to a timestamped or user-supplied output path.

.PARAMETER Backend
    Which renderer(s) to measure: python, native, or both (default).

.PARAMETER Desktop
    Also validate real pixel color data after measurement. Use on a normal
    Windows desktop session with a real frame surface; keep this unset for
    offscreen or headless execution.

.PARAMETER Report
    Destination path for the JSON report. When not given, the report is
    stored under Sagittarius_Elite_Warrior/Tasks/reports with a UTC timestamp
    in the filename for local analysis.

.EXAMPLE
    .\scripts\run-chart-benchmark.ps1
    # CI contract (offscreen), both backends, timestamped report under Tasks/reports

.EXAMPLE
    .\scripts\run-chart-benchmark.ps1 -Desktop
    # CI contract + Windows desktop visual assertion

.EXAMPLE
    .\scripts\run-chart-benchmark.ps1 -Backend native -Report .\out\bench.json
#>
[CmdletBinding()]
param(
    [ValidateSet("python", "native", "both")]
    [string]$Backend = "both",
    [switch]$Desktop,
    [string]$Report
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$botRoot   = Split-Path -Parent $scriptDir
$repoRoot  = Split-Path -Parent $botRoot

# $IsWindows only exists on PowerShell Core (6+); Windows PowerShell 5.1 is
# Windows-only, so its absence means "definitely Windows".
$isWindowsOs = if (Test-Path variable:IsWindows) { $IsWindows } else { $true }
$venvBinSubdir = if ($isWindowsOs) { "Scripts" } else { "bin" }
$exeSuffix     = if ($isWindowsOs) { ".exe" } else { "" }

$venvRoot = $null
if (Test-Path (Join-Path $botRoot ".venv")) { $venvRoot = Join-Path $botRoot ".venv" }
elseif (Test-Path (Join-Path $repoRoot ".venv")) { $venvRoot = Join-Path $repoRoot ".venv" }

$pythonExe = if ($venvRoot) { Join-Path (Join-Path $venvRoot $venvBinSubdir) "python$exeSuffix" } else { "python" }
if (-not (Test-Path $pythonExe)) { $pythonExe = "python" }

if (-not $Report) {
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
    $reportsDir = Join-Path (Join-Path $botRoot "Tasks") "reports"
    $Report = Join-Path $reportsDir "BOT-098F5_benchmark_$stamp.json"
}

$reportDir = Split-Path -Parent $Report
if ($reportDir -and -not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}

$envArgs = @(
    "-m", "Sagittarius_Elite_Warrior.scripts.benchmarking.chart_migration_benchmark",
    "--backend", $Backend,
    "--ci-contract",
    "--report", $Report
)
if ($Desktop) { $envArgs += "--desktop-contract" }

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  ▶  Chart Benchmark — $Backend $(if ($Desktop) { '(CI + Desktop)'} else { '(CI)'})" -ForegroundColor Cyan
Write-Host "     Report → $Report" -ForegroundColor DarkGray
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

$needsOffscreen = -not $Desktop -and -not $env:QT_QPA_PLATFORM
if ($needsOffscreen) { $env:QT_QPA_PLATFORM = "offscreen" }

Push-Location $repoRoot
try {
    & $pythonExe @envArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌  Chart Benchmark FAILED" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✅  Chart Benchmark passed" -ForegroundColor Green
    Write-Host "     Report: $Report" -ForegroundColor DarkGray

    $json = Get-Content $Report -Raw | ConvertFrom-Json
    if ($json.python_over_native_median_speedup) {
        Write-Host ("     Speedup (python/native median): {0}x" -f $json.python_over_native_median_speedup) -ForegroundColor DarkGray
    }
} finally { Pop-Location }
