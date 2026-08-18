# BOT-098F6D — Backtest native opt-in cutover

**Parent:** [`BOT-098F6`](BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F5`, `BOT-098F6A`, `BOT-098F6C`  
**Priority:** P1  
**Complexity:** L  
**Status:** Backlog

## Goal

Wire the factory into the production Backtest route so a configuration-selected
native OHLC path can render real Backtest data, with explicit capability
fallback to the existing Python renderer for modes not yet native-supported.

## Scope

Allowed native scope in this slice:

- OHLC candles, volume bars, price-overlay indicators, truthful LONG entry/exit
  markers, pan/zoom, crosshair/tooltip, timezone-aware axes and dev FPS.
  They must be driven by a stable config selection and action-aware
  diagnostics.

Outside native scope in this slice (must retain Python explicitly):

- equity-only and BOTH subplot, line/area/Heikin-Ashi implementations in C++,
  script regions, script info and arbitrary script marker text. Unsupported
  presentation modes must select the Python host with one explicit testable
  transition rule; no silent visual omission.

This slice also owns the user-facing contract: config layering, env source
followed by app/user JSON sources, `backtest.chart.backend =
python|native|auto` enum/default, fallback selection, backend-switched teardown
and integration coverage.

## Acceptance criteria

1. DI registers the factory only; no QWidget/QQuickWidget is singleton.
2. Each BackTestView construction selects host via the stable config hierarchy;
   selection is once per view construction and requires view reconstruction on
   backend change.
3. Missing plugin, ABI mismatch, construction or post-construction viewport,
   snapshot or QML failure returns the Python fallback once with one actionable
   log and zero blank chart.
4. OHLC backtest and preview data reach the rendered host; unsupported modes
   newly take the Python fallback deterministically; one valid Backtest probe
   path exits zero before the benchmark.
5. `BOT-098F5` DPR 1 and DPR 2 reports are published against the production host
   wiring; native must not lose the coverable host integration tests.
6. Unit, Backtest integration, sanity/layout and probe tests, plus
   `./scripts/ci-local.ps1 -Full`, pass.
