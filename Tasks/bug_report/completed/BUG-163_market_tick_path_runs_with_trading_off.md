# BUG-163 — The live market stream runs with trading off, and its tick path logs twice per tick and can read the account

- **Reported:** 2026-10-06 (the owner, in chat, Vietnamese: why does the live stream run by itself when trading is not enabled and the key fails the connection check; is it a red flag)
- **Severity:** 🟡 P2 — no order can be sent, but a `--dev` log is buried (about 24 lines a second for three symbols) and an armed strategy reads the account with the venue key while trading is OFF
- **Status:** ✅ Fixed (2026-10-06)
- **Board:** Fixed: the Market stream is by design (started by the user's open of the Market mode); its per-tick lines were DEBUG, now TRACE (`logging-rule.md` §6), and a strategy signal with trading OFF now stops before any metadata or account read (the key) and tells the desk, instead of reading first.
- **Context:** `Docs/SPEC/` Market data view → `src/modules/strategy/` (`application/event_handlers/`, `application/services/`) and `src/modules/market_data/adapters/binance/`
- **Environment:** Windows (the owner's desktop), Futures Testnet venue, a mainnet key (`-2015`, shown as KEY_EXPIRED). Reproduced on Linux, master-warrior at 2a5c739, Python 3.12.

## Reproduction
1. Open the Market mode with a click (watchlist BTCUSDT, ETHUSDT, BNBUSDT at 1m). Trading stays OFF.
2. Run with `--dev` (DEBUG). The log fills with the lines below, forever.
3. Unit tier: `handler.handle(tick)` with no session logs one DEBUG line; the websocket service logs one more per kline.
4. With a strategy armed on the venue and trading OFF, `LiveTradingCoordinator.handle(signal)` calls `metadata_provider.get_or_fetch` and `account_reader.check_connection()` (a signed request) before it looks at the switch.

## Symptom
```
2026-10-06 23:03:20,131 - App.LiveStream - DEBUG - [Live Stream] BTCUSDT | Price: 85768.7 | Vol: 68.671 | Closed: False
2026-10-06 23:03:20,131 - App.TradingStrategy - DEBUG - Processing futures_usd_m tick for BTCUSDT at 85768.7
2026-10-06 23:03:20,233 - App.LiveStream - DEBUG - [Live Stream] ETHUSDT | Price: 2702.73 | Vol: 1929.232 | Closed: False
```
Four updates a second per symbol (Binance pushes the forming kline about every 250 ms), three symbols, two lines each: about 24 lines a second, 86,000 an hour.

## Root cause
(a) The stream is by design, and a defect only in its noise. `MarketPresenter.on_mode_shown` (`src/modules/trading/ui/market/market_presenter.py:158`) starts the Watchlist stream when the mode is shown by `USER_INTENT`; a restore at start stays quiet (`test_main_window_state.py`, 14 tests green here, including every stored mode). A public kline stream needs no key, and none is read on that path. What I could not establish is who clicked Market on the owner's run; a restore at start does not start it.

(b) The tick handler is subscribed to every market's ticks (`strategy/module.py:274`). With no armed strategy it does nothing but log: `VenueStrategySessions.built_for` returns no session, or `LiveStrategySession.dispatch_tick` returns at `engine is None` (`live_strategy_session.py:212`). It cannot reach an order, the account or the key. With a strategy armed (arming needs trading OFF, `arm_strategy/handler.py:115`; a saved complete config is re-armed at boot, `strategy/module.py:285`), a signal reached `LiveTradingCoordinator.handle` (`live_trading_coordinator.py`), which fetched metadata and called `account_reader.check_connection()` before the switch was asked; `ExecuteOrderHandler` orders its own gates switch first (`execute_order/handler.py:240`), the coordinator did not. So with an armed strategy the key was used while trading was OFF, for a refusal that is free.

(c) `MarketTickEventHandler.handle` logged at DEBUG for every tick of every symbol (`market_tick_event_handler.py:103`), and `binance_websocket_service.py:266` another, against `logging-rule.md` §6 (per-tick is TRACE). `BUG-113` moved the second from INFO to DEBUG and a test pinned DEBUG. The rest of the per-tick work is a lock, an empty tuple and the bus fan-out (`BotEventRouter.on_tick`, the Qt tick feeds).

No net was green-and-wrong in a way that earns a case study: the test that pinned DEBUG pinned the fault.

## Fix
- `live_trading_coordinator.py`: `handle()` asks the trading switch first (`_is_ignored`, with the symbol check that was already there). With trading OFF it publishes `LiveOrderBlockedEvent("Trading is OFF — …")` for the desk and returns before the metadata fetch and `check_connection()`; the order it would have refused anyway is untouched, so nothing that sent an order before is changed. The mechanism is the gate order the submission handler already uses, applied where the strategy's signal enters, not a flag at one caller.
- `market_tick_event_handler.py`, `binance_websocket_service.py`: the per-tick lines are `TRACE` behind `isEnabledFor`, so a `--dev` run no longer carries them and a normal run pays no formatting cost.
- Scanned for the same shapes: no other per-tick DEBUG on the bus path (`BotEventRouter.on_tick`, both Qt tick feeds log nothing); the other coordinator-style entry (`BotOrderGateway`) already refuses on the switch first.

## Regression test
- `tests/unit/modules/strategy/application/services/test_live_trading_coordinator_trading_off.py::test_a_signal_with_trading_off_reads_no_account_and_no_metadata` — red before the fix: `Expected 'check_connection' to not have been called. Called 1 times.`; green after. Real coordinator, real stdlib logging untouched; only the ports are doubles, and the account reader is the one whose call is asserted.
- `tests/unit/modules/strategy/application/event_handlers/test_market_tick_event_handler.py::test_a_tick_logs_nothing_above_trace` and `tests/unit/modules/market_data/adapters/binance/test_binance_websocket_service.py::test_kline_tick_logs_at_trace_only` — red before (one DEBUG record each), green after. They replace the two tests that pinned DEBUG and are stronger: no record at DEBUG or above, one at TRACE (5).

## Verification
- The three tests above, red then green; `tests/unit/modules/strategy`, `tests/unit/modules/market_data/adapters`, `tests/unit/architecture`: 982 passed.
- Commit tier (`ci-local.ps1 -SkipTests`): PASS. The first run of the architecture guards caught two growths of mine (`C901` on `handle`, the god-file ceiling on its test file); fixed by extracting `_is_ignored` and moving the test to its own file.
- Positive proof the new mechanism ran: the `caplog` tests capture the `App.TradingStrategy` and `App.LiveStream` records at TRACE and none at DEBUG, and the blocked event is published once with the "Trading is OFF" reason.
- `tests/integration/presentation/ui/test_main_window_state.py`: 14 passed on the unchanged tree, so nothing starts the stream at launch.
- Not run: the real application with a real stream (no network). GitHub Actions' `ci-local.ps1 -Full` on the PR.

## Follow-ups (not part of this fix)
- Owner decision, not changed here: the Market mode's Watchlist keeps streaming after the user leaves the mode (no hide hook releases it until the window closes). Recommendation: release it when the mode is hidden, restart on the next open.
- Owner decision: a saved complete strategy is re-armed at boot, so an armed strategy exists at start without a click.
- Separate defect, to file as BUG-164 once the coordinating session confirms the number: `LiveStrategySession.dispatch_tick` (`live_strategy_session.py:198`) feeds forming candles (`is_closed=False`) into `StrategyEngine.on_tick`, committing indicator state per update where the docstrings say closed candles.
