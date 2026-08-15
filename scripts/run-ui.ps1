param(
    # Enables dev-mode UI instrumentation (currently: logs every button
    # click to each screen's System Monitor). Usage: run-ui.ps1 -Dev
    [switch]$Dev
)

# Also accept the literal GNU-style "--dev" form some users may type.
if ($args -contains "--dev") {
    $Dev = $true
}

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BotRoot = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $BotRoot

# Support cloning with hyphens (Sagittarius-Elite-Warrior) while code expects underscores
$PackageName = "Sagittarius_Elite_Warrior"
if ((Split-Path -Leaf $BotRoot) -ne $PackageName) {
    Write-Host "Repository name is '$(Split-Path -Leaf $BotRoot)', but Python expects '$PackageName'. Creating alias..." -ForegroundColor Yellow
    $AliasDir = Join-Path $BotRoot ".venv_alias"
    if (-not (Test-Path $AliasDir)) { New-Item -ItemType Directory -Path $AliasDir -Force | Out-Null }
    $JunctionPath = Join-Path $AliasDir $PackageName
    if (-not (Test-Path $JunctionPath)) { New-Item -ItemType Junction -Path $JunctionPath -Target $BotRoot -Force | Out-Null }
    $env:PYTHONPATH = $AliasDir
} else {
    $env:PYTHONPATH = $ProjectRoot
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

$ActivateScript = if ($IsWindows) {
    Join-Path $VenvRoot "Scripts/Activate.ps1"
} else {
    Join-Path $VenvRoot "bin/Activate.ps1"
}

if (-not (Test-Path $ActivateScript)) {
    throw "Virtual environment activation script was not found at $ActivateScript"
}

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
. $ActivateScript

$VenvPython = if ($IsWindows) {
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

Set-Location $BotRoot
$UIEntry = [System.IO.Path]::Combine($BotRoot, "src", "presentation", "ui", "main_window.py")

$UIArgs = @()
if ($Dev) {
    $UIArgs += "--dev"
    Write-Host "Starting PySide6 Trading Bot UI (dev mode)..." -ForegroundColor Green
} else {
    Write-Host "Starting PySide6 Trading Bot UI..." -ForegroundColor Green
}

& $VenvPython $UIEntry @UIArgs
