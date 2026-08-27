#Requires -Version 5.1
<#
.SYNOPSIS
    Local CI runner - mirrors the GitHub Actions CI pipeline for Binance Bot.

.DESCRIPTION
    Runs Ruff lint, Ruff format check, Mypy static type check, and Pytest
    with coverage locally.

    By default, unit/full test runs use 6 parallel workers (benchmark sweet spot
    on this machine). Sanity tests always run on 1 sequential process because they
    boot a real QApplication and cannot share Qt process context across xdist workers.

    By default, sanity and unit run CONCURRENTLY: sanity launches as a background
    job while unit tests execute in the foreground with 6 workers — total wall-clock
    time ≈ max(sanity_time, unit_time) instead of their sum.

.PARAMETER SkipLint
    Skip Ruff lint, Ruff format check, and Mypy static type check steps.

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
    No-op as of 2026-08-25 (BOT-038 re-verified, does not reproduce): tests/integration/presentation/ui/ now runs by default in every mode. Kept only so existing invocations of this flag do not error.

.EXAMPLE
    .\scripts\ci-local.ps1                  # Full: lint + parallel tests (default)
    .\scripts\ci-local.ps1 -UnitOnly        # Unit (6 workers) + sanity (concurrent)
    .\scripts\ci-local.ps1 -SanityOnly      # Sanity only
    .\scripts\ci-local.ps1 -Workers 4       # Full with 4 workers
    .\scripts\ci-local.ps1 -SkipLint        # Full, skip lint
    .\scripts\ci-local.ps1 -IncludeFlakyUi  # No-op flag, kept for compatibility -- see PARAMETER IncludeFlakyUi
#>
[CmdletBinding()]
param(
    [switch]$SkipLint,
    [switch]$SkipTests,
    [switch]$SanityOnly,
    [switch]$UnitOnly,
    [switch]$Full,
    [int]$Workers = 6,   # Default: 6 workers (benchmark sweet spot for this machine)
    [switch]$IncludeFlakyUi,
    # code-rule.md §4 "CI/CD MUST capture a log file, then scan it for problem
    # levels": a green exit code is not proof a run was clean. Set this only
    # to triage a run whose hits are already understood and recorded — never
    # as the normal way to get a green build.
    [switch]$AllowLogWarnings
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

#: code-rule.md §4 — scan a captured run log for the problem levels
#: logging-rule.md defines (WARNING/ERROR/CRITICAL), using that file's own
#: documented matcher. Automated here rather than left to a human/AI reading
#: the log by hand, so it actually happens on every run.
#:
#: Matches the `logger - LEVEL - message` shape a real log line has, NOT bare
#: words: pytest's own output says things like "warnings summary" and "ERROR"
#: for collection errors, which are not application log records.
function Invoke-RunLogScan {
    param([string]$LogFile, [string]$Label)

    if (-not (Test-Path $LogFile)) {
        Write-Host "  ⚠️  $Label — no log file captured at $LogFile" -ForegroundColor Yellow
        return $false
    }

    $hits = Select-String -Path $LogFile -Pattern '- (WARNING|ERROR|CRITICAL) -'
    if (-not $hits -or $hits.Count -eq 0) {
        Write-Host "  ✅  $Label — no WARNING/ERROR/CRITICAL log records" -ForegroundColor Green
        return $false
    }

    Write-Host ""
    Write-Host "  🔎  $Label — $($hits.Count) problem-level log record(s) found:" -ForegroundColor Yellow
    foreach ($level in @('CRITICAL', 'ERROR', 'WARNING')) {
        $ofLevel = $hits | Where-Object { $_.Line -match "- $level -" }
        if ($ofLevel.Count -gt 0) {
            Write-Host "     $level : $($ofLevel.Count)" -ForegroundColor Yellow
        }
    }
    Write-Host ""
    # Distinct messages only — one real defect usually logs the same line on
    # every bar/tick/event, and 600 copies of it hide the other hits.
    $hits |
        ForEach-Object { $_.Line.Trim() } |
        Select-Object -Unique |
        Select-Object -First 25 |
        ForEach-Object { Write-Host "     $_" -ForegroundColor DarkYellow }
    Write-Host ""
    Write-Host "  Every hit MUST be investigated and reported (code-rule.md §4):" -ForegroundColor Yellow
    Write-Host "  either a real defect (then follow bug-fix-rule.md in full), or an" -ForegroundColor Yellow
    Write-Host "  understood expected condition, named with its reason." -ForegroundColor Yellow
    Write-Host "  Full log: $LogFile" -ForegroundColor DarkGray
    return $true
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$botRoot   = Split-Path -Parent $scriptDir
$repoRoot  = Split-Path -Parent $botRoot

# ONBOARDING.md §5 / BUG-029 / BUG-030 (2026-08-21): a truncated terminal or
# `| tail -N` view can hide a real failure ENTIRELY, not just add noise — a
# session reported "100% green" from a run that, fully captured, actually
# failed. Every step's full output (lint, mypy,
# tests, sanity) is captured to a real file automatically here, so nobody —
# human or AI — has to remember to redirect manually.
$logsDir = Join-Path $botRoot "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$transcriptLog = Join-Path $logsDir "ci-local-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
$latestLogPointer = Join-Path $logsDir "ci-local-latest.log"
$transcriptStarted = $false
try {
    Start-Transcript -Path $transcriptLog -Force | Out-Null
    $transcriptStarted = $true
} catch {
    Write-Warning "Could not start full-run transcript ($($_.Exception.Message)) — falling back to the Tests-only log capture below."
}

# $IsWindows only exists on PowerShell Core (6+); Windows PowerShell 5.1 is
# Windows-only, so its absence means "definitely Windows".
$isWindowsOs = if (Test-Path variable:IsWindows) { $IsWindows } else { $true }
$venvBinSubdir = if ($isWindowsOs) { "Scripts" } else { "bin" }
$exeSuffix     = if ($isWindowsOs) { ".exe" } else { "" }
$tempDir = [System.IO.Path]::GetTempPath().TrimEnd('/', '\')

$venvRoot = $null
if (Test-Path (Join-Path $botRoot ".venv")) {
    $venvRoot = Join-Path $botRoot ".venv"
} elseif (Test-Path (Join-Path $repoRoot ".venv")) {
    $venvRoot = Join-Path $repoRoot ".venv"
}

$venvBinDir = if ($venvRoot) { Join-Path $venvRoot $venvBinSubdir } else { $null }
$pytestExe = if ($venvBinDir) { Join-Path $venvBinDir "pytest$exeSuffix" } else { "pytest" }
$pythonExe = if ($venvBinDir) { Join-Path $venvBinDir "python$exeSuffix" } else { "python" }
$ruffExe   = if ($venvBinDir) { Join-Path $venvBinDir "ruff$exeSuffix" } else { "ruff" }
$mypyExe   = if ($venvBinDir) { Join-Path $venvBinDir "mypy$exeSuffix" } else { "mypy" }

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

# The repo directory's own name now matches the Python package name
# (Sagittarius_Elite_Warrior), so $repoRoot alone on PYTHONPATH already
# resolves `import Sagittarius_Elite_Warrior` -- no .venv_alias symlink
# needed. That alias existed only to paper over a checkout cloned with
# hyphens (see run-ui.ps1's still-present name-mismatch fallback).
$pythonPathSeparator = [System.IO.Path]::PathSeparator
$env:PYTHONPATH = "$botRoot$pythonPathSeparator$repoRoot"

# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------
if (-not $SkipLint) {
    # `tools` alongside `src`/`tests`: the widget-kit showcase lives there, and a
    # whole top-level directory outside the lint gate is how the gate quietly
    # stops covering the repo. GitHub Actions (.github/workflows/ci.yml) has
    # lint tools since it was restored; this was the one place still missing it.
    Write-Step "Ruff — Lint Check (ruff check src tests tools)"
    Push-Location $botRoot
    try {
        & $ruffExe check src tests tools
        if ($LASTEXITCODE -ne 0) { $failed += "Ruff Lint"; Write-Failure "Ruff Lint" }
        else { Write-Success "Ruff Lint" }
    } catch {
        $failed += "Ruff Lint"; Write-Failure "Ruff Lint"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }

    Write-Step "Ruff — Format Check (ruff format --check src tests tools)"
    Push-Location $botRoot
    try {
        & $ruffExe format --check src tests tools
        if ($LASTEXITCODE -ne 0) { $failed += "Ruff Format"; Write-Failure "Ruff Format" }
        else { Write-Success "Ruff Format" }
    } catch {
        $failed += "Ruff Format"; Write-Failure "Ruff Format"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }

    # EPIC-002B — static type check, opened at the exact baseline EPIC-002A
    # measured (see [tool.mypy] in pyproject.toml), not at zero. Catches what
    # Ruff structurally cannot: e.g. a class that stops fully implementing a
    # Port's abstract methods (BUG-026). Must run from $repoRoot with both
    # `Sagittarius_Elite_Warrior/src` and `Sagittarius_Elite_Warrior/scripts`
    # in the SAME invocation — checking either alone lets exactly this error
    # class go undetected, because mypy then never resolves the Port's own
    # defining module in the same analysis pass (verified empirically while
    # writing this gate, see Tasks/reports/EPIC-002A_mypy_baseline_audit.md §3).
    Write-Step "Mypy — Static Type Check (src + scripts, baseline-gated)"
    Push-Location $repoRoot
    try {
        $engineDir = Join-Path $repoRoot "Sagittarius_Engine"
        $env:MYPYPATH = "$engineDir$pythonPathSeparator$repoRoot"
        $env:PYTHONPATH = "$botRoot$pythonPathSeparator$repoRoot"
        & $mypyExe --config-file (Join-Path $botRoot "pyproject.toml") --namespace-packages --explicit-package-bases "Sagittarius_Elite_Warrior/src" "Sagittarius_Elite_Warrior/scripts"
        if ($LASTEXITCODE -ne 0) { $failed += "Mypy"; Write-Failure "Mypy" }
        else { Write-Success "Mypy" }
    } catch {
        $failed += "Mypy"; Write-Failure "Mypy"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }

    # EPIC-011H / EPIC-012 -- the seven agent prompts under .agents/Skills/
    # (moved there from .jules/ in EPIC-012) are system prompts for agents that
    # run on a schedule with nobody watching, so a prompt pointing at a file the
    # repo has since deleted fails silently: the run completes and reports
    # success. sentinel.prompt.md instructed its agent for months to scan
    # against a rule file that has no commit in any branch's history. A checker
    # that only runs when someone remembers to type it is how that survived,
    # which is why it belongs here beside the other static gates rather than in
    # a test tier -- it needs neither Qt nor the engine, and runs in
    # milliseconds.
    Write-Step "Skill Prompts - Repository Reference Check (.agents/Skills/*.md)"
    Push-Location $botRoot
    try {
        & $pythonExe (Join-Path $botRoot "scripts/check_skill_prompt_references.py")
        if ($LASTEXITCODE -ne 0) { $failed += "Skill Prompt References"; Write-Failure "Skill Prompt References" }
        else { Write-Success "Skill Prompt References" }
    } catch {
        $failed += "Skill Prompt References"; Write-Failure "Skill Prompt References"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }

}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
if (-not $SkipTests) {
    # $repoRoot's basename check: the repo directory is expected to already
    # be named Sagittarius_Elite_Warrior, matching the Python package name,
    # so running pytest from $repoRoot with target "Sagittarius_Elite_Warrior/tests"
    # resolves against the real directory -- no .venv_alias symlink needed.
    $testExecutionRoot = $repoRoot

    $pythonPathSeparator = [System.IO.Path]::PathSeparator
    # $repoRoot is required so the sibling `sagittarius_engine` package
    # (one level above the bot root) is importable during tests.
    $env:PYTHONPATH = "$botRoot$pythonPathSeparator$repoRoot"
    $env:QT_QPA_PLATFORM = "offscreen"
    # Suppress 3rd-party DeprecationWarnings at Python interpreter level so they are
    # silenced even at module import time, before pytest filterwarnings can intercept.
    $env:PYTHONWARNINGS  = "ignore::DeprecationWarning:binance,ignore::DeprecationWarning:websockets"

    # code-rule.md §4 — every run is captured to a file so it can be scanned
    # for problem-level log records afterwards.
    $runLogFile = Join-Path $tempDir "ci_run_$([System.Diagnostics.Process]::GetCurrentProcess().Id).log"
    if (Test-Path $runLogFile) { Remove-Item $runLogFile -Force -ErrorAction SilentlyContinue }

    if ($SanityOnly) {
        # ----------------------------------------------------------------
        # Sanity-only mode: sequential, 1 process
        # ----------------------------------------------------------------
        Write-Step "Sanity Tests (sequential — Qt DI boot checks)"
        Push-Location $testExecutionRoot
        try {
            & $pytestExe $sanityTarget -v 2>&1 | Tee-Object -FilePath $runLogFile
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
        $sanityLogFile = Join-Path $tempDir "ci_sanity_$([System.Diagnostics.Process]::GetCurrentProcess().Id).log"
        $sanityJob = Start-Job -ScriptBlock {
            param($executionRoot, $pytestBin, $target, $logFile, $rootDir, $repoDir, $pathSep)
            Set-Location $executionRoot
            $env:PYTHONPATH     = "$executionRoot$pathSep$repoDir"
            $env:QT_QPA_PLATFORM = "offscreen"
            $output = & $pytestBin $target -v --rootdir=$rootDir 2>&1
            $output | Out-File -FilePath $logFile -Encoding utf8
            return $LASTEXITCODE
        } -ArgumentList $testExecutionRoot, $pytestExe, $sanityTarget, $sanityLogFile, $botRoot, $repoRoot, $pythonPathSeparator

        # Run main tests in foreground while sanity runs in background
        Push-Location $testExecutionRoot
        $mainExitCode = 0
        try {
            $pytestArgs = @($mainTarget, "-v", "--rootdir=$botRoot")

            # Exclude sanity from main parallel run (sanity runs in background job)
            $pytestArgs += "--ignore=Sagittarius_Elite_Warrior/tests/sanity"

            # BOT-038's exclusion is REMOVED as of 2026-08-25 -- see BOT-038's own
            # task file and Tasks/epics/EPIC-009_sanity_tier_redesign/ for the
            # re-verification. 7 runs (sequential and -n 6 + a concurrent sanity
            # process, matching this script's real load) produced zero crash
            # markers across the board -- the native Qt/PySide6 segfault this
            # exclusion existed for did not reproduce. Most likely cause: EPIC-006
            # deleted every QQuickWidget/QQmlEngine from this app (the object-
            # lifetime class BOT-038 itself named as the top suspect), so the
            # mechanism the bug depended on may no longer exist. -IncludeFlakyUi
            # is now a no-op kept only so existing invocations do not break; it
            # will be removed once nothing references it.
            if ($false) {
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

            & $pytestExe @pytestArgs 2>&1 | Tee-Object -FilePath $runLogFile
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
            # Fold the background job's output into the scanned run log too —
            # sanity boots the real app/DI, so it is exactly where a startup
            # WARNING/ERROR would surface (code-rule.md §4).
            Get-Content $sanityLogFile | Add-Content -Path $runLogFile
            Remove-Item $sanityLogFile -Force -ErrorAction SilentlyContinue
        }

        if ($mainExitCode -ne 0) { $failed += "Tests"; Write-Failure "Tests" }
        else { Write-Success "Tests" }

        if ($sanityExitCode -ne 0) { $failed += "Sanity"; Write-Failure "Sanity" }
        else { Write-Success "Sanity" }
    }

    # -----------------------------------------------------------------------
    # Run-log scan (code-rule.md §4) — a green exit code is not proof a run
    # was clean. BUG-021/BUG-022 both passed every test while logging the
    # real defect on every single bar.
    # -----------------------------------------------------------------------
    Write-Step "Run Log Scan (WARNING / ERROR / CRITICAL)"
    $hasLogProblems = Invoke-RunLogScan -LogFile $runLogFile -Label "Run log"
    if ($hasLogProblems) {
        if ($AllowLogWarnings) {
            Write-Host "  ⚠️  -AllowLogWarnings set — not failing the run." -ForegroundColor Yellow
        } else {
            $failed += "Log Scan"; Write-Failure "Log Scan"
        }
    }
}

$exitCode = if ($failed.Count -eq 0) { 0 } else { 1 }

if ($transcriptStarted) {
    try { Stop-Transcript | Out-Null } catch {}
    Copy-Item -Path $transcriptLog -Destination $latestLogPointer -Force -ErrorAction SilentlyContinue
}

# Machine-readable summary block, always the LAST thing printed. An agent
# reading truncated/tail output only needs these final lines — never trust
# a status claimed from anything earlier in the stream without opening
# LOG_FILE first (BUG-029/BUG-030, 2026-08-21: a run that "looked green" in
# a truncated view was actually failing every time, reproducibly).
Write-Host ""
Write-Host "===CI_LOCAL_RESULT==="
Write-Host "RESULT: $(if ($exitCode -eq 0) { 'PASS' } else { 'FAIL' })"
Write-Host "FAILED_STEPS: $(if ($failed.Count -eq 0) { 'none' } else { $failed -join ',' })"
Write-Host "LOG_FILE: $transcriptLog"
Write-Host "LOG_FILE_LATEST: $latestLogPointer"
Write-Host "INSTRUCTION: Do not report PASS/FAIL from this console output alone. Read LOG_FILE (grep for FAILED, ERROR, Traceback, ResourceWarning) before declaring the gate green."
Write-Host "===END_CI_LOCAL_RESULT==="

exit $exitCode
