$ErrorActionPreference = "Stop"

# Get absolute paths to calculate the root of the project
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BotRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $BotRoot

# Inject the parent root directory into PYTHONPATH so sagittarius_engine can be resolved
$env:PYTHONPATH = $ProjectRoot

# Attempt to find and activate the virtual environment
$VenvPaths = @(
    Join-Path $ProjectRoot ".venv"
    Join-Path $ProjectRoot "venv"
    Join-Path $BotRoot ".venv"
    Join-Path $BotRoot "venv"
)

$VenvActivated = $false
foreach ($path in $VenvPaths) {
    $ActivateScript = Join-Path $path "Scripts\Activate.ps1"
    if (Test-Path $ActivateScript) {
        Write-Host "Activating virtual environment at $path..." -ForegroundColor Cyan
        . $ActivateScript
        $VenvActivated = $true
        break
    }
}

if (-not $VenvActivated) {
    Write-Host "WARNING: No Python virtual environment (.venv or venv) found in $ProjectRoot or $BotRoot. Using global python environment." -ForegroundColor Yellow
}

# Change working directory to the Bot root and execute the main entrypoint
Set-Location -Path $BotRoot
python .\src\main.py $args
