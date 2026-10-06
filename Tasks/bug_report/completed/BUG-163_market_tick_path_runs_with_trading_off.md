# BUG-163 — The live market stream runs with trading off, and its tick path logs twice per tick and can read the account

- **Reported:** 2026-10-06 (the owner, in chat, Vietnamese: why does the live stream run by itself when trading is not enabled and the key fails the connection check; is it a red flag)
- **Severity:** 🟡 P2 — no order can be sent, but a `--dev` log is buried (about 24 lines a second for three symbols) and an armed strategy reads the account with the venue key while trading is OFF
- **Status:** Open
- **Board:** The Market stream's ticks log two DEBUG lines each (`App.LiveStream`, `App.TradingStrategy`), about 24 a second for three symbols; with a strategy armed and trading OFF each signal still fetched metadata and read the account with the key before the switch refused it. Not fixed yet.
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
Not yet.

## Regression test
Not yet.

## Verification
Not run.

## Suggested next steps
- Owner decision, not changed here: the Market mode's Watchlist keeps streaming after the user leaves the mode (no hide hook releases it until the window closes). Recommendation: release it when the mode is hidden, restart on the next open.
- Owner decision: a saved complete strategy is re-armed at boot, so an armed strategy exists at start without a click.
- Separate defect, to file as BUG-164 once the coordinating session confirms the number: `LiveStrategySession.dispatch_tick` (`live_strategy_session.py:198`) feeds forming candles (`is_closed=False`) into `StrategyEngine.on_tick`, committing indicator state per update where the docstrings say closed candles.
