# BUG-184 — `test_older_candles_come_from_the_store_when_it_has_them` times out when the machine is busy

- **Reported:** 2026-10-07 (gating PR #426: one timeout under `-n 4`, passes alone)
- **Severity:** 🟢 P3 — a flaky gate; the chart behaves as designed
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** The backfill integration tests timed out now and then under load. Cause: they waited for the first window to be drawn, then panned; the window settles on its own queued signal after that, a pan before it is dropped by design, and nothing pans again. Fix: the tests wait until the backfill has a window to ask about, which is the settle.
- **Context:** [SPEC-002](../../Docs/SPEC/SPEC-002_watch_the_live_market.md) → Charting (`src/support/charting/live_chart/`) → `tests/integration/modules/market_data/`
- **Environment:** Linux container, 4 cores, engine `f4ef582`; CI under `-n 4`.

## Reproduction
Frequency: 3 of 25 single runs with six busy-loop processes on 4 cores; never on an idle machine. A temporary diagnostic in the failing branch printed `pending_at_pan True pending_now False` in each of 5 failures out of 30 runs: the pan met a chart whose first window was drawn but not yet settled, and a moment later it had settled.

## Symptom
`qtbot.waitUntil(lambda: len(card._raw_history) == 1000, timeout=10_000)` times out; the chart keeps its 500 candles and the store is never asked.

## Root cause
`LiveCandleChart._backfill_window` (`live_candle_chart.py`) answers `None` while `_pending` is set, so `OlderCandlesBackfill._on_near_left_edge` ignores the pan: "a first window is on its way and about to replace what is drawn". `_pending` is cleared by `_on_load_settled`, which the worker's `load_finished` reaches as its own queued signal *after* the history's. The test helper `_chart` returned as soon as `len(card._raw_history) == 500` was true, then panned once. The drop is the designed behaviour (a user keeps dragging; a test pans once); the wait was on the wrong condition. All four pan-and-wait tests of the file shared the helper, so the same exposure applied to each.

## Fix
`tests/integration/modules/market_data/test_chart_backfills_older_candles.py`: `_chart` waits for `chart._backfill_window() is not None`, the very answer the backfill asks before a pan, before it returns. No production change: the drop is by design, and a public read of it would have pushed `live_candle_chart.py` over the 400-line ceiling for a test's sake.

## Regression test
`test_a_pan_before_the_first_window_settles_asks_for_nothing_until_it_has`: it holds the settle signal, so "drawn, not settled" is deterministic instead of a race. It pans (dropped, nothing asked, no loading; the window is `None`), releases the settle, pans again (the older candles are drawn from the store). The timing flake itself was red under CPU load (3/25, then 5/30 with the diagnostic) and is 0/40 over the whole file after the fix with the same load. The pin passes before and after the helper change; it records the mechanism the helper's wait relies on.

## Verification
`pytest tests/integration/modules/market_data/test_chart_backfills_older_candles.py`: 8 passed; 0 failures in 40 runs of the file under six busy loops. Commit tier PASS; `src/` untouched.
