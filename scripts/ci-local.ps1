#Requires -Version 5.1
<#
.SYNOPSIS
    Local CI runner - mirrors the GitHub Actions CI pipeline for Binance Bot.

.DESCRIPTION
    Runs Ruff lint, Ruff format check, and Pytest with coverage locally.
    Use this to validate your changes before pushing.

.PARAMETER SkipLint
    Skip Ruff lint and format check steps.

.PARAMETER SkipTests
    Skip Pytest step.

.PARAMETER SanityOnly
    Run only tests/sanity (boot/import-time checks, no coverage instrumentation —
    meant to finish in well under a second). Implies -SkipLint.

.PARAMETER UnitOnly
    Run only tests/unit (isolated logic, mocked I/O). Implies -SkipLint.

.PARAMETER Full
    Explicit alias for the default behavior: lint + format + the full test suite
    with the --cov-fail-under=80 gate enforced.

.PARAMETER Parallel
    Run tests in parallel across multiple CPU workers using pytest-xdist (-n auto).

.PARAMETER Workers
    Specify the exact number of worker processes for parallel testing (e.g. -Workers 4).

.PARAMETER IncludeFlakyUi
    Also run tests/integration/presentation/ui/, which is excluded by default
    (see BOT-038) because running it as one full block intermittently crashes
    the process natively (Qt/PySide6) or hangs — not a real assertion
    failure, and not reproducible on demand. Pass this only when deliberately
    investigating BOT-038.

.EXAMPLE
    .\scripts\ci-local.ps1
    .\scripts\ci-local.ps1 -Parallel
    .\scripts\ci-local.ps1 -UnitOnly -Parallel
    .\scripts\ci-local.ps1 -SkipLint
    .\scripts\ci-local.ps1 -SkipTests
    .\scripts\ci-local.ps1 -SanityOnly
    .\scripts\ci-local.ps1 -UnitOnly
    .\scripts\ci-local.ps1 -Full
    .\scripts\ci-local.ps1 -IncludeFlakyUi
#>
[CmdletBinding()]
param(
    [switch]$SkipLint,
    [switch]$SkipTests,
    [switch]$SanityOnly,
    [switch]$UnitOnly,
    [switch]$Full,
    [switch]$Parallel,
    [int]$Workers = 0,
    [switch]$IncludeFlakyUi
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Name)
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  ▶  $Name" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Name)
    Write-Host "  ✅  $Name passed" -ForegroundColor Green
}

function Write-Failure {
    param([string]$Name)
    Write-Host "  ❌  $Name FAILED" -ForegroundColor Red
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$botRoot   = Split-Path -Parent $scriptDir
$repoRoot  = Split-Path -Parent $botRoot

# ---------------------------------------------------------------------------
# Resolve which test tier to run and whether coverage/lint apply.
# -SanityOnly / -UnitOnly are fast dev-loop subsets: no lint, no --cov-fail-under
# (a partial test run always under-reports total coverage). -Full is just the
# default full-suite-with-coverage-gate behavior, spelled out explicitly.
#
# Project rule (code-rule.md): sanity tests MUST always run alongside unit tests.
# -UnitOnly therefore runs sanity first (sequential — Qt cannot use xdist) then
# unit tests (parallel if -Parallel/-Workers is set).
# ---------------------------------------------------------------------------
$pytestTarget = "Sagittarius_Elite_Warrior/tests"
$useCoverage = $true
$enforceCoverageGate = $true
$runSanityPass = $false   # separate sequential sanity pass before unit tests

if ($SanityOnly) {
    $pytestTarget = "Sagittarius_Elite_Warrior/tests/sanity"
    $useCoverage = $false
    $enforceCoverageGate = $false
    $SkipLint = $true
} elseif ($UnitOnly) {
    # Unit-only fast loop: run sanity first (sequential), then unit (parallel).
    # This enforces the project rule that sanity always ships with every feature.
    $pytestTarget = "Sagittarius_Elite_Warrior/tests/unit"
    $enforceCoverageGate = $false
    $SkipLint = $true
    $runSanityPass = $true
}

$venvActivateWin = if (Test-Path (Join-Path $repoRoot ".venv\Scripts\Activate.ps1")) {
    Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
} elseif (Test-Path (Join-Path $botRoot ".venv\Scripts\Activate.ps1")) {
    Join-Path $botRoot ".venv\Scripts\Activate.ps1"
} else {
    $null
}
$venvActivateLin = Join-Path $botRoot ".venv/bin/activate"

if ($venvActivateWin) {
    Write-Host "Activating venv (Windows)..." -ForegroundColor DarkGray
    & $venvActivateWin
} elseif (Test-Path $venvActivateLin) {
    Write-Host "Activating venv (Linux)..." -ForegroundColor DarkGray
    # In pwsh on Linux, sourcing a bash script doesn't work natively the same way,
    # but we can just run the commands directly using the venv python/ruff/pytest binaries.
    $env:PATH = "$(Join-Path $botRoot '.venv/bin'):$env:PATH"
} else {
    Write-Warning "Virtual environment not found. Using system Python."
}

$failed = @()

if (-not $SkipLint) {
    Write-Step "Ruff — Lint (ruff check src tests)"
    Push-Location $botRoot
    try {
        ruff check src tests
        if ($LASTEXITCODE -ne 0) { $failed += "Ruff Lint"; Write-Failure "Ruff Lint" }
        else { Write-Success "Ruff Lint" }
    } catch {
        $failed += "Ruff Lint"; Write-Failure "Ruff Lint"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }

    Write-Step "Ruff — Format Check (ruff format --check src tests)"
    Push-Location $botRoot
    try {
        ruff format --check src tests
        if ($LASTEXITCODE -ne 0) { $failed += "Ruff Format"; Write-Failure "Ruff Format" }
        else { Write-Success "Ruff Format" }
    } catch {
        $failed += "Ruff Format"; Write-Failure "Ruff Format"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }
}

if (-not $SkipTests) {
    $testExecutionRoot = $repoRoot
    if (-not (Test-Path (Join-Path $repoRoot "Sagittarius_Elite_Warrior"))) {
        if ((Split-Path -Leaf $botRoot) -ne "Sagittarius_Elite_Warrior") {
            $aliasDir = Join-Path $botRoot ".venv_alias"
            if (-not (Test-Path $aliasDir)) { New-Item -ItemType Directory -Path $aliasDir -Force | Out-Null }
            $junctionPath = Join-Path $aliasDir "Sagittarius_Elite_Warrior"
            if (-not (Test-Path $junctionPath)) { New-Item -ItemType Junction -Path $junctionPath -Target $botRoot -Force | Out-Null }
            $testExecutionRoot = $aliasDir
        }
    }

    $env:PYTHONPATH = $testExecutionRoot
    $env:QT_QPA_PLATFORM = "offscreen"

    # -------------------------------------------------------------------------
    # Step A (optional): dedicated sequential sanity pass for -UnitOnly.
    # Sanity tests boot real Qt/DI — they MUST run single-process (no xdist).
    # -------------------------------------------------------------------------
    if ($runSanityPass) {
        Write-Step "Sanity Tests (sequential — Qt DI boot checks)"
        Push-Location $testExecutionRoot
        try {
            pytest "Sagittarius_Elite_Warrior/tests/sanity" -v
            if ($LASTEXITCODE -ne 0) { $failed += "Sanity"; Write-Failure "Sanity" }
            else { Write-Success "Sanity" }
        } catch {
            $failed += "Sanity"; Write-Failure "Sanity"
            Write-Host $_.Exception.Message -ForegroundColor Yellow
        } finally { Pop-Location }
    }

    # -------------------------------------------------------------------------
    # Step B: main pytest run (unit, sanity-only, or full).
    # -------------------------------------------------------------------------
    Write-Step "Pytest ($pytestTarget)"
    Push-Location $testExecutionRoot
    try {
        $pytestArgs = @($pytestTarget, "-v")
        if (-not $IncludeFlakyUi) {
            # BOT-038: running this dir as one full block intermittently
            # crashes/hangs the process natively (Qt/PySide6) — not a real
            # test failure. Excluded by default; pass -IncludeFlakyUi to
            # opt back in when deliberately investigating BOT-038.
            $pytestArgs += "--ignore=Sagittarius_Elite_Warrior/tests/integration/presentation/ui"
        }
        if ($useCoverage) {
            $pytestArgs += "--cov=Sagittarius_Elite_Warrior/src"
            $pytestArgs += "--cov-report=term-missing"
            if ($enforceCoverageGate) { $pytestArgs += "--cov-fail-under=80" }
        }
        if ($Parallel -or $Workers -gt 0) {
            # Default 6 workers — determined by benchmark sweep as the sweet spot
            # for this Windows machine (spawn overhead kills gains above 6).
            # Override with -Workers N to use a different count.
            $workerCount = if ($Workers -gt 0) { "$Workers" } else { "6" }
            $pytestArgs += @("-n", $workerCount)
        }

        pytest @pytestArgs
        if ($LASTEXITCODE -ne 0) { $failed += "Pytest"; Write-Failure "Pytest" }
        else { Write-Success "Pytest" }
    } catch {
        $failed += "Pytest"; Write-Failure "Pytest"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
if ($failed.Count -eq 0) {
    Write-Host "  🎉  All checks passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  💥  Failed steps: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
