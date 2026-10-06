# BUG-159 — Market mode: choosing 1s when no 1s data exists shows no error or warning

- **Reported:** 2026-10-06 (the user, in chat, with one screenshot)
- **Severity:** 🟡 P2 — the chart does not show the chosen timeframe and nothing tells the user, so the candles can be read as 1s when they are not
- **Status:** Open
- **Board:** Market mode: with 1s chosen and no 1s data available, the chart shows other candles and no error or warning appears. Not investigated yet.
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
Not yet established. The user asked for the report only; no investigation was done.

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Record whether the chart's candles are the previously chosen timeframe, and the app and engine commits.
- Then follow `fix-bug-rule.md`.
