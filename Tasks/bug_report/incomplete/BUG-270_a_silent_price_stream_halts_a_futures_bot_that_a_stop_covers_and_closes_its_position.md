# BUG-270 — A silent price stream halted a Futures Grid whose stop stood on the exchange, and the halt closed its position at market

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
Four mechanisms, read at `bfae44f` (a point-in-time record: `file:line` at that sha).

1. **The age check ignored the price the bot was reading.** `GridPriceReaction.check_age` (`src/modules/bots/application/kinds/grid/watch/grid_price_reaction.py:232`) halted on the stream's age alone (`PRICE_STALE_AFTER_SECONDS = 60.0`, `domain/grid/price_freshness.py:23`), although a Futures bot reads its mark price over REST on every beat for its stop loss and take profit (`GridMarkExit.check`, `application/kinds/grid/stop/grid_mark_exit.py:34`, posted by `GridFacts.on_price_age_check`, `grid_facts.py:209`). The REST read judged the exits and was ignored by the age.
2. **The Futures venue layer recovered only `rate_limited`.** `_FUTURES` (`contracts/venue_profile.py:115-134`) cleared the lower layers and listed `RATE_LIMITED` alone, so `price_feed_stale` was a plain `halt`; `GridParking.park` (`application/kinds/grid/grid_parking.py:78`) then cancelled the ladder and closed the position (`_close_position`, `:100`) whether or not a stop covered it, although `StopCoverageReader.read` (`protection/stop_coverage_reader.py:72`) already tells whether one does and ADR 038M O12 leaves a covered Futures bot alone at a host stop.
3. **The library's records bypassed the application log.** `ReconnectingWebsocket` logs through `logging.getLogger("binance.ws.reconnecting_websocket")` (`binance/ws/reconnecting_websocket.py:64`), outside `App.*`, so its ERROR records fell to Python's unformatted last resort on stderr (`logging-rule.md` §1).
4. **Why the stream was blind for about 65 s and not for the few seconds the library needs to reconnect, and what the overflow was** (answers the owner's question 3; measured by the one-off probe described under *The probe* below, which is not kept in the tree). The library reconnects by itself within a second. The app's consumer reads the library's `{"e": "error"}` message at once, raises `KlineStreamError` (`binance_websocket_service.py:289`) and leaves `async with socket`; the library's `__aexit__` sets `ws_state = EXITING` and waits for its read loop to end, but the read loop is mid-reconnect and `connect()` then sets `ws_state = STREAMING`, overwriting `EXITING` (`reconnecting_websocket.py:114-135`, `:95-110`), so the loop never ends. The consumer sits in that exit and **reads nothing** while the library fills its 100-message queue (25 s at the Futures rate of 4 klines a second, 100 to 200 s on Spot); `BinanceWebsocketQueueOverflow` ends the read loop, which releases the exit, and only then does the app log its error, wait 5 s and reconnect. **The overflow was a consumer that did not read** (held in the socket's own shutdown), **not a burst on reconnect**: a 35 s stall of the event loop with the same server produced no overflow (peak queue 0), and a clean cancel of the stream task left no read loop running. In the probe: 12 klines, the drop at 3.0 s, `ConnectionClosedError`, `BinanceWebsocketClosed`, nothing read until 34.9 s, `BinanceWebsocketQueueOverflow` at 29.9 s: the three records of the owner's journal, in its order. Forty seconds to notice the dead connection, about twenty-five more in the stuck exit, and the 60 s limit was crossed (last tick 62 s old).

The gate was green: no test held a Futures bot with a stop and a silent stream, none read the stderr of the library, and nothing exercised the stream's exit against the real library.

### The probe (a one-off measurement, not kept in the tree)
Method, so it can be rebuilt: a local `websockets` server on 127.0.0.1 pushes one Binance-shaped `kline` message every 250 ms (the Futures rate) and, on its first connection only, closes with code 1011 ("keepalive ping timeout") after 12 messages; the real `BinanceWebsocketService._run_stream` runs on an asyncio loop with `create_closing_on_cancel`, `BinanceSocketManager` and `open_kline_socket` replaced in the module by a stub client and a factory returning `ReconnectingWebsocket("ws://127.0.0.1:<port>/", path="", prefix="")`; the event bus is a stub that notes the time of each `emit`, and a sampler reads the library's `_queue.qsize()` every 50 ms for 40 s. A second run blocks the loop with `time.sleep(35)` in the first `emit` instead of dropping the connection, and a third cancels the stream task cleanly.
Output of the drop run (python-binance as pinned in `requirements.lock`, 2026-10-25):
```
   3.0 binance.ws.reconnecting_websocket: ConnectionClosedError (received 1011 (internal error) keepalive ping timeout; then sent 1011 (internal error) keepalive ping timeout)
   3.0 binance.ws.reconnecting_websocket: BinanceWebsocketClosed (Connection closed. Reconnecting...)
  29.9 binance.ws.reconnecting_websocket: Unknown exception: BinanceWebsocketQueueOverflow (Message queue size 100 exceeded maximum 100)
  29.9 App.LiveStream: WebSocket connection error: the library reported a stream error: type='ConnectionClosedError' ... Reconnecting in 5s...
klines read: 35; connections the server saw: 3
peak of the library's queue: 101 (its limit is 100)
gaps in which the consumer read nothing, (from, to) seconds: [(2.8, 34.9)]
```
The 35 s loop block: 191 klines read after it, peak queue 0, no overflow. The clean cancel: the read loop was not alive afterwards and the queue held 1 message.

## Fix
Three commits, one per item of the owner's decision (2026-10-25, and again in the author session: "đồng ý ba việc, chờ tối đa 15 phút, chỉ Futures"), each with its test red first; the decision record is [`DECISION_2026-10-25_a_silent_stream_is_not_a_halt`](../../epics/EPIC-042_halt_auto_recovery/DECISION_2026-10-25_a_silent_stream_is_not_a_halt.md).
- **Item 1** (`41302f4`): `GridPriceAge.note_poll` (`.../watch/grid_price_age.py`); `GridPriceReaction.on_mark` notes each mark read as a price heard, so a quiet stream with a readable mark halts nothing; the quiet stream is said once at WARNING `[price-poll]` after 15 s. No new request: the mark read was already made every beat. Futures only.
- **Item 2** (`2523b80`): the Futures venue layer lists `price_feed_stale` under the default rule; `GridCoveredWait` (`.../recovery/grid_covered_wait.py`) makes the halt a wait only when a fresh read answers `COVERED`, keeps the ladder and the stop, and ends the wait in the plain halt (cancel, close at market) when the stop stops covering, is unread three reads in a row (one read in three beats), or 15 minutes pass; the stop is supervised during the wait.
- **Item 3**: `route_binance_client_logs` (`src/shell/binance_client_log.py`), installed by `create_app`: the library's records are `App.BinanceClient` records tagged `[binance-client]`, capped at WARNING.
- **Not fixed here, and proposed:** the stuck exit of mechanism 4 is the reason the stream is blind for so long; items 1 and 2 stop a blind stream from closing a bot, they do not shorten it. Filed as [BUG-271](BUG-271_a_dropped_price_websocket_leaves_the_app_reading_nothing_for_25_s_in_the_librarys_socket_shutdown.md), to be decided after this pull request merges.

### What a waiting bot meets, decided and tested (review round 1)
- **A fill**: booked, its counter order held (the ladder places nothing outside RUNNING and PAUSED); nothing is sent; the stop covers the grown position; the recovery attempt re-lays the ladder from the exchange's evidence.
- **A user stream that goes down**: does not end the wait (`GridStreamGap.halt` acts on RUNNING and PAUSED bots only), but the resume now waits for the stream (`GridHaltRecovery._every_cause_clear`), because the policy of a Futures venue lists no stream reason and a ladder must not be laid while its fills go unreported (the rule of PR #552, for Spot). Found by the review's question and red before the fix.
- **The exchange's pause**: met by the recovery attempt it hands the wait to the rate-limit wait (`EPIC-042F`; the reason becomes `rate_limited`, the position stays open under its stop, nothing is sent into the pause, the 15-minute limit is not judged for its length, the attempt budget is); a pause over an hour is a plain halt that leaves the position under its stop and says so, as a rate limit always did on a Futures venue. A coverage read refused by the pause counts as unreadable, and three in a row end the wait in the plain halt, whose own cancel and close then meet the same pause: the outcome a halt had before this change.

## Regression test
- Item 1: `tests/unit/modules/bots/application/services/test_a_silent_stream_with_a_readable_mark_is_not_a_halt.py` (3 of 5 red before: a dead stream with a readable mark halted the bot; a mark back inside the limit did not keep it running; the quiet stream was not said) and the composed `tests/integration/modules/bots/test_a_futures_grid_halts_and_recovers_on_the_fake_exchange.py::test_a_silent_feed_does_not_halt_a_bot_whose_mark_price_is_read`.
- Item 2: `tests/unit/modules/bots/application/services/test_a_futures_wait_under_a_covering_stop.py` (4 of 7 red before: the covered wait, its recovery, its end on a lost stop, its end at 15 minutes; the 3 halts without a covering stop, uncovered, unread, nothing exposed, are green before and after: the unchanged path) and `tests/unit/modules/bots/application/kinds/grid/protection/test_a_wait_under_the_stop_is_supervised.py` (red before).
- Item 3: `tests/unit/shell/test_the_binance_client_log_goes_through_the_app_log.py` (4 of 5 red against a no-op route; the wiring test red with the call removed from `create_app`).
- Four tests that used a silent feed to prove "a halt closes the position" now use a down user stream: the Futures halt-closes journeys keep their proof, on a reason that is still unrecovered there.

## Verification
At the head named in the pull request: the commit tier (`ci-local.ps1 -SkipTests`) PASS; the touched unit and integration tests, `tests/unit/modules/bots` and `tests/unit/architecture` green except `test_system_display_timezone.py[Europe/London]`, which fails on this container's tzdata (`BST` against `GMT`) and touches nothing here. The full gate is GitHub Actions' `ci-local.ps1 -Full` run on the head; its job logs are cited in the pull request. Positive proof the mechanisms ran: the tests' own logs show `[price-poll]`, `the wait under the stop ends` and `[binance-client]` lines; mechanism 4 by the probe's output above. Not proven: a real exchange (the fake has no mark-read fault, so the covered wait is proven on the simulated venue of the unit tier, not on the composed fake).

