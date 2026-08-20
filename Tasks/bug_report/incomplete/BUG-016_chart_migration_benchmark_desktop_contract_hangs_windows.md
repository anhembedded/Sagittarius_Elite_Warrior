# BUG-016 — `chart_migration_benchmark.py --backend both --desktop-contract` hangs indefinitely on Windows

**Reported:** 2026-08-19, same investigation as `BUG-015`.
**Severity:** P1 — this is the exact script `BOT-098F5` acceptance criterion 6
requires to run to completion for Windows Desktop E2E evidence; it currently
cannot run to completion at all.
**Status:** Open — not root-caused, process force-killed after hanging

## Symptom

```powershell
$env:PYTHONPATH = "."
python -m Sagittarius_Elite_Warrior.scripts.benchmarking.chart_migration_benchmark `
    --backend both --ci-contract --desktop-contract --report f5_windows_report.json
```

Run on a real Windows 11 machine (confirmed genuine Direct3D11 RHI, native
chart plugin freshly rebuilt against the exact installed `PySide6==6.11.1`
ABI via `.\scripts\build-native-chart.ps1` immediately beforehand — so this
is not a stale-DLL or ABI-mismatch symptom).

The process produced **zero stdout output** — not even the first informational
line the script normally prints before doing any real work — and sat idle for
over 15 minutes. `Get-Process` showed `Responding: False` and CPU time
essentially flat (22.19s → 23.42s across that whole window, i.e. almost no
further computation happened after some initial startup cost). This is not
"the Python renderer with 1,112 markers is slow" (BOT-098's own historical
number for that is ~9 updates/s, i.e. worst case seconds not minutes for 140
updates) — it reads as a genuine deadlock or blocked wait, not slow
computation. Process was force-killed
(`Stop-Process -Id <pid> -Force`); no report, no partial output, no
traceback was ever produced.

## What is confirmed, to narrow the search

- The native plugin builds and loads fine on this machine — separately
  confirmed via `native_backtest_chart_interaction_probe.py` (see `BUG-015`),
  which runs to completion repeatedly on the same install.
- `--ci-contract` alone (without `--desktop-contract`) was not isolated as a
  separate test in this session — worth trying first, since it's a strictly
  smaller code path and would tell you whether the hang is specific to the
  desktop-visual-evidence branch or present in the base run too.
- The hang happens before any of the script's own print statements fire (the
  script prints progress/report info as it goes per its own `--report`
  option and general structure), meaning it is very early — plausibly during
  `QApplication`/`QQuickView` construction, initial window show/expose wait,
  or the very first fixture/payload build, rather than deep inside the
  benchmark loop itself.

## Suggested next steps (not yet attempted)

1. Reproduce with `--backend native` and `--backend python` **separately**
   (not `both`) to find out which backend's code path the hang is actually
   in, or whether it happens before backend selection even matters.
2. Reproduce with `--ci-contract` only (no `--desktop-contract`) to check
   whether the desktop-visual-evidence branch specifically is implicated.
3. If it reproduces, attach a debugger or insert early `print(..., flush=True)`
   statements at the very top of `main()` and before/after `QApplication`
   construction to find exactly where execution stops — the complete absence
   of any output so far means the hang location is currently unknown, not
   just unresolved.
4. Check for a modal dialog or message box being constructed but never shown
   non-blockingly (a common cause of a Qt app going "Not Responding" with no
   output) — the "Windows visual probe" and "Desktop E2E" scripts in this
   area (`BUG-015`'s report) construct a plain `QApplication`/window
   directly, no dialogs, so if this script does anything different in its
   window/app setup that would be a lead.

## Relationship to `BUG-015`

Found in the same investigation, but is a different failure mode: `BUG-015`
is a real script (`native_backtest_chart_interaction_probe.py`) that *runs to
completion* and shows a real intermittent correctness issue. This bug is a
different script (`chart_migration_benchmark.py`) that does not run to
completion at all. Do not conflate the two while investigating either.
