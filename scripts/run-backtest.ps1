$ErrorActionPreference = "Stop"

# Get the directory of the current script and navigate to the project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir

# Set the working directory to the project root
Set-Location $ProjectRoot

# Define the path to the virtual environment activation script
$VenvActivate = Join-Path $ProjectRoot "..\.venv\Scripts\Activate.ps1"

# Check if the virtual environment exists
if (-Not (Test-Path $VenvActivate)) {
    Write-Host "Virtual environment not found at $VenvActivate" -ForegroundColor Red
    Write-Host "Please create it first (e.g., python -m venv .venv)" -ForegroundColor Yellow
    exit 1
}

# Activate the virtual environment
& $VenvActivate

# Set PYTHONPATH so absolute imports work correctly
$env:PYTHONPATH = (Get-Item "..").FullName

Write-Host "Starting Desktop Backtester App..." -ForegroundColor Green
python .\src\presentation\ui\backtest_app.py
