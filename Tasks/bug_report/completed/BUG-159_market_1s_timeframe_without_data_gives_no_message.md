# BUG-159 — Market mode: choosing 1s when no 1s data exists shows no error or warning

- **Reported:** 2026-10-06 (the user, in chat, with one screenshot)
- **Severity:** 🟡 P2 — the chart does not show the chosen timeframe and nothing tells the user, so the candles can be read as 1s when they are not
- **Status:** ✅ Fixed (2026-10-06)
- **Board:** Root cause: `LiveChartCoordinator._load_history` returned without drawing when a timeframe had no stored candles, and a sync the exchange refuses (Futures has no 1s: `APIError -1120`) raised before any history was loaded, so the chart kept the previous timeframe's candles under the new label and the Output line named no timeframe. Fixed at that one coordinator, shared by the Market, Desk and Bot charts: an empty or failed load draws an empty window and logs a line naming the symbol and timeframe.
- **Context:** View market data (choose a timeframe) → `src/modules/market_data/` → live chart timeframe bar, `ui/` layer
- **Environment:** Windows (the user's desktop). App commit, engine commit and Python version not captured. Market mode, Futures market, BTCUSDT, trading off; the Output log reads "Loading BTCUSDT data from the local database (not connected live — enable trading to connect)."

## Reproduction
1. Start the app with trading off; open the Market mode on Futures, BTCUSDT.
2. On the chart's timeframe bar choose 1s.

**Expected (the user's words, translated):** when that timeframe does not exist, an error or a warning says so.
**Actual:** 1s shows as chosen; the chart keeps showing candles whose time axis steps by 5 minutes (13:20, 13:25, …); the Output panel shows no message about the timeframe.

**Frequency:** Not yet established (one occurrence reported). Not yet reproduced here.

## Symptom
- The user's words: "chọn 1s, nhưng nếu k có khung đó, vẫn k có báo erro hay wanring gì."
- Screenshot, 1s chosen and outlined by the user: [`BUG-159_1s_selected.webp`](BUG-159_1s_selected.webp).
- The app log of the same run (pasted later, in [BUG-160](BUG-160_run_backtest_leaves_no_backtest_in_the_log.md)) shows each 1s sync failing on the exchange: `App.ExchangeClient - ERROR - Failed to stream historical klines for BTCUSDT: APIError(code=-1120): Invalid interval.` then `App - ERROR - SyncMarketDataCommand failed: …`. The error is in the log only.
- Output panel as shown: "[22:48:21] Live for BTCUSDT, ETHUSDT, BNBUSDT." and "[22:48:22] Loading BTCUSDT data from the local database (not connected live — enable trading to connect)."

## Root cause
`src/support/charting/live_chart/live_chart_coordinator.py` `_load_history`: when the store held no candles at the chosen interval it logged "No historical data for BTCUSDT." and returned without telling the chart, so `ChartCard` kept drawing the previous timeframe's candles (the 5-minute axis in the screenshot) under a toolbar already on 1s. The go-live path was worse: `_run` let a sync the exchange refuses (Binance Futures has no 1s klines, `APIError(code=-1120): Invalid interval.`, BUG-160's log) raise before `_load_history`, so nothing was drawn at all. `LiveCandleChart._on_history` was not at fault: it draws whatever the coordinator reports.

## Fix
- `live_chart_coordinator.py`: an empty history reports an empty first window (`history_ready(symbol, [], [], [])`) and logs "No historical data for {symbol} at {interval}: the chart shows no candles."; a failed sync is reported as `Could not sync {symbol} at {interval}: {error}` and the stored candles are still loaded (and drawn empty if there are none). One mechanism for the Market, Desk and Bot charts.
- `chart_card.py` `_set_initial_view_range`: an empty draw leaves the axis alone instead of auto-ranging over nothing.

## Regression test
- `tests/unit/modules/trading/ui/market/test_market_chart_empty_timeframe.py` (the Market presenter on real fakes): switching to a timeframe with nothing stored clears the drawn candles and names the timeframe in the log. Red before the fix on the stale `_raw_history` and the unnamed message.
- `tests/unit/support/charting/live_chart/test_live_chart_coordinator.py::test_a_refused_sync_is_named_and_the_stored_candles_still_draw`: red before the fix, the sync's exception skipped the history.

## Verification
Both new tests red before, green after; `tests/unit/support` and `tests/unit/modules` green (5893 passed); ruff, ruff format, mypy and `tests/unit/architecture` green (the god-file baseline for `chart_card.py` shrank 768 → 767). Not run on a real desktop with Binance.

## Open point for the owner
Futures never offers 1s klines, so on a Futures chart 1s can only ever be empty. Recommendation: hide 1s from the Futures timeframe bar (a market capability, a separate change); until then the chart now says so instead of looking selected and silent.
