#Requires -Version 5.1
<#
.SYNOPSIS
    Configure and build the Sagittarius.NativeChart QML plugin with CMake.

.DESCRIPTION
    Resolves the repository virtual environment, requires a Qt SDK whose exact
    version matches PySide6, and writes the plugin to build/native-chart/qml.
    The build directory is disposable and excluded from Git.

.PARAMETER Configuration
    CMake build configuration. Defaults to Release.

.PARAMETER Clean
    Remove only build/native-chart before configuring.

.EXAMPLE
    .\scripts\build-native-chart.ps1
    .\scripts\build-native-chart.ps1 -Clean
#>
[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release", "RelWithDebInfo")]
    [string]$Configuration = "Release",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$botRoot = Split-Path -Parent $scriptDir
$sourceDir = Join-Path $botRoot "native\chart_renderer"
$buildDir = Join-Path $botRoot "build\native-chart"
$pythonExe = Join-Path $botRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment not found at $pythonExe"
}

$pysideVersion = (& $pythonExe -c "import PySide6; print(PySide6.__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $pysideVersion) {
    throw "Could not read the PySide6 version from $pythonExe"
}

$qtRoot = $env:SAGITTARIUS_QT_ROOT
if (-not $qtRoot) {
    $qtRoot = Join-Path $env:LOCALAPPDATA "SagittariusToolchains\Qt\$pysideVersion\msvc2022_64"
}

$qtConfig = Join-Path $qtRoot "lib\cmake\Qt6\Qt6Config.cmake"
$qmakeExe = Join-Path $qtRoot "bin\qmake.exe"
if (-not (Test-Path $qtConfig) -or -not (Test-Path $qmakeExe)) {
    throw @"
Qt SDK $pysideVersion was not found at:
  $qtRoot
Install the matching MSVC 2022 Qt SDK or set SAGITTARIUS_QT_ROOT.
"@
}

$qtVersion = (& $qmakeExe -query QT_VERSION).Trim()
if ($qtVersion -ne $pysideVersion) {
    throw "Qt SDK $qtVersion does not match PySide6 $pysideVersion. Refusing an ABI-unsafe build."
}

if ($Clean -and (Test-Path $buildDir)) {
    $resolvedBuild = (Resolve-Path -LiteralPath $buildDir).Path
    $resolvedBotRoot = (Resolve-Path -LiteralPath $botRoot).Path
    if (-not $resolvedBuild.StartsWith($resolvedBotRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean build directory outside the repository: $resolvedBuild"
    }
    Remove-Item -LiteralPath $resolvedBuild -Recurse -Force
}

& cmake -S $sourceDir -B $buildDir `
    -G "Visual Studio 17 2022" `
    -A x64 `
    "-DCMAKE_PREFIX_PATH=$qtRoot"
if ($LASTEXITCODE -ne 0) {
    throw "CMake configure failed for Sagittarius.NativeChart"
}

& cmake --build $buildDir --config $Configuration --parallel
if ($LASTEXITCODE -ne 0) {
    throw "CMake build failed for Sagittarius.NativeChart"
}

$qmlImportRoot = Join-Path $buildDir "qml"
$moduleDir = Join-Path $qmlImportRoot "Sagittarius\NativeChart"
if (-not (Test-Path (Join-Path $moduleDir "qmldir"))) {
    throw "Native QML module metadata was not generated at $moduleDir"
}

Write-Host "Native chart plugin ready." -ForegroundColor Green
Write-Host "QML import root: $qmlImportRoot"
Write-Host "Qt/PySide ABI:  $qtVersion"
