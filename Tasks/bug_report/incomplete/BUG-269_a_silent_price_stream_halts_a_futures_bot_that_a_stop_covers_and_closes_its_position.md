# BUG-269 — A silent price stream halted a Futures Grid whose stop stood on the exchange, and the halt closed its position at market

- **Reported:** 2026-10-25 (the owner's mainnet Futures bot `y3embt`, through the coordinating session)
- **Severity:** 🔴 P1 — real money: a healthy leveraged position under a standing protective stop was closed at market (a taker exit and the loss of the grid's cycle) because a WebSocket dropped for about a minute while REST worked throughout.
- **Status:** Open
- **Board:** A dead Binance price WebSocket takes about 40 s to be noticed and the 60 s staleness limit then halts the bot, although REST prices were readable the whole time; on Futures the halt is not recoverable and closes the position even when the exchange-side stop covers it.
- **Context:** [SPEC-014 run a grid bot](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `src/modules/bots/` → `application/kinds/grid/watch/` (`GridPriceReaction.check_age`, `GridPriceAge`), `domain/halt_recovery_policy.py`, `contracts/venue_profile.py`, `application/kinds/grid/grid_parking.py`; and `src/modules/market_data/adapters/binance/binance_websocket_service.py` for the library's log output
- **Environment:** Mainnet Futures USD-M, BNBUSDT Grid, 31 grid orders and a protective stop standing; `master-warrior` at `bfae44f` (code read there). Engine: `engine.ref` of that commit.

## Reproduction
Not yet reproduced as a test; the journal below is the evidence. Minimum path to reproduce on the fake exchange: a running Futures Grid with a standing protective stop; stop delivering ticks for 60 s while the mark price stays readable over REST. Expected: the bot goes on judging its stop and ladder on the REST price. Actual: `price_feed_stale` halts it, `GridParking.park` cancels the ladder and closes the position at market.

## Symptom
Journal of 2026-10-25 (unstamped lines come from the Binance client library on stderr):
```
11:30:36 -1021: one request rejected as late; the clock offset re-measured 40 ms -> 5 ms
11:31:45 health: tick_age_s=2
ConnectionClosedError (sent 1011 (internal error) keepalive ping timeout; no close frame received)
BinanceWebsocketClosed (Connection closed. Reconnecting...)
11:32:58 RUNNING -> HALTED on halt (price_feed_stale: last tick 62 s ago; the limit is 60 s)
11:32:58-11:33:02 31 CancelOrderCommand over REST, each about 90 ms: all done
11:33:02 HALTED -> STOPPING: "any position is closed at market, as a leveraged position is never left bare"
11:33:04 exit slice 1 of 0.19 done; the protective stop was already gone at 11:33:05
11:33:05 STOPPED, result +1.577 USDT
BinanceWebsocketQueueOverflow (Message queue size 100 exceeded maximum 100)
```
Expected instead: the bot keeps judging on the REST mark price, or, if it must wait, waits with its stop standing and recovers by itself.

## Root cause
Not yet established as one mechanism; three established facts at `bfae44f` and one open question. Cited as `file:line` at that sha (a point-in-time record).

1. **The staleness limit is longer than the library needs to reconnect and shorter than the library needs to notice.** `python-binance` pings every 20 s and waits 20 s (`websockets` defaults), so a dead connection is noticed after about 40 s, then reconnects. `PRICE_STALE_AFTER_SECONDS = 60.0` (`src/modules/bots/domain/grid/price_freshness.py:23`) leaves about 20 s for the reconnect. `GridPriceReaction.check_age` (`.../watch/grid_price_reaction.py:232`) then halts on the stream's age alone: **nothing counts a price read over REST as a heard price**, although a Futures bot already reads the mark price over REST on every beat for its exits (`GridMarkExit.check`, `.../stop/grid_mark_exit.py:34`, posted by `GridFacts.on_price_age_check`, `grid_facts.py:209`). The REST read judged the exits and was ignored by the age.
2. **The Futures recovery layer recovers only `rate_limited`.** `_FUTURES` in `contracts/venue_profile.py:115-134` clears the lower layers and lists `RATE_LIMITED` alone, so `price_feed_stale` is a plain `halt`. `GridParking.park` (`grid_parking.py:78`) cancels the ladder and, because the venue closes on a halt, closes the position at market (`_close_position`, `:100`), whether or not a stop stands. `describe_stop`/`StopCoverageReader.read` already know whether a stop covers the position (`protection/stop_coverage_reader.py:72`) and `EPIC-038M` (O12) already leaves a covered Futures bot alone at a host stop; the halt does not ask.
3. **The library's records bypass the application log.** `ReconnectingWebsocket` logs through `logging.getLogger("binance.ws.reconnecting_websocket")` (`.venv/.../binance/ws/reconnecting_websocket.py:64`), a logger outside `App.*`, so its ERROR records fall to Python's unformatted last resort on stderr: no timestamp, not in the log file, not caught by the gate's log scan (`logging-rule.md` §1).
4. **Open: the `BinanceWebsocketQueueOverflow`.** `max_queue_size` is 100 (`reconnecting_websocket.py:46`) and the overflow is raised by the library's read loop when the consumer has not drained the queue. Whether the consumer stopped reading (the stream task was cancelled when the stopped bot released its last owner, at 11:33:05, while the library's read loop was still receiving) or a burst arrived on reconnect is **not yet established**; to be settled by a test that drives the real `ReconnectingWebsocket` against a fake server, not by reading.

The gate was green: no test held a Futures bot with a stop and a silent stream, and no test read the stderr of the library.

## Fix
Pending; the design is in the decision record [`DECISION_2026-10-25_a_silent_stream_is_not_a_halt`](../../epics/EPIC-042_halt_auto_recovery/DECISION_2026-10-25_a_silent_stream_is_not_a_halt.md). Three commits, one per item, each with its regression test red first.

## Regression test
Pending (named in the decision record §5).

## Verification
Not run.

## Suggested next steps
Owner confirmation in the author session (real-money rule); then the three items in order.
