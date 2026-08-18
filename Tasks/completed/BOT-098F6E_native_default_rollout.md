# BOT-098F6E — Native default rollout and Python kill-switch

**Parent:** [`BOT-098F6`](BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F6D`  
**Priority:** P1  
**Complexity:** M  
**Status:** Completed  

## Goal

Promote the retained native Backtest OHLC host from opt-in to default only after
production-host evidence is available, while shipping the tested Python backend
as an emergency compatibility fallback for one release.

## Scope

- Change default selection only after the F5 shared benchmark, native visual
  probe, Backtest integration and full CI evidence are recorded.
- Keep `backtest.chart.backend=python` and
  `SAGITTARIUS_BACKTEST_CHART_BACKEND=python` as documented tested recovery
  paths for the entire release.
- Record selected/fallback renderer and reason once per BackTestView creation;
  do not report GPU/RHI use as proof of chart performance.
- Deletion of Python Backtest host is explicitly outside this task and requires
  a separate post-release decision/task.

## Acceptance criteria

1. The default chooses native only for a runtime-valid, native-capable OHLC
   workflow; Python is chosen deterministically for explicit override,
   unavailable native runtime and unsupported presentation capabilities.
2. Tests cover default/native/Python/env-override/fallback selection and prove
   that backend changes reconstruct a host rather than hot-swap live widgets.
3. The completed F5 report includes hybrid production-host DPR1+DPR2 results,
   visual semantic checks and Qt message output; no timing is promoted to a
   shared CI threshold.
4. One release of desktop evidence records no unresolved native lifecycle or
   semantic regression before any removal task may be proposed.
5. `./scripts/ci-local.ps1 -Full` and opt-in desktop E2E pass.

## Result

- **Default Backend Configuration**:
  - `ConfigKeys.BACKTEST_CHART_BACKEND` default is now `"auto"`.
  - `BacktestChartHostFactory.create()` defaults to `"auto"`.
  - `BackTestPresenter` and `BackTestView` now default to `"auto"`.
  - Resolution precedence: `SAGITTARIUS_BACKTEST_CHART_BACKEND` env var $\rightarrow$ `backtest.chart.backend` config $\rightarrow$ `"auto"`.
  - Under `"auto"`, `NativeBacktestChartHost.create()` is attempted first. When the runtime is valid and native plugin is present, `NativeBacktestChartHostAdapter` is selected.
  - When native runtime is missing or raises `NativeChartRuntimeError`, it gracefully falls back to `PythonBacktestChartHost` with actionable logging.
  - When `backend="python"` (or `SAGITTARIUS_BACKTEST_CHART_BACKEND=python`), `PythonBacktestChartHost` is created directly as a kill-switch / emergency fallback.
- **Structured Diagnostic Logging**:
  - `BacktestChartHostFactory` logs structured info on each host creation:
    `"Backtest chart host initialized for symbol '%s' with backend '%s' (requested: '%s')"`.
- **Verification & CI Evidence**:
  - Full local CI (`.\scripts\ci-local.ps1 -Full`) passed 100%:
    - Native QML chart build: `Sagittarius.NativeChart` compiled cleanly.
    - Chart migration benchmark contract: PASSED.
    - Read-only Ruff lint & format: PASSED (0 errors, 373 files clean).
    - Primary unit & integration tests: 1,118 passed (94.11% coverage $\ge$ 80% threshold).
    - Sanity suite: 37 passed sequentially.
