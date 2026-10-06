# BUG-160 — Run backtest shows no run, and the log holds no backtest; the Market chart flips between 1s and 1m

- **Reported:** 2026-10-06 (the user, in chat, with the app log pasted)
- **Severity:** 🟡 P2 — the user cannot tell whether a backtest ran; none appears in the log
- **Status:** ✅ Closed (2026-10-06)
- **Board:** Not a defect for the missing backtest: Run was never triggered (the owner could not see F7 / Run); the one real defect in the log was a WARNING for an unheld stream stop (`StopLiveStreamCommandHandler`), now INFO; the 1s sync failure is BUG-159. The 1s/1m flip was the user's clicks.
- **Context:** Run a backtest (Backtest mode, Run backtest) → `src/modules/backtesting/` and `src/modules/market_data/` → `ui/` and `application/` layers
- **Environment:** Windows (the user's desktop). App commit, engine commit and Python version not captured. Futures USD-M, BTCUSDT, trading off (live ticks from the stream). Same run as [BUG-159](BUG-159_market_1s_timeframe_without_data_gives_no_message.md).

## Reproduction
1. Choose 1s on the Market chart ([BUG-159](BUG-159_market_1s_timeframe_without_data_gives_no_message.md)).
2. Start a backtest. The exact steps between the two were not recorded.

**Expected:** a backtest runs and its run shows in the app and in the log.
**Actual (the user's words, translated):** "I don't see the backtest run." The log excerpt below holds no backtest command.

**Frequency:** Not yet established (one occurrence reported). Not yet reproduced here.

## Symptom
What the pasted log shows, read as written — observations, not a cause:

1. **No backtest command.** No `Run…Backtest` command is executed. The only lines naming a backtest are `App.QueryHandler - INFO - BACKTEST_TRACE action=read_complete symbol='BTCUSDT' rows=500`, each followed by `ChartCard(BTCUSDT): loaded 500 candles`: a chart read. The tag `BACKTEST_TRACE` is also the prefix in `src/modules/market_data/application/queries/get_historical_klines/handler.py:40`.
2. **1s fails on the exchange, and the user is not told.** Every 1s sync ends `App.ExchangeClient - ERROR - Failed to stream historical klines for BTCUSDT: APIError(code=-1120): Invalid interval.` and `App - ERROR - SyncMarketDataCommand failed: …`. Only the log carries it ([BUG-159](BUG-159_market_1s_timeframe_without_data_gives_no_message.md)).
3. **The chart flips between 1s and 1m about every half second.** 22:52:40.186 sync 1s (fails) → 22:52:41.267 sync 1m, stream at 1m → 22:52:41.666 sync 1s (fails) → 22:52:42.367 sync 1m, stream at 1m → 22:52:42.775 stop again. Whether these came from the user's clicks was not recorded.
4. **A warning after each failed 1s sync.** The next `StopLiveStreamCommand` logs `release_owner(market.BTCUSDT) requested but it held no subscription` and `App.LiveStreamUseCase - WARNING - Failed to stop live stream. It might not be running.`, yet the command then reports `completed successfully`.
5. **Ticks are processed by a strategy with trading off.** Every live tick is followed by `App.TradingStrategy - DEBUG - Processing futures_usd_m tick for …`.

The log as pasted:

```text
2026-10-06 22:52:40,186 - App - DEBUG - StopLiveStreamCommand completed successfully.
2026-10-06 22:52:40,186 - App - INFO - Executing command: SyncMarketDataCommand
2026-10-06 22:52:40,186 - App - DEBUG - Payload: symbols=['BTCUSDT'] interval=<TimeFrame.ONE_SECOND: '1s'> market=<MarketType.FUTURES_USD_M: 'futures_usd_m'> days_back_if_empty=30 start_time=None end_time=None cancellation_requested=<bound method CancellationToken.is_cancelled of <sagittarius_engine.runtime.tasks.cancellation_token.CancellationToken object at 0x00000247E5B91FE0>> correlation_id='70afc064f40e43e0a37157a61f96f446'
2026-10-06 22:52:40,186 - App.SyncMarketData - INFO - Starting sync for symbols: ['BTCUSDT'] at interval 1s
2026-10-06 22:52:40,188 - App.SyncMarketData - INFO - [BTCUSDT] No existing data found. Syncing from 30 days ago: 2026-09-06 15:52:40.188957+00:00
2026-10-06 22:52:40,189 - App.ExchangeClient - INFO - Streaming historical klines for BTCUSDT at 1s from 06 Sep 2026 15:52:40 to NOW
2026-10-06 22:52:40,296 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85947.9 | Vol: 212.348 | Closed: False
2026-10-06 22:52:40,297 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85947.9
2026-10-06 22:52:40,305 - App.ExchangeClient - ERROR - Failed to stream historical klines for BTCUSDT: APIError(code=-1120): Invalid interval.
2026-10-06 22:52:40,305 - App - ERROR - SyncMarketDataCommand failed: APIError(code=-1120): Invalid interval.
2026-10-06 22:52:40,499 - App.LiveStream - DEBUG - [Live Stream] ETHUSDT | Price: 2708.98 | Vol: 908.32 | Closed: False
2026-10-06 22:52:40,499 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for ETHUSDT at 2708.98
2026-10-06 22:52:40,559 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85947.9 | Vol: 213.67 | Closed: False
2026-10-06 22:52:40,559 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85947.9
2026-10-06 22:52:40,863 - App.LiveStream - DEBUG - [Live Stream] ETHUSDT | Price: 2708.98 | Vol: 911.161 | Closed: False
2026-10-06 22:52:40,863 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for ETHUSDT at 2708.98
2026-10-06 22:52:40,870 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85948.0 | Vol: 213.685 | Closed: False
2026-10-06 22:52:40,870 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85948.0
2026-10-06 22:52:41,145 - App.LiveStream - DEBUG - [Live Stream] ETHUSDT | Price: 2708.98 | Vol: 913.732 | Closed: False
2026-10-06 22:52:41,145 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for ETHUSDT at 2708.98
2026-10-06 22:52:41,164 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85947.9 | Vol: 213.732 | Closed: False
2026-10-06 22:52:41,165 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85947.9
2026-10-06 22:52:41,259 - App.LiveStream - DEBUG - [Live Stream] BNBUSDT | Price: 785.41 | Vol: 61.05 | Closed: False
2026-10-06 22:52:41,260 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BNBUSDT at 785.41
2026-10-06 22:52:41,266 - App - INFO - Executing command: StopLiveStreamCommand
2026-10-06 22:52:41,266 - App - DEBUG - Payload: owner='market.BTCUSDT'
2026-10-06 22:52:41,266 - App.LiveStreamUseCase - INFO - Executing StopLiveStreamCommand for owner=market.BTCUSDT
2026-10-06 22:52:41,266 - App.LiveStream - DEBUG - release_owner(market.BTCUSDT) requested but it held no subscription; nothing to do.
2026-10-06 22:52:41,266 - App.LiveStreamUseCase - WARNING - Failed to stop live stream. It might not be running.
2026-10-06 22:52:41,267 - App - DEBUG - StopLiveStreamCommand completed successfully.
2026-10-06 22:52:41,267 - App - INFO - Executing command: SyncMarketDataCommand
2026-10-06 22:52:41,267 - App - DEBUG - Payload: symbols=['BTCUSDT'] interval=<TimeFrame.ONE_MINUTE: '1m'> market=<MarketType.FUTURES_USD_M: 'futures_usd_m'> days_back_if_empty=30 start_time=None end_time=None cancellation_requested=<bound method CancellationToken.is_cancelled of <sagittarius_engine.runtime.tasks.cancellation_token.CancellationToken object at 0x00000247E5B79860>> correlation_id='32d714be4144408aa551d39768e4780e'
2026-10-06 22:52:41,267 - App.SyncMarketData - INFO - Starting sync for symbols: ['BTCUSDT'] at interval 1m
2026-10-06 22:52:41,269 - App.SyncMarketData - INFO - [BTCUSDT] Syncing from latest timestamp: 2026-10-06 15:50:00+00:00
2026-10-06 22:52:41,269 - App.ExchangeClient - INFO - Streaming historical klines for BTCUSDT at 1m from 06 Oct 2026 15:50:00 to NOW
2026-10-06 22:52:41,424 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85948.0 | Vol: 213.748 | Closed: False
2026-10-06 22:52:41,424 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85948.0
2026-10-06 22:52:41,501 - App.Database - DEBUG - Saved 1 klines for futures_usd_m/BTCUSDT to database in chunks of 5000.
2026-10-06 22:52:41,501 - App.SyncMarketData - DEBUG - [BTCUSDT] Persisted chunk of 1 klines (1 total so far) — streamed straight to DB, not held in RAM.
2026-10-06 22:52:41,502 - App.ExchangeClient - INFO - Successfully streamed 1 klines for BTCUSDT.
2026-10-06 22:52:41,502 - App.SyncMarketData - INFO - [BTCUSDT] Successfully synced 1 klines.
2026-10-06 22:52:41,502 - App - DEBUG - SyncMarketDataCommand completed successfully.
2026-10-06 22:52:41,510 - App.QueryHandler - INFO - BACKTEST_TRACE action=read_complete symbol='BTCUSDT' rows=500
2026-10-06 22:52:41,512 - App - INFO - Executing command: StartLiveStreamCommand
2026-10-06 22:52:41,513 - App - DEBUG - Payload: owner='market.BTCUSDT' market_type=<MarketType.FUTURES_USD_M: 'futures_usd_m'> symbols=['BTCUSDT'] interval=<TimeFrame.ONE_MINUTE: '1m'>
2026-10-06 22:52:41,513 - App.LiveStreamUseCase - INFO - Executing StartLiveStreamCommand for owner=market.BTCUSDT futures_usd_m ['BTCUSDT'] at 1m
2026-10-06 22:52:41,514 - App.LiveStreamUseCase - INFO - StartLiveStreamCommand executed successfully.
2026-10-06 22:52:41,514 - App.ChartCard - INFO - [chart-data] ChartCard(BTCUSDT): loaded 500 candles spanning [1791271920.0, 1791301860.0] | price [85253.0000, 86664.9000] | initial view x-range [1791292741.2, 1791302038.8] | y-range [85881.7880, 86691.9120] | autorange=[False, 1.0] | chart type=candlestick
2026-10-06 22:52:41,514 - App - DEBUG - StartLiveStreamCommand completed successfully.
2026-10-06 22:52:41,575 - App.LiveStream - DEBUG - [Live Stream] ETHUSDT | Price: 2708.98 | Vol: 919.052 | Closed: False
2026-10-06 22:52:41,575 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for ETHUSDT at 2708.98
2026-10-06 22:52:41,665 - App - INFO - Executing command: StopLiveStreamCommand
2026-10-06 22:52:41,665 - App - DEBUG - Payload: owner='market.BTCUSDT'
2026-10-06 22:52:41,666 - App.LiveStreamUseCase - INFO - Executing StopLiveStreamCommand for owner=market.BTCUSDT
2026-10-06 22:52:41,666 - App.LiveStreamUseCase - INFO - StopLiveStreamCommand executed successfully.
2026-10-06 22:52:41,666 - App - DEBUG - StopLiveStreamCommand completed successfully.
2026-10-06 22:52:41,666 - App - INFO - Executing command: SyncMarketDataCommand
2026-10-06 22:52:41,666 - App - DEBUG - Payload: symbols=['BTCUSDT'] interval=<TimeFrame.ONE_SECOND: '1s'> market=<MarketType.FUTURES_USD_M: 'futures_usd_m'> days_back_if_empty=30 start_time=None end_time=None cancellation_requested=<bound method CancellationToken.is_cancelled of <sagittarius_engine.runtime.tasks.cancellation_token.CancellationToken object at 0x00000247E54562B0>> correlation_id='14a65aae24b44f928a0d1c78991fc31c'
2026-10-06 22:52:41,667 - App.SyncMarketData - INFO - Starting sync for symbols: ['BTCUSDT'] at interval 1s
2026-10-06 22:52:41,669 - App.SyncMarketData - INFO - [BTCUSDT] No existing data found. Syncing from 30 days ago: 2026-09-06 15:52:41.669296+00:00
2026-10-06 22:52:41,669 - App.ExchangeClient - INFO - Streaming historical klines for BTCUSDT at 1s from 06 Sep 2026 15:52:41 to NOW
2026-10-06 22:52:41,717 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85947.9 | Vol: 213.757 | Closed: False
2026-10-06 22:52:41,717 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85947.9
2026-10-06 22:52:41,788 - App.ExchangeClient - ERROR - Failed to stream historical klines for BTCUSDT: APIError(code=-1120): Invalid interval.
2026-10-06 22:52:41,788 - App - ERROR - SyncMarketDataCommand failed: APIError(code=-1120): Invalid interval.
2026-10-06 22:52:41,829 - App.LiveStream - DEBUG - [Live Stream] ETHUSDT | Price: 2708.98 | Vol: 921.09 | Closed: False
2026-10-06 22:52:41,829 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for ETHUSDT at 2708.98
2026-10-06 22:52:42,016 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85947.9 | Vol: 214.565 | Closed: False
2026-10-06 22:52:42,016 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85947.9
2026-10-06 22:52:42,221 - App.LiveStream - DEBUG - [Live Stream] ETHUSDT | Price: 2708.99 | Vol: 923.09 | Closed: False
2026-10-06 22:52:42,221 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for ETHUSDT at 2708.99
2026-10-06 22:52:42,365 - App - INFO - Executing command: StopLiveStreamCommand
2026-10-06 22:52:42,366 - App - DEBUG - Payload: owner='market.BTCUSDT'
2026-10-06 22:52:42,366 - App.LiveStreamUseCase - INFO - Executing StopLiveStreamCommand for owner=market.BTCUSDT
2026-10-06 22:52:42,366 - App.LiveStream - DEBUG - release_owner(market.BTCUSDT) requested but it held no subscription; nothing to do.
2026-10-06 22:52:42,366 - App.LiveStreamUseCase - WARNING - Failed to stop live stream. It might not be running.
2026-10-06 22:52:42,367 - App - DEBUG - StopLiveStreamCommand completed successfully.
2026-10-06 22:52:42,367 - App - INFO - Executing command: SyncMarketDataCommand
2026-10-06 22:52:42,367 - App - DEBUG - Payload: symbols=['BTCUSDT'] interval=<TimeFrame.ONE_MINUTE: '1m'> market=<MarketType.FUTURES_USD_M: 'futures_usd_m'> days_back_if_empty=30 start_time=None end_time=None cancellation_requested=<bound method CancellationToken.is_cancelled of <sagittarius_engine.runtime.tasks.cancellation_token.CancellationToken object at 0x00000247E5864780>> correlation_id='02e2d571c5994d868dc8b112d5fdbc85'
2026-10-06 22:52:42,367 - App.SyncMarketData - INFO - Starting sync for symbols: ['BTCUSDT'] at interval 1m
2026-10-06 22:52:42,370 - App.SyncMarketData - INFO - [BTCUSDT] Syncing from latest timestamp: 2026-10-06 15:50:00+00:00
2026-10-06 22:52:42,370 - App.ExchangeClient - INFO - Streaming historical klines for BTCUSDT at 1m from 06 Oct 2026 15:50:00 to NOW
2026-10-06 22:52:42,409 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85947.9 | Vol: 214.781 | Closed: False
2026-10-06 22:52:42,409 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85947.9
2026-10-06 22:52:42,438 - App.LiveStream - DEBUG - [Live Stream] BNBUSDT | Price: 785.41 | Vol: 61.15 | Closed: False
2026-10-06 22:52:42,438 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BNBUSDT at 785.41
2026-10-06 22:52:42,492 - App.LiveStream - DEBUG - [Live Stream] ETHUSDT | Price: 2708.99 | Vol: 923.51 | Closed: False
2026-10-06 22:52:42,493 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for ETHUSDT at 2708.99
2026-10-06 22:52:42,598 - App.Database - DEBUG - Saved 1 klines for futures_usd_m/BTCUSDT to database in chunks of 5000.
2026-10-06 22:52:42,598 - App.SyncMarketData - DEBUG - [BTCUSDT] Persisted chunk of 1 klines (1 total so far) — streamed straight to DB, not held in RAM.
2026-10-06 22:52:42,598 - App.ExchangeClient - INFO - Successfully streamed 1 klines for BTCUSDT.
2026-10-06 22:52:42,598 - App.SyncMarketData - INFO - [BTCUSDT] Successfully synced 1 klines.
2026-10-06 22:52:42,599 - App - DEBUG - SyncMarketDataCommand completed successfully.
2026-10-06 22:52:42,606 - App.QueryHandler - INFO - BACKTEST_TRACE action=read_complete symbol='BTCUSDT' rows=500
2026-10-06 22:52:42,609 - App - INFO - Executing command: StartLiveStreamCommand
2026-10-06 22:52:42,609 - App - DEBUG - Payload: owner='market.BTCUSDT' market_type=<MarketType.FUTURES_USD_M: 'futures_usd_m'> symbols=['BTCUSDT'] interval=<TimeFrame.ONE_MINUTE: '1m'>
2026-10-06 22:52:42,609 - App.ChartCard - INFO - [chart-data] ChartCard(BTCUSDT): loaded 500 candles spanning [1791271920.0, 1791301860.0] | price [85253.0000, 86664.9000] | initial view x-range [1791292741.2, 1791302038.8] | y-range [85881.7880, 86691.9120] | autorange=[False, 1.0] | chart type=candlestick
2026-10-06 22:52:42,610 - App.LiveStreamUseCase - INFO - Executing StartLiveStreamCommand for owner=market.BTCUSDT futures_usd_m ['BTCUSDT'] at 1m
2026-10-06 22:52:42,611 - App.LiveStreamUseCase - INFO - StartLiveStreamCommand executed successfully.
2026-10-06 22:52:42,611 - App - DEBUG - StartLiveStreamCommand completed successfully.
2026-10-06 22:52:42,660 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85950.0 | Vol: 219.474 | Closed: False
2026-10-06 22:52:42,661 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85950.0
2026-10-06 22:52:42,775 - App - INFO - Executing command: StopLiveStreamCommand
2026-10-06 22:52:42,775 - App - DEBUG - Payload: owner='market.BTCUSDT'
2026-10-06 22:52:42,776 - App.LiveStreamUseCase - INFO - Executing StopLiveStreamCommand for owner=market.BTCUSDT
2026-10-06 22:52:42,776 - App.LiveStreamUseCase - INFO - StopLiveStreamCommand executed successfully.
2026-10-06 22:52:42,776 - App - DEBUG - StopLiveStreamCommand completed successfully.
```

## Root cause
**Closed 2026-10-06.** On a fresh dev log (23:16-23:17, relayed by the coordinating session) the owner set the execution mode to HISTORICAL_TICK at 23:16:54 and the run completed at 23:17:41: `RunStaticBacktestCommand`, 61 trades, net -9.34%, `action_finished outcome='SUCCEEDED'`. The owner's words: "à được rồi, tôi không thấy nút F7, nên tưởng không run được" (it works; I could not see the F7 button, so I thought it could not run). So Run was never triggered in the first log, which is why no `run_requested` trace exists. The command matches HLD §11.2.3 (Tools menu, F7, Backtest toolbar; `backtest_commands.py:87`, enabled while idle, tested in `test_backtest_commands.py`).

Established so far (2026-10-06, code read against the log; BUG-159 and BUG-160 share the 1s sync failure, not the missing backtest):
- **Missing backtest: not established, and not a Market-chart defect.** `BackTestPresenter._on_run_backtest` (`backtest_presenter.py:816`) writes the `run_requested` dev trace as its first act, and Run is a Backtest-mode command (`backtest_commands.py:87`, `mode=route`). The pasted app log holds no backtest command and the Backtest Output of BUG-161 holds no `run_requested` between 22:51:05 and 22:53:38, which covers 22:52:40–42. So in that window Run was either not pressed in the Backtest mode or was disabled; the code shows no path that swallows a press. `BACKTEST_TRACE` lines are the Market chart's own history read (`get_historical_klines/handler.py:40`), which is why they looked like a backtest.
- **1s fails on Futures: BUG-159's cause.** Binance USD-M Futures has no 1s klines (`APIError -1120`); fixed in `fix(bug-159)`.
- **Warning after each failed 1s sync: fixed.** `StopLiveStreamCommandHandler` logged `WARNING` ("Failed to stop live stream. It might not be running.") for an owner holding no stream, though every chart restart stops unconditionally (`LiveChartCoordinator.stop`) and the run-log scan fails on WARNING. It is now INFO.
- **The 1s/1m flip every ~0.5 s: not established.** No code path re-selects a timeframe on its own (`ChartToolbar.set_active` never emits); each flip is a `sig_timeframe_changed` from the toolbar, i.e. a click. The log carries no click record.

## Fix
Only the WARNING (above), by `StopLiveStreamCommandHandler`; the report stays Open for the missing backtest and the flip.

## Regression test
`tests/unit/modules/market_data/application/stream/stop_live_stream/test_handler.py::test_an_owner_holding_nothing_is_not_a_warning`, red before the fix, green after.

## Verification
The handler test above; the unit suites of `support` and `modules` green. Not reproduced on the user's desktop.

## Suggested next steps
Proposal for the owner (not done): make Run backtest more discoverable than the toolbar entry and F7, e.g. a Run button inside the setup panel; a UX change under `ui-presentation-rule.md`.
