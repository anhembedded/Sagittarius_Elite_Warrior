# BUG-166 — The historical-tick backtest mode cannot run on Futures, and its Execution dialog misleads

- **Reported:** 2026-10-07 (the owner's request to the coordinating session; filed by the session that holds the reserved id; report only, no fix)
- **Severity:** 🟡 P2 — a mode the Backtest screen offers always fails on its default market, and every text on the way tells the user to do something that cannot work; no wrong figure is produced
- **Status:** Open
- **Board:** On Futures, the Backtest's "On every tick of the historical bar" always fails with "No 1s tick data found … Please run sync first", and a sync of 1s Futures data cannot succeed (Binance has no Futures 1s klines); the Execution dialog's tooltip points to that sync, shows a locked "real-time bar" box inside a backtest, and lets "On order fill" be ticked where it does nothing.
- **Context:** The Backtest mode's historical-tick run (no SPEC file for it yet) → Module `src/modules/backtesting/` → `ui/backtest_modals/` (Execution dialog) and `application/run_historical_tick_backtest/` (handler)
- **Environment:** Linux, master-warrior at `fa4477d`; Binance public endpoints probed 2026-10-07 by the coordinating session; Backtest default market Futures USD-M (`broker_simulation_config.py:86`).

## Reproduction
Not run through the GUI by this session; the handler was driven by the coordinating session over the real SQLite repository (see Symptom).
1. Backtest mode, market Futures (the default). Execution… → "On every tick of the historical bar".
2. Run the backtest.
3. Expected: a result, or a message that says what can be done. Actual: the run fails with the text below; the "run sync first" advice cannot be followed (Data mode's sync is Spot-only, and Futures has no 1s klines to sync).

## Symptom
Established by the coordinating session on 2026-10-07:

**Binance USD-M Futures has no 1-second klines.**
- `fapi/v1/klines?interval=1s` answers `{"code":-1120,"msg":"Invalid interval."}`; the same call with `1m` returns candles.
- python-binance `futures_klines(interval="1s")` raises `BinanceAPIException APIError(code=-1120)`.
- data.binance.vision lists `1s/` under `data/spot/daily/klines/BTCUSDT/` but not under `data/futures/um/daily/klines/BTCUSDT/`.
- Spot 1s klines are complete: 86,400 rows per day for BTC, DOGE and TRX on 2026-10-01; seconds with no trades are kept with zero volume.

**The mode needs stored 1s klines.** `RunHistoricalTickBacktestCommandHandler` (`src/modules/backtesting/application/run_historical_tick_backtest/handler.py`) reads stored `tick_resolution` klines (default 1s) for `command.market`. The real handler over the real SQLite repository:
- Spot holding 1s klines gives a `BacktestResult`.
- Futures holding only 1m klines gives `None` plus `BacktestFailedEvent("No 1s tick data found for BTCUSDT. Please run sync first.")` (`handler.py:129-130`).

Four defects:
- **(a) On Futures the mode always fails.** The Execution dialog's tooltip `_HISTORICAL_TICK_TIP` (`src/modules/backtesting/ui/backtest_modals/order_execution_dialog.py:41`) says "a separate sync of 1-second data will be required", and the failure text says "Please run sync first". Both send the user to a sync that can never succeed on Futures.
- **(b) "On every tick of the real-time bar" is shown checked and disabled** inside a backtest dialog (`order_execution_dialog.py`, `realtime_tick`). It reads as if the backtest used real-time ticks; its tooltip says "Live trading only: a backtest has no real-time bar".
- **(c) "On order fill" can be ticked in bar-close mode**, where it has no effect; its own tooltip (`_ORDER_FILL_TIP`) says it "Only takes effect in Historical Tick mode".
- **(d) Inherent limits, to document, not code defects:**
  - fills happen at the tick's own close with no latency;
  - the strategy is re-evaluated each second, while the live kline stream updates faster;
  - the order of the high and the low inside one second is unknown.

## Root cause
Not yet established for (a)–(c) as a design question; the mechanism is known. (a): the mode's data source is stored 1s klines, and the exchange publishes none for Futures; nothing in the screen ties the mode to a market that has them. (b), (c): the dialog shows live-trading facts and a mode-dependent flag without regard to the selected mode. No fix is designed here; (a)'s real fix is `BOT-168` (true Futures 1-second ticks from aggTrades), or a decision to disable the mode on Futures with a message that says why.

## Fix
Pending. `BOT-167` removes `1s` from every timeframe picker while the market is Futures (and from the Data mode's sync list), so nobody is offered a Futures 1s timeframe or can start a Futures 1s sync. It does not by itself fix (a)–(c): the tick mode's tooltip and failure text still send a Futures user to a sync that cannot work, the real-time box is still shown, and "On order fill" is still tickable in bar-close mode.

## Regression test
Pending.

## Verification
Not run.

## Suggested next steps
1. Decide (a): disable the mode on Futures with a message naming the reason, until `BOT-168` provides Futures ticks; correct the tooltip and the failure text to say what is actually missing per market.
2. (b): drop the locked real-time row from the dialog, or move its sentence to the tooltip of the mode.
3. (c): disable "On order fill" while "On bar close" is chosen, with the reason as its tooltip.
4. (d): state the three limits in the mode's documentation (`Docs/SPEC/`) and its tooltip.
