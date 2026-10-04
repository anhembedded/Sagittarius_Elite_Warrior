$ErrorActionPreference = "Stop"

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BotRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $BotRoot

$env:PYTHONPATH = $ProjectRoot

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

# BUG-147: the engine CI builds (engine.ref's commit); nothing when already installed.
Write-Host "Installing Sagittarius Engine at engine.ref..." -ForegroundColor Cyan
& $VenvPython (Join-Path $PSScriptRoot "engine_pin.py") install
if ($LASTEXITCODE -ne 0) {
    throw "Sagittarius Engine installation failed with exit code $LASTEXITCODE."
}

Set-Location -Path $BotRoot
$EntryPoint = [System.IO.Path]::Combine($BotRoot, "src", "main.py")
& $VenvPython $EntryPoint @args
