# BUG-161 — Backtest mode: the backtest does not run

- **Reported:** 2026-10-06 (the user, in chat, with the Backtest Output log pasted)
- **Severity:** 🟡 P2 — no backtest result can be produced
- **Status:** Open
- **Board:** Backtest mode: the backtest does not run; the Backtest Output log shows no run starting, only `preview_ignored` lines for a tick-mode range. Not investigated yet.
- **Context:** Run a backtest → `src/modules/backtesting/` → Backtest mode, `ui/` and `application/` layers
- **Environment:** Windows (the user's desktop). App commit, engine commit and Python version not captured. Backtest mode, BTCUSDT, Ema Crossover (fast 12, slow 26), 30m then 15m, range Custom then All. Same run as [BUG-158](BUG-158_backtest_equity_curve_and_side_by_side_do_not_change_the_chart.md) and [BUG-160](BUG-160_run_backtest_leaves_no_backtest_in_the_log.md).

## Reproduction
1. Open the Backtest mode; BTCUSDT, Ema Crossover.
2. Change the timeframe to 15m and the range to All; save the strategy parameters.
3. Run the backtest. How it was started (Run backtest on the toolbar, F7, Tools menu) was not recorded.

**Expected:** a backtest runs and its trades, metrics and equity curve appear.
**Actual (the user's words, translated):** "the backtest does not run."

**Frequency:** Not yet established. Not yet reproduced here.

## Symptom
What the pasted Output log (channel Backtest) shows, read as written — observations, not a cause:

1. No line reports a backtest starting, running, failing or finishing.
2. `preview_ignored` three times, with reasons `tick_mode_range_too_wide` (twice) and `tick_mode_unbounded_range` (after choosing range All). Which "tick mode" this is, and whether it is what blocks the run, is not established.
3. Range All reads `2026-09-04 13:47 -> 2026-10-04 13:47`: it ends two days before the report date.
4. `chart_mode_changed` is logged for equity, both and ohlc at 22:50:55–22:51:05 while the chart did not change ([BUG-158](BUG-158_backtest_equity_curve_and_side_by_side_do_not_change_the_chart.md)).

The log as pasted:

```text
[22:48:02] Changed symbol to BTCUSDT.
[22:48:02] Changed timeframe: 30m
[22:48:02] Selected time range: custom
[22:48:02] Updated reference indicators: None
[22:48:02] [Health] System status: HEALTHY (Container: OK, Event_bus: OK, Database: OK)
[22:50:55] [DEV] chart_mode_changed mode='equity'
[22:50:55] [DEV] chart_mode_changed mode='both'
[22:50:56] [DEV] chart_mode_changed mode='equity'
[22:50:56] [DEV] chart_mode_changed mode='ohlc'
[22:50:57] [DEV] chart_mode_changed mode='equity'
[22:50:58] [DEV] chart_mode_changed mode='both'
[22:50:59] [DEV] chart_mode_changed mode='equity'
[22:50:59] [DEV] chart_mode_changed mode='ohlc'
[22:51:04] [DEV] chart_mode_changed mode='equity'
[22:51:05] [DEV] chart_mode_changed mode='ohlc'
[22:51:05] [DEV] chart_mode_changed mode='equity'
[22:53:38] [DEV] preview_ignored reason='tick_mode_range_too_wide'
[22:53:42] Changed timeframe: 15m
[22:53:42] [DEV] preview_ignored reason='tick_mode_range_too_wide'
[22:53:46] Selected time range: all (2026-09-04 13:47 -> 2026-10-04 13:47)
[22:53:46] [DEV] preview_ignored reason='tick_mode_unbounded_range'
[22:56:37] Saved strategy parameters (Ema Crossover): fast_period=12, slow_period=26
[22:56:44] [DEV] chart_mode_changed mode='ohlc'
```

## Root cause
Not yet established. The log was read for what it shows; the code was not investigated.

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Ask the user how the run was started and for the app log file (not the Output panel) from that moment; check the Execution… settings for a tick mode.
- Then follow `fix-bug-rule.md`.
