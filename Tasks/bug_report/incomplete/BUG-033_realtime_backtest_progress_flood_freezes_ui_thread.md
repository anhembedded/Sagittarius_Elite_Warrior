# BUG-033 — Realtime (tick-level) Backtest floods the UI thread with progress signals, freezing it for 5+ seconds

**Reported:** 2026-08-23, user-pasted real application log from a completed Realtime Backtest
run (BTCUSDT, `HISTORICAL_TICK` execution mode).
**Severity:** 🟡 P2 — does not corrupt data or crash the app (the watchdog itself confirms
recovery: "UI Thread recovered from freeze. Event loop responsive."), but the entire UI is
genuinely unresponsive to input for 5+ seconds on every large tick-range Realtime Backtest run.
**Status:** 🔴 **Open — root cause narrowed via log-timestamp cross-reference + code trace
(2026-08-23), not yet reproduced live with debug instrumentation or fixed.**

## Symptom

Real log evidence, user-pasted, from a single Realtime Backtest run for `BTCUSDT`:

```text
2026-08-22 23:07:27,036 - App.RunRealtimeBacktest - INFO - REALTIME_BACKTEST_TRACE action=handler_simulation_complete ticks=2592000 bars_committed=43201
2026-08-22 23:07:27,090 - App.RunRealtimeBacktest - INFO - REALTIME_BACKTEST_TRACE action=handler_complete trades=787 net_profit_percent=-2.135061811927917
2026-08-22 23:07:27,090 - App.RunRealtimeBacktest - INFO - Realtime backtest complete for BTCUSDT: 787 trades, net profit -2.14%
2026-08-22 23:07:27,551 - App - WARNING - 🚨 UI FREEZE DETECTED: Qt Main Thread unresponsive for 5.2s (Threshold: 5.0s).
Current Main Thread Stack Trace:
  File "/home/hoanganh/Documents/Claude/Sagittarius_Elite_Warrior/src/presentation/ui/main_window.py", line 170, in <module>
    main()
  File "/home/hoanganh/Documents/Claude/Sagittarius_Elite_Warrior/src/presentation/ui/app_bootstrapper.py", line 137, in main
    exit_code = app.exec()
  File "/home/hoanganh/Documents/Claude/Sagittarius_Elite_Warrior/.venv/lib/python3.14/site-packages/sagittarius_engine/extensions/pyside_mvc/thread_bridge.py", line 33, in wrapper
    return func(*args, **kwargs)
  File "/home/hoanganh/Documents/Claude/Sagittarius_Elite_Warrior/src/presentation/ui/screens/backtest/backtest_presenter.py", line 1155, in _on_backtest_progress_for_action
    self._view_model.set_backtest_progress(
  File "/home/hoanganh/Documents/Claude/Sagittarius_Elite_Warrior/src/presentation/ui/screens/backtest/backtest_view_model.py", line 911, in set_backtest_progress
    self._backtest_progress_percent = percent

2026-08-22 23:07:28,470 - App - INFO - UI Thread recovered from freeze. Event loop responsive.
```

The stack trace is captured live by `UIWatchdog` (see Root cause) at the moment its own
background monitor thread notices the main thread hasn't produced a heartbeat in >5s — it is
real, not a guess at where the code "probably" is stuck.

## Root cause — narrowed, not yet live-instrumented

**The chain, traced from the real files, not assumed:**

1. [`run_realtime_backtest/handler.py:302-307`](../../../src/application/use_cases/backtest/run_realtime_backtest/handler.py) throttles `command.progress_callback` by **tick index**, not wall-clock time: `index == 1 or index % 256 == 0 or index == total_ticks`. For this run's `ticks=2592000`, that is **exactly 10,125** callback invocations over the run (`2592000 / 256`).
2. Each invocation is the closure at [`backtest_presenter.py:2263-2268`](../../../src/presentation/ui/screens/backtest/backtest_presenter.py), which does `self._backtestProgressSignal.emit(...)` — a cross-thread Qt signal from the background worker thread (`_run_backtest` runs via `IThreadManager`, confirmed by its own docstring: "Background method — submitted to IThreadManager... Signals only") to the main GUI thread.
3. The main-thread slot, [`_on_backtest_progress_for_action` (line 1126-1157)](../../../src/presentation/ui/screens/backtest/backtest_presenter.py), calls `self._view_model.set_backtest_progress(percent, text)`.
4. [`backtest_view_model.py:909-913`](../../../src/presentation/ui/screens/backtest/backtest_view_model.py) `set_backtest_progress` writes two `Property` values and emits `backtestProgressChanged` — triggering every QML binding on `backtestProgressPercent`/`backtestProgressText` to re-evaluate.
5. `BackTestTopPanel.qml`'s `progressBanner` binds an `AppProgressBar` to those properties. [`AppProgressBar.qml:98-100`](../../../src/presentation/ui/components/AppProgressBar.qml) has `Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }` on the fill bar — **every single progress update retriggers a new animation** on the main/GUI thread, not just a cheap value assignment.
6. [`UIWatchdog`](../../../../Sagittarius_Engine/sagittarius_engine/extensions/pyside_mvc/safety/ui_watchdog.py) fires only when its 1-second `QTimer` heartbeat (also on the main thread) hasn't ticked in over 5 seconds — confirming the main thread's event loop was **continuously busy**, not merely slow to respond to a specific input.

**Timestamp cross-reference from the log itself (real evidence, not inference from code alone):**
the tick loop's own `handler_simulation_complete` trace fires at `23:07:27,036`; the freeze
warning (reporting `elapsed=5.2s`, i.e. onset ≈ `23:07:22.35`) fires at `23:07:27,551`; recovery
is logged at `23:07:28,470` — **roughly 1.4s *after* the background computation itself had
already finished**, the main thread was still saturated draining its backlog of queued
progress-signal deliveries. This is the expected signature of a producer (background thread,
~10,125 emits) outrunning the consumer (main thread, each emit costing a Property write + QML
notify + `Behavior` animation retrigger) badly enough that draining continues well past the
producer stopping.

**Not yet done, and why this is "narrowed" rather than "confirmed":** no live reproduction with
temporary timing instrumentation (e.g. per-emit `perf_counter()` deltas logged on both sides)
has been run to directly measure the per-emit cost and confirm it — as opposed to some other
main-thread stall — actually accounts for the full 5.2s. The timestamp cross-reference above is
strong circumstantial evidence, not a proof.

**Related but not confirmed the same bug:** the static-backtest path
([`run_static_backtest/handler.py:279-281`](../../../src/application/use_cases/backtest/run_static_backtest/handler.py))
throttles by `index % 16` instead of `% 256` — a lower per-bar rate, but static backtests can
still process very large bar counts. This report only has direct evidence for the Realtime/tick
path; the static path is flagged here as sharing the same *class* of risk, not asserted to have
actually frozen anyone's UI.

## Suggested next steps (not yet attempted)

1. Reproduce live with temporary instrumentation: log `perf_counter()` on both the emit side
   (`progress_callback`) and the receive side (`_on_backtest_progress_for_action`) for a subset
   of calls, to directly measure emit rate vs. drain rate and confirm the backlog theory instead
   of inferring it from timestamps alone.
2. If confirmed, throttle `progress_callback` by **wall-clock time** (e.g. "at most once per
   ~100-150ms of real time", always still firing on `index == 1`/`index == total` so the bar
   never gets visually stuck at 0% or fails to reach 100%) instead of by tick/bar index — bounds
   the absolute emission rate regardless of how many ticks/bars a given run processes. Natural
   shared location: both `run_static_backtest/handler.py` and `run_realtime_backtest/handler.py`
   currently duplicate the same index-based throttle condition; a shared, wall-clock-based
   helper would fix both instead of patching one and leaving the other's same-shaped risk.
3. Separately worth checking (lower priority, only if step 1-2 doesn't fully explain the 5.2s):
   whether `AppProgressBar`'s `Behavior on width` should be suppressed above some update
   frequency, independent of the emission-rate fix — 10,000+ animation retriggers is wasted work
   even after throttling reduces the count, if the throttle still allows a burst faster than
   ~5/sec.
