$ErrorActionPreference = "Stop"

# Get absolute paths to calculate the root of the project
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BotRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $BotRoot

# Inject the parent root directory into PYTHONPATH so sagittarius_engine can be resolved
$env:PYTHONPATH = $ProjectRoot

# Change working directory to the Bot root and execute the main entrypoint
Set-Location -Path $BotRoot
python .\src\main.py $args
