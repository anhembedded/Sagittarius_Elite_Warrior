# BOT-098F6E — Native default rollout and Python kill-switch

**Parent:** [`BOT-098F6`](BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F6D`  
**Priority:** P1  
**Complexity:** M  
**Status:** Backlog

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
