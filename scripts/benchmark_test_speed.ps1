# Benchmark: Sweep across worker counts to find optimal parallelism
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$botRoot   = Split-Path -Parent $scriptDir
$repoRoot  = Split-Path -Parent $botRoot
$pytestExe = Join-Path $botRoot ".venv\Scripts\pytest.exe"

# The repo directory's own name matches the Python package name
# (Sagittarius_Elite_Warrior), so $repoRoot alone resolves
# `import Sagittarius_Elite_Warrior` -- no .venv_alias symlink needed.
$env:PYTHONPATH     = $repoRoot
$env:QT_QPA_PLATFORM = "offscreen"

$TestTarget = "Sagittarius_Elite_Warrior/tests/unit"

# Worker counts to sweep. "auto" is always included for reference.
$workerCounts = @(1, 2, 4, 6, 8, "auto")

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  PYTEST PARALLELISM SWEEP BENCHMARK" -ForegroundColor Cyan
Write-Host "  Target: $TestTarget" -ForegroundColor DarkGray
Write-Host "==================================================" -ForegroundColor Cyan

$results = [System.Collections.Generic.List[PSCustomObject]]::new()

foreach ($w in $workerCounts) {
    $label = if ($w -eq 1) { "Sequential (no xdist)" } else { "$w workers" }
    Write-Host "`n  ▶  Running: $label ..." -ForegroundColor Yellow

    Push-Location $repoRoot
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()

        if ($w -eq 1) {
            & $pytestExe $TestTarget -q --no-header 2>&1 |
                Select-String -Pattern "passed|failed|error" |
                Select-Object -Last 1
        } else {
            & $pytestExe $TestTarget -n $w -q --no-header 2>&1 |
                Select-String -Pattern "passed|failed|error" |
                Select-Object -Last 1
        }

        $sw.Stop()
        $elapsed = [math]::Round($sw.Elapsed.TotalSeconds, 2)
        Write-Host "     Done: $elapsed s" -ForegroundColor DarkGreen

        $results.Add([PSCustomObject]@{
            Workers = $w
            Label   = $label
            Seconds = $elapsed
        })
    } finally {
        Pop-Location
    }
}

# Find baseline (1 core) and best time
$baseline    = ($results | Where-Object { $_.Workers -eq 1 }).Seconds
$best        = $results | Sort-Object Seconds | Select-Object -First 1
$bestSpeedup = [math]::Round($baseline / $best.Seconds, 2)

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  RESULTS SUMMARY" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

foreach ($r in $results) {
    $speedup = if ($r.Workers -eq 1) { "1.00x (baseline)" } else { "$([math]::Round($baseline / $r.Seconds, 2))x" }
    $color   = if ($r.Seconds -eq $best.Seconds) { "Green" } else { "White" }
    $star    = if ($r.Seconds -eq $best.Seconds) { "  ★ FASTEST" } else { "" }
    Write-Host ("  {0,-25} {1,8} s   {2,-12}{3}" -f $r.Label, $r.Seconds, $speedup, $star) -ForegroundColor $color
}

Write-Host ""
Write-Host "  Best config : $($best.Label)" -ForegroundColor Cyan
Write-Host "  Best time   : $($best.Seconds) s (${bestSpeedup}x vs sequential)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Tip: Update ci-local.ps1 with -Workers $($best.Workers) for optimal speed." -ForegroundColor DarkGray
Write-Host ""
