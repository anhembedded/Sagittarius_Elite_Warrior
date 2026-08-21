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
$sourceDir = Join-Path (Join-Path $botRoot "native") "chart_renderer"
$buildDir = Join-Path (Join-Path $botRoot "build") "native-chart"

# $IsWindows only exists on PowerShell Core (6+); Windows PowerShell 5.1 is
# Windows-only, so its absence means "definitely Windows".
$isWindowsOs = if (Test-Path variable:IsWindows) { $IsWindows } else { $true }
$exeSuffix   = if ($isWindowsOs) { ".exe" } else { "" }
$venvBinSubdir = if ($isWindowsOs) { "Scripts" } else { "bin" }

$pythonExe = Join-Path (Join-Path (Join-Path $botRoot ".venv") $venvBinSubdir) "python$exeSuffix"

if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment not found at $pythonExe"
}

$pysideVersion = (& $pythonExe -c "import PySide6; print(PySide6.__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $pysideVersion) {
    throw "Could not read the PySide6 version from $pythonExe"
}

# The Qt SDK toolchain/ABI subfolder differs per platform (e.g. msvc2022_64
# on Windows, gcc_64 on Linux). SAGITTARIUS_QT_ROOT always overrides this.
$qtToolchain = if ($isWindowsOs) { "msvc2022_64" } else { "gcc_64" }
$qtRoot = $env:SAGITTARIUS_QT_ROOT
if (-not $qtRoot) {
    $toolchainsBase = if ($isWindowsOs) {
        Join-Path $env:LOCALAPPDATA "SagittariusToolchains"
    } else {
        Join-Path $HOME ".sagittarius-toolchains"
    }
    $qtRoot = Join-Path (Join-Path (Join-Path $toolchainsBase "Qt") $pysideVersion) $qtToolchain
}

$qtConfig = Join-Path (Join-Path (Join-Path (Join-Path $qtRoot "lib") "cmake") "Qt6") "Qt6Config.cmake"
$qmakeExe = Join-Path (Join-Path $qtRoot "bin") "qmake$exeSuffix"
if (-not (Test-Path $qtConfig) -or -not (Test-Path $qmakeExe)) {
    $sdkHint = if ($isWindowsOs) { "the matching MSVC 2022 Qt SDK" } else { "a matching Qt $pysideVersion SDK for $qtToolchain (e.g. via aqtinstall)" }
    throw @"
Qt SDK $pysideVersion was not found at:
  $qtRoot
Install $sdkHint or set SAGITTARIUS_QT_ROOT.
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

$cmakeConfigureArgs = @("-S", $sourceDir, "-B", $buildDir, "-DCMAKE_PREFIX_PATH=$qtRoot")
if ($isWindowsOs) {
    $cmakeConfigureArgs += @("-G", "Visual Studio 17 2022", "-A", "x64")
} elseif (Get-Command ninja -ErrorAction SilentlyContinue) {
    $cmakeConfigureArgs += @("-G", "Ninja")
}
# Non-Windows without Ninja falls through to CMake's platform default
# (Unix Makefiles), which needs no explicit -G/-A.

& cmake @cmakeConfigureArgs
if ($LASTEXITCODE -ne 0) {
    throw "CMake configure failed for Sagittarius.NativeChart"
}

& cmake --build $buildDir --config $Configuration --parallel
if ($LASTEXITCODE -ne 0) {
    throw "CMake build failed for Sagittarius.NativeChart"
}

$qmlImportRoot = Join-Path $buildDir "qml"
$moduleDir = Join-Path (Join-Path $qmlImportRoot "Sagittarius") "NativeChart"
if (-not (Test-Path (Join-Path $moduleDir "qmldir"))) {
    throw "Native QML module metadata was not generated at $moduleDir"
}

Write-Host "Native chart plugin ready." -ForegroundColor Green
Write-Host "QML import root: $qmlImportRoot"
Write-Host "Qt/PySide ABI:  $qtVersion"
Write-Host "Guide:          Docs\NATIVE_CHART_BUILD_AND_DEPLOY.md"
