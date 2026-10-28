# BUG-277 — A backtest data sync asks the USDⓈ-M Futures market for 1s candles, which it does not have, and fails with a message box

- **Reported:** 2026-10-28 (the owner, desktop log pasted in chat; filed as a record only, no fix requested yet)
- **Severity:** 🟢 P3 — the backtest screen cannot fill the missing candles of a 1s Futures series and opens an error box on the sync it starts itself; no order, position or money is touched.
- **Status:** Open
- **Board:** Opening the Backtest mode on a 1s Futures series starts a sync of the coverage gap, and Binance refuses the interval for USDⓈ-M Futures (code -1120), so the sync fails with a message box instead of the screen not offering or not syncing 1s there.
- **Context:** Use case run a backtest → `backtesting` (`ui/coordinators/data_sync_coordinator.py` → `run_sync`, `BackTestPresenter`) → `market_data` (`application/sync/sync_market_data/handler.py`, `adapters/binance/client.py` → `stream_historical_klines`, `kline_refusal.py` → `reraise_as_refusal`)
- **Environment:** the owner's Windows desktop, app at an unknown commit of 2026-10-28 (not captured), data source `mainnet_public`; the symbol is ETHUSDT, the interval 1s.

## Reproduction
Observed once; not reproduced here. Order of events in the log: the Backtest mode is shown; the presenter resolves the sync start from a coverage gap (`source=coverage_gap`, gap and requested start both 2026-10-06 01:52 UTC); `SyncMarketDataCommand` starts for `ETHUSDT` at `1s` from `mainnet_public`; the client streams historical klines 06 Oct 01:52 → 09 Oct 01:52; Binance answers `APIError(code=-1120): Invalid interval`; the failure is shown in a message box. Not yet established: which market the screen had selected (the error text says USDⓈ-M Futures), whether the owner chose 1s or the screen defaulted to it, and whether Spot syncs 1s without trouble.

## Symptom
```
App.SyncMarketData - Starting sync for symbols: ['ETHUSDT'] at interval 1s from mainnet_public
App.ExchangeClient - Streaming historical klines for ETHUSDT at 1s from 06 Oct 2026 01:52:00 to 09 Oct 2026 01:52:01
App.ExchangeClient - ERROR - Failed to stream historical klines for ETHUSDT: This exchange has no 1s candles for its USDⓈ-M Futures market.
App - ERROR - SyncMarketDataCommand failed: This exchange has no 1s candles for its USDⓈ-M Futures market.
App.BackTestPresenter - ERROR - Market data sync failed
binance.exceptions.BinanceAPIException: APIError(code=-1120): Invalid interval.
App.Shell.Notifier - WARNING - Command failed, shown in a message box: backtesting.sync [notice-command]
```
The traceback runs `data_sync_coordinator.py` `run_sync` → `_ask_for_the_sync` → `market_data_sync_service.py` `sync` → the handler → `client.py` `_generate_raw_klines_with_retry` → `kline_refusal.py` `reraise_as_refusal` → `ExchangeRefusedKlinesError`. Expected: the screen does not offer or start a sync the venue cannot serve, or says so before asking the exchange.

## Root cause
Not yet established. What the log shows: the exchange's refusal is already translated into the typed `ExchangeRefusedKlinesError` with the right sentence (`kline_refusal.py`), so the translation works; the gap is upstream, where the screen resolves a sync start from a coverage gap and starts the sync for an interval and market the venue does not serve. Suspected, not verified: the series list or the timeframe picker offers 1s for a Futures market, and the screen starts the gap sync on opening the mode without asking whether the venue serves that interval.

## Fix
Pending.

## Regression test
Pending: a Futures series at 1s must not start a sync (or must say before asking the exchange that the venue has no such candles); a Spot 1s series is unchanged.

## Verification
Not run.

## Suggested next steps
Read where the backtest screen builds its timeframe and venue choices and where it starts the coverage-gap sync (`BackTestPresenter`, `data_sync_coordinator.py`); ask the owner which market and timeframe were selected. Related, not duplicates: [BOT-073](../../backlog/BOT-073_realtime_tick_backtest_epic.md) (a 1s feed for realtime backtests) and the backtest timeframe list the owner asked to be complete.
