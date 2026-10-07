# BOT-168 — The realtime backtest runs on true Futures 1-second ticks built from Futures aggTrades

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** Build 1-second ticks for the realtime (historical-tick) backtest from Futures aggTrades (data.binance.vision `data/futures/um/daily/aggTrades/<SYMBOL>/`, or `fapi/v1/aggTrades`), because Futures has no 1s klines; unblocks `BUG-166` (a). Several GB a month for BTC. Documented only, no code.
**Source:** The owner, 2026-10-07, through the coordinating session (session_01PZn6EWxn6gytSGKwbuRJGg): build true Futures 1-second ticks for the realtime backtest from Futures aggTrades; Spot 1s is not an acceptable proxy.
**Risk:** 🟡 — a new data source and a new store shape; a wrong aggregation would feed the backtest ticks that look right and are not
**Complexity:** L — download or API ingest, a 1-second aggregation, storage, a sync path in Data mode, and a reader for the tick handler
**SPEC (optional):** None yet; the tick mode has no use case file
**Depends on:** None to start; `BUG-166` records why it is needed

---

## 1. Context and problem
The realtime backtest ("On every tick of the historical bar", `RunHistoricalTickBacktestCommandHandler`, `src/modules/backtesting/application/run_historical_tick_backtest/handler.py`) reads stored 1s klines for the backtest's market. The backtest's default market is Futures USD-M (`broker_simulation_config.py:86`), and Binance USD-M Futures serves no 1s klines: `fapi/v1/klines?interval=1s` answers `-1120 Invalid interval`, and data.binance.vision has `1s/` under `data/spot/daily/klines/BTCUSDT/` but not under `data/futures/um/daily/klines/BTCUSDT/` (verified 2026-10-07). On Futures the mode therefore always fails with "No 1s tick data found … Please run sync first." (`BUG-166` (a)).

Spot 1s is not an acceptable proxy: the Spot and Futures prices differ by a basis that matters most near stops and liquidation prices, which are exactly what a Futures backtest exists to test.

Futures aggTrades exist at both places: data.binance.vision `data/futures/um/daily/aggTrades/<SYMBOL>/` (daily files) and the `fapi/v1/aggTrades` API. One-second ticks are built from them by aggregating trades into 1-second candles (open, high, low, close, volume; a second with no trades is kept with zero volume, as Spot's published 1s klines do).

## 2. Acceptance criteria
- [ ] For a Futures USD-M symbol and a date range, the app holds 1-second candles built from Futures aggTrades, complete (86,400 rows per day, empty seconds kept with zero volume), and the historical-tick backtest on Futures returns a `BacktestResult` from them.
- [ ] The Data mode can sync these ticks for Futures, with progress, resume after a gap and cancellation, as it does for Spot klines (`SPEC-001`).
- [ ] The Futures 1s data is stored and read as the Futures market's, never mixed with Spot's 1s series.
- [ ] The size is shown before the sync starts (see §3) and a sync can be bounded by date range.
- [ ] `BUG-166` (a) is closed: the mode's tooltip and failure text no longer send a Futures user to a sync that cannot work.

## 3. Design
Open questions to settle before implementing; the choice is the implementer's, with these facts:
- **Size.** Futures aggTrades are the full trade tape. For BTCUSDT that is several GB a month on disk once downloaded, far more than the 1s klines (86,400 rows a day) they reduce to. Aggregate while streaming each daily file and keep only the 1-second candles; do not store the raw trades.
- **Source.** data.binance.vision daily files for history (one download per day, no rate limit pressure); `fapi/v1/aggTrades` for the days not yet published and for the most recent hours (weighted by the API's rate limits).
- **Where it lives.** The existing kline store keyed by market and interval (`i_market_data_repository.py`) is the first candidate, so the handler's read does not change; the new part is the producer, and the `1s` Futures series is then the only exception to "Futures has no 1s" (`core/vo/market_timeframes.py`, from `BOT-167`). That rule must then distinguish *loadable from the exchange as klines* from *available as stored ticks*; decide this before reusing the same picker rule.
- **Correctness.** A 1-second candle from aggTrades must use the trade time bucket the exchange's own Spot 1s klines use (`floor(time_ms / 1000)`), and be checked against a Spot day built the same way from Spot aggTrades versus the published Spot 1s klines before it is trusted on Futures.

## 4. Changes, per file
Not decided; to be listed when the task starts.

## 5. Testing
To be defined when the task starts; at least: a unit test of the aggregation against a hand-built trade list (empty seconds, the second boundary, the high/low/close of one second), and an integration test of the handler over the real SQLite repository with Futures ticks present.
