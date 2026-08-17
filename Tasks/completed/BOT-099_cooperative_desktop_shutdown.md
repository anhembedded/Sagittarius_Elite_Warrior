# BOT-099 — Cooperative desktop shutdown with in-flight work

**Source:** [`BUG-007`](../bug_report/BUG-007.md)  
**Priority:** P1  
**Status:** Completed  
**Repositories:** Sagittarius Engine + Sagittarius Elite Warrior

## Scope

1. Add an idempotent PresenterManager/MainWindow shutdown lifecycle.
2. Cancel Backtest run/sync tokens before the Qt event loop and engine stop.
3. Extend the sync command/exchange port with a cooperative cancellation check.
4. Keep cancellation distinct from failure and prevent partial database writes.
5. Retain unit, integration and isolated process-exit regressions.

`wait=False` may remain non-blocking at the engine boundary, but completion is
only valid when cooperative tasks actually observe shutdown and terminate. A
log line alone is not evidence of process exit.

## Verification

- The isolated desktop child-process regression exits within its deadline while
  deterministic sync work is in flight.
- Sagittarius Engine: 449 passed, 8 skipped.
- Sagittarius Elite Warrior full CI: native CMake, Ruff, 1,018 primary tests
  and 28 sanity tests passed.
