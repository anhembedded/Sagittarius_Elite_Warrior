---
description: Where a log line goes so one reproduce-and-send cycle locates a root cause; namespace, levels, tags, dev/debug modes.
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
---

# Logging

The measure is not volume: one reproduce-and-send-log cycle must locate a root cause (`BUG-009` lost three).

1. **Every logger is `logging.getLogger("App.<Component>")`.** A `__name__` logger has no handler: `info()`/`debug()` emit nothing, WARNING+ falls to Python's unformatted last resort. Only exemption: `getLogger(name)` to add/remove a handler on someone else's logger. `[guard: tests/unit/test_logging_namespace_guard.py]`
2. **Log the decision, not just the outcome.** Which backend/adapter/host was chosen, what was requested, why they differ, which optional mechanism is engaged — including the *disabled* case. What is in effect, not what was configured. `[review: I3]`
3. **One-shot environment line at construction** for any UI/rendering component: real backend, fallback reason, DPR, platform, geometry (`ChartCard._log_environment`, `[chart-env]`). `[review: I3]`
4. **Per gesture or operation, never per event.** One line at start (geometry, thresholds), one per significant transition, one summary with counts, worst case, final state — pixels as well as percentages. `[review: I2]`
5. **Log what lets a layer be ruled out**: asked, applied, pending — a coalesced update not yet applied must say so.
6. **Six levels:** `TRACE(5) < DEBUG < INFO < WARNING < ERROR < CRITICAL`. TRACE: per-frame/per-tick, only under `--debug`. DEBUG: per-event detail safe for a whole `--dev` run. INFO: decisions, environment, per-operation summaries. WARNING: degraded but recovered. ERROR: an operation failed, process sound. CRITICAL: the process is compromised. **Never INFO in a hot loop** (per trade/candle/tick/frame): `SignalLogHandler` pushes every `App.*` record through the UI thread — `BUG-042` froze the app with 5 028 lines in 2 s. `[review: I2, I4]`
7. **`--dev`** sets `DEBUG` and writes `logs/dev-<ts>.log`; **`--debug`** implies `--dev` and sets `TRACE` (`logs/debug-<ts>.log`). Never require a config edit for diagnostics; ask for the log **file**, never scrollback.
8. **Stable greppable tag first** (`[chart-env]`, `[chart-data]`, `BACKTEST_TRACE action=`). The formatter is fixed-field `%(asctime)s - %(name)s - %(levelname)s - %(message)s` so a file filters by level (`grep -E '\- (WARNING|ERROR|CRITICAL) \-'`) and by tag; do not change the field order or separator (the gate's log scan and documented filters depend on it). `[gate: run-log scan]`
9. **A diagnostic never seen to emit does not exist.** After adding logging, run the path through the **real** logging configuration (never `logging.basicConfig` in a scratch script) and see the lines. `[review: I5]`
