param(
    # Enables dev-mode UI instrumentation (log level DEBUG, session written
    # to logs/dev-<timestamp>.log): click logs and a paint-event FPS overlay
    # on the Backtest graph. Usage: run-ui.ps1 -Dev
    [switch]$Dev,
    # Strictly more verbose than -Dev, not a separate mode — implies
    # everything -Dev does, plus drops the log threshold to TRACE (one
    # level below DEBUG) and writes to logs/debug-<timestamp>.log instead.
    # See .agents/rules/logging-rule.md §6-7. Usage: run-ui.ps1 -Debug
    [switch]$Debug,
    # Option 2 per .agents/rules/install-rule.md: opt-in to develop/debug
    # Sagittarius Engine locally from sibling checkout instead of official GitHub.
    # Usage: run-ui.ps1 -LocalEngine
    [switch]$LocalEngine
)

# Also accept the literal GNU-style "--dev"/"--debug"/"--local-engine" forms some users may type.
if ($args -contains "--dev") {
    $Dev = $true
}
if ($args -contains "--debug") {
    $Debug = $true
}
if ($args -contains "--local-engine" -or $args -contains "-LocalEngine") {
    $LocalEngine = $true
}

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BotRoot = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $BotRoot

$isWindowsPlatform = ($env:OS -eq "Windows_NT") -or ($PSVersionTable.PSEdition -eq "Desktop") -or ($IsWindows -eq $true)
$PathSeparator = if ($isWindowsPlatform) { ";" } else { ":" }

# Sibling engine checkout handling per .agents/rules/install-rule.md:
# Default (Option 1): Engine is loaded from the virtual environment (installed from GitHub).
# Option 2 (Development & Debugging): Sibling checkout is only added to PYTHONPATH if -LocalEngine is specified.
$PythonPathEntries = @($ProjectRoot)
$EngineRoot = Join-Path $ProjectRoot "Sagittarius_Engine"
if ($LocalEngine) {
    if (Test-Path (Join-Path $EngineRoot "sagittarius_engine")) {
        $PythonPathEntries += $EngineRoot
        Write-Host "Using local Sagittarius Engine checkout from $EngineRoot (-LocalEngine)..." -ForegroundColor Yellow
    } else {
        Write-Warning "Local engine checkout requested (-LocalEngine), but '$EngineRoot' was not found."
    }
}
$env:PYTHONPATH = $PythonPathEntries -join $PathSeparator

# Support cloning with hyphens (Sagittarius-Elite-Warrior) while code expects underscores
$PackageName = "Sagittarius_Elite_Warrior"
if ((Split-Path -Leaf $BotRoot) -ne $PackageName) {
    Write-Host "Repository name is '$(Split-Path -Leaf $BotRoot)', but Python expects '$PackageName'. Creating alias..." -ForegroundColor Yellow
    $AliasDir = Join-Path $BotRoot ".venv_alias"
    if (-not (Test-Path $AliasDir)) { New-Item -ItemType Directory -Path $AliasDir -Force | Out-Null }
    $JunctionPath = Join-Path $AliasDir $PackageName
    if (-not (Test-Path $JunctionPath)) { New-Item -ItemType Junction -Path $JunctionPath -Target $BotRoot -Force | Out-Null }
    $env:PYTHONPATH = "$AliasDir$PathSeparator$($PythonPathEntries -join $PathSeparator)"
} else {
    $env:PYTHONPATH = $PythonPathEntries -join $PathSeparator
}

$PythonCandidates = @("python", "python3")
$PythonCommand = $null
foreach ($candidate in $PythonCandidates) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($command) {
        $PythonCommand = $command.Source
        break
    }
}

if (-not $PythonCommand) {
    throw "Python was not found. Install Python 3 and ensure 'python' or 'python3' is available."
}

$VenvRoot = Join-Path $BotRoot ".venv"
if (-not (Test-Path $VenvRoot)) {
    Write-Host "Creating virtual environment at $VenvRoot..." -ForegroundColor Cyan
    & $PythonCommand -m venv $VenvRoot
}

$ActivateScript = if ($isWindowsPlatform) {
    Join-Path $VenvRoot "Scripts/Activate.ps1"
} else {
    Join-Path $VenvRoot "bin/Activate.ps1"
}

if (-not (Test-Path $ActivateScript)) {
    throw "Virtual environment activation script was not found at $ActivateScript"
}

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
. $ActivateScript

$VenvPython = if ($isWindowsPlatform) {
    Join-Path $VenvRoot "Scripts/python.exe"
} else {
    Join-Path $VenvRoot "bin/python"
}

if (-not (Test-Path $VenvPython)) {
    $VenvPython = Join-Path $VenvRoot "bin/python3"
}

if (Test-Path (Join-Path $BotRoot "requirements.txt")) {
    Write-Host "Installing Python dependencies from requirements.txt..." -ForegroundColor Cyan
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $BotRoot "requirements.txt")
}

if ($LocalEngine) {
    if (Test-Path (Join-Path $EngineRoot "pyproject.toml")) {
        Write-Host "Installing Sagittarius Engine from the local sibling checkout (-LocalEngine)..." -ForegroundColor Cyan
        & $VenvPython -m pip install -e $EngineRoot
    } else {
        throw "Local engine checkout (-LocalEngine) requested, but pyproject.toml not found at $EngineRoot"
    }
} else {
    Write-Host "Installing Sagittarius Engine from GitHub (Option 1 per install-rule.md)..." -ForegroundColor Cyan
    & $VenvPython -m pip install "git+https://github.com/anhembedded/Sagittarius_Engine.git"
}

if ($LASTEXITCODE -ne 0) {
    throw "Sagittarius Engine installation failed with exit code $LASTEXITCODE."
}

Set-Location $BotRoot
$UIEntry = [System.IO.Path]::Combine($BotRoot, "src", "presentation", "ui", "main_window.py")

$UIArgs = @()
if ($Debug) {
    # --debug alone already implies --dev's own behavior on the Python side
    # (resolve_dev_verbosity treats it as strictly more verbose, not a
    # separate mode) — passing both would be redundant, not wrong, but
    # only one is needed.
    $UIArgs += "--debug"
    Write-Host "Starting PySide6 Trading Bot UI (debug mode — log level TRACE)..." -ForegroundColor Green
} elseif ($Dev) {
    $UIArgs += "--dev"
    Write-Host "Starting PySide6 Trading Bot UI (dev mode — log level DEBUG)..." -ForegroundColor Green
} else {
    Write-Host "Starting PySide6 Trading Bot UI..." -ForegroundColor Green
}

& $VenvPython $UIEntry @UIArgs
