#Requires -Version 5.1
<#
.SYNOPSIS
    Local CI runner - mirrors the GitHub Actions CI pipeline for Binance Bot.

.DESCRIPTION
    Runs Ruff lint, Ruff format check, and Pytest with coverage locally.

    By default, unit/full test runs use 6 parallel workers (benchmark sweet spot
    on this machine). Sanity tests always run on 1 sequential process because they
    boot a real QApplication and cannot share Qt process context across xdist workers.

    By default, sanity and unit run CONCURRENTLY: sanity launches as a background
    job while unit tests execute in the foreground with 6 workers — total wall-clock
    time ≈ max(sanity_time, unit_time) instead of their sum.

.PARAMETER SkipLint
    Skip Ruff lint and format check steps.

.PARAMETER SkipTests
    Skip Pytest step.

.PARAMETER SanityOnly
    Run only tests/sanity (boot/import-time checks, no coverage instrumentation).
    Implies -SkipLint.

.PARAMETER UnitOnly
    Run tests/unit (parallel) + tests/sanity (concurrent background, 1 core).
    Implies -SkipLint. No coverage gate — partial run always under-reports coverage.

.PARAMETER Full
    Explicit alias for the default behavior: lint + format + full parallel test
    suite with --cov-fail-under=80 gate enforced.

.PARAMETER Workers
    Override the number of parallel xdist worker processes (default: 6).
    Use -Workers 1 to force sequential execution.

.PARAMETER IncludeFlakyUi
    Also run tests/integration/presentation/ui/, excluded by default (BOT-038).

.EXAMPLE
    .\scripts\ci-local.ps1                  # Full: lint + parallel tests (default)
    .\scripts\ci-local.ps1 -UnitOnly        # Unit (6 workers) + sanity (concurrent)
    .\scripts\ci-local.ps1 -SanityOnly      # Sanity only
    .\scripts\ci-local.ps1 -Workers 4       # Full with 4 workers
    .\scripts\ci-local.ps1 -SkipLint        # Full, skip lint
    .\scripts\ci-local.ps1 -IncludeFlakyUi  # Full, include flaky UI integration
#>
[CmdletBinding()]
param(
    [switch]$SkipLint,
    [switch]$SkipTests,
    [switch]$SanityOnly,
    [switch]$UnitOnly,
    [switch]$Full,
    [int]$Workers = 6,   # Default: 6 workers (benchmark sweet spot for this machine)
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
$pytestExe = Join-Path $botRoot ".venv\Scripts\pytest.exe"

# ---------------------------------------------------------------------------
# Resolve which test tier to run and whether coverage/lint apply.
#
# Project rule (code-rule.md): sanity tests MUST always run alongside unit tests.
#
# All modes except -SanityOnly run unit + sanity. By default:
#   - Unit/full tests   → parallel, 6 workers (xdist)
#   - Sanity tests      → always sequential, 1 process (Qt DI boot)
#   - Execution model   → sanity runs as a background job while unit runs in
#                         foreground → total wall time ≈ max(sanity, unit)
# ---------------------------------------------------------------------------
$unitTarget  = "Sagittarius_Elite_Warrior/tests/unit"
$sanityTarget = "Sagittarius_Elite_Warrior/tests/sanity"
$useCoverage = $true
$enforceCoverageGate = $true

if ($SanityOnly) {
    $useCoverage = $false
    $enforceCoverageGate = $false
    $SkipLint = $true
} elseif ($UnitOnly) {
    $useCoverage = $false
    $enforceCoverageGate = $false
    $SkipLint = $true
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
    $env:PATH = "$(Join-Path $botRoot '.venv/bin'):$env:PATH"
} else {
    Write-Warning "Virtual environment not found. Using system Python."
}

$failed = @()

# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
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

    $env:PYTHONPATH     = $testExecutionRoot
    $env:QT_QPA_PLATFORM = "offscreen"
    # Suppress 3rd-party DeprecationWarnings at Python interpreter level so they are
    # silenced even at module import time, before pytest filterwarnings can intercept.
    $env:PYTHONWARNINGS  = "ignore::DeprecationWarning:binance,ignore::DeprecationWarning:websockets"

    if ($SanityOnly) {
        # ----------------------------------------------------------------
        # Sanity-only mode: sequential, 1 process
        # ----------------------------------------------------------------
        Write-Step "Sanity Tests (sequential — Qt DI boot checks)"
        Push-Location $testExecutionRoot
        try {
            & $pytestExe $sanityTarget -v
            if ($LASTEXITCODE -ne 0) { $failed += "Sanity"; Write-Failure "Sanity" }
            else { Write-Success "Sanity" }
        } catch {
            $failed += "Sanity"; Write-Failure "Sanity"
            Write-Host $_.Exception.Message -ForegroundColor Yellow
        } finally { Pop-Location }

    } else {
        # ----------------------------------------------------------------
        # Unit / Full mode:
        #   Sanity → background job (1 core, sequential)
        #   Unit   → foreground (Workers parallel, default 6)
        # Both run concurrently. Total time ≈ max(sanity, unit).
        # ----------------------------------------------------------------
        $workerCount = [math]::Max(1, $Workers)

        if ($UnitOnly) {
            $mainTarget = $unitTarget
            Write-Step "Unit ($workerCount workers) + Sanity (1 core) — running concurrently"
        } else {
            # Full: unit + integration (excluding flaky UI by default)
            $mainTarget = "Sagittarius_Elite_Warrior/tests"
            Write-Step "Full Tests ($workerCount workers, excl. sanity) + Sanity (1 core) — running concurrently"
        }

        # Launch sanity as a background PowerShell job
        $sanityLogFile = Join-Path $env:TEMP "ci_sanity_$([System.Diagnostics.Process]::GetCurrentProcess().Id).log"
        $sanityJob = Start-Job -ScriptBlock {
            param($executionRoot, $pytestBin, $target, $logFile, $rootDir)
            Set-Location $executionRoot
            $env:PYTHONPATH     = $executionRoot
            $env:QT_QPA_PLATFORM = "offscreen"
            $output = & $pytestBin $target -v --rootdir=$rootDir 2>&1
            $output | Out-File -FilePath $logFile -Encoding utf8
            return $LASTEXITCODE
        } -ArgumentList $testExecutionRoot, $pytestExe, $sanityTarget, $sanityLogFile, $botRoot

        # Run main tests in foreground while sanity runs in background
        Push-Location $testExecutionRoot
        $mainExitCode = 0
        try {
            $pytestArgs = @($mainTarget, "-v", "--rootdir=$botRoot")

            # Exclude sanity from main parallel run (sanity runs in background job)
            $pytestArgs += "--ignore=Sagittarius_Elite_Warrior/tests/sanity"

            if (-not $IncludeFlakyUi) {
                # BOT-038: intermittent native crash/hang in Qt process — excluded by default.
                $pytestArgs += "--ignore=Sagittarius_Elite_Warrior/tests/integration/presentation/ui"
            }
            if ($useCoverage) {
                $pytestArgs += "--cov=Sagittarius_Elite_Warrior/src"
                $pytestArgs += "--cov-report=term-missing"
                if ($enforceCoverageGate) { $pytestArgs += "--cov-fail-under=80" }
            }
            # Parallel: default 6 workers, override with -Workers N (-Workers 1 = sequential)
            if ($workerCount -gt 1) {
                $pytestArgs += @("-n", "$workerCount")
            }

            & $pytestExe @pytestArgs
            $mainExitCode = $LASTEXITCODE
        } catch {
            $mainExitCode = 1
            Write-Host $_.Exception.Message -ForegroundColor Yellow
        } finally { Pop-Location }

        # Wait for background sanity job and collect results
        Write-Host ""
        Write-Host "  ⏳ Waiting for sanity job to complete..." -ForegroundColor DarkGray
        $sanityExitCode = Receive-Job -Job $sanityJob -Wait -AutoRemoveJob

        # Print sanity output
        if (Test-Path $sanityLogFile) {
            Get-Content $sanityLogFile | Select-String -Pattern "PASSED|FAILED|ERROR|passed|failed|error|warning"
            Remove-Item $sanityLogFile -Force -ErrorAction SilentlyContinue
        }

        if ($mainExitCode -ne 0) { $failed += "Tests"; Write-Failure "Tests" }
        else { Write-Success "Tests" }

        if ($sanityExitCode -ne 0) { $failed += "Sanity"; Write-Failure "Sanity" }
        else { Write-Success "Sanity" }
    }
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
