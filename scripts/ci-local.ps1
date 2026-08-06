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

.EXAMPLE
    .\scripts\ci-local.ps1
    .\scripts\ci-local.ps1 -SkipLint
    .\scripts\ci-local.ps1 -SkipTests
#>
[CmdletBinding()]
param(
    [switch]$SkipLint,
    [switch]$SkipTests
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

$venvActivateWin = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
$venvActivateLin = Join-Path $botRoot ".venv/bin/activate"

if (Test-Path $venvActivateWin) {
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
    Write-Step "Pytest with Coverage"
    Push-Location $repoRoot
    try {
        $env:PYTHONPATH = $repoRoot
        $env:QT_QPA_PLATFORM = "offscreen"
        pytest Binace_Bot/tests --cov=Binace_Bot/src --cov-report=term-missing -v
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
