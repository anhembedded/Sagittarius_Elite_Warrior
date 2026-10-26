# BUG-271 — A dropped price WebSocket leaves the app reading nothing for about 25 s, held in the library's socket shutdown

- **Reported:** 2026-10-25 (found while explaining the owner's mainnet incident behind [BUG-270](BUG-270_a_silent_price_stream_halts_a_futures_bot_that_a_stop_covers_and_closes_its_position.md); filed as its own bug on the coordinator's instruction, to be decided after #732 merges)
- **Severity:** 🟡 P2 — a Futures bot rides the blind window on its REST mark price and its stop (BUG-270), so nothing is lost; but every chart and every Spot bot (whose exits are judged on the stream) is blind for the drop's detection (about 40 s) plus about 25 s more, and at the Spot rate (one kline a second or two) the stuck exit lasts 100 to 200 s.
- **Status:** Open
- **Board:** After a price WebSocket drop the market-data adapter leaves the socket on the library's error message and sits in the library's `__aexit__`, which waits for a read loop that the library's own reconnect keeps alive, until the unread queue overflows; the stream is blind about 25 s longer than the connection is down.
- **Context:** the live price stream → `src/modules/market_data/` → `adapters/binance/` (`BinanceWebsocketService._run_stream`); the library is `python-binance`'s `ReconnectingWebsocket`
- **Environment:** the pinned `python-binance` of `requirements.lock`, Linux, reproduced against a local server (no exchange); the owner's mainnet journal of 2026-10-25 shows the same three records.

## Reproduction
The method and its output are in BUG-270's *The probe*. In short: a local server pushes a kline every 250 ms and closes its first connection with 1011; the real `BinanceWebsocketService._run_stream` and the real `ReconnectingWebsocket`. Every time: the consumer reads nothing from the drop (2.8 s) to 34.9 s.

## Symptom
```
   3.0 binance.ws.reconnecting_websocket: ConnectionClosedError (received 1011 ... keepalive ping timeout ...)
   3.0 binance.ws.reconnecting_websocket: BinanceWebsocketClosed (Connection closed. Reconnecting...)
  29.9 binance.ws.reconnecting_websocket: Unknown exception: BinanceWebsocketQueueOverflow (Message queue size 100 exceeded maximum 100)
  29.9 App.LiveStream: WebSocket connection error: the library reported a stream error ... Reconnecting in 5s...
gaps in which the consumer read nothing, (from, to) seconds: [(2.8, 34.9)]
```
Expected: ticks resume within a second or two of the library's reconnect.

## Root cause
Not yet fixed; established in BUG-270 (code read at `bfae44f`): `BinanceWebsocketService._process_socket_message` raises `KlineStreamError` on the library's `{"e": "error"}` message (`binance_websocket_service.py:289`), and `_run_stream` leaves `async with socket`. `ReconnectingWebsocket.__aexit__` sets `ws_state = EXITING` and waits (`_kill_read_loop`) for the read loop to end; the read loop is mid-reconnect and `connect()` sets `ws_state = STREAMING`, overwriting `EXITING`, so the loop keeps running and the exit waits until `BinanceWebsocketQueueOverflow` ends it (`reconnecting_websocket.py:95-135`, `:184-250`). The app asked to leave a socket that was already repairing itself.

## Fix
Pending. Proposed, decided by the Constitution (the owner may veto; nothing is built before #732 merges):

| Option | What | Verdict |
| :--- | :--- | :--- |
| A | **Do not leave the socket on an error the library reconnects from.** Keep reading after `ConnectionClosedError`, `ConnectionClosedOK`, `IncompleteReadError`, `BinanceWebsocketClosed` (log them, they are already in the app log since BUG-270); leave only on the library's terminal errors (`BinanceWebsocketUnableToConnect`, `BinanceWebsocketQueueOverflow`, `ReadLoopClosed`), where the app's own 5 s reconnect applies as today. | **Recommended.** P5: uses the library as it is designed to be used instead of fighting its reconnect. P6: removes the mechanism (an exit that races a reconnect) instead of patching its symptom. P1/P4: a test on the real `ReconnectingWebsocket` against a local server (the BUG-270 probe, as a test with a fake clock-free wait on the queue) is red before and green after. P7: no new seam. Reversible by a revert; touches no real-money behaviour by itself, but it changes when ticks reach every bot, so the owner confirms. |
| B | Close the library's websocket directly and drop the cached socket from the manager, then reconnect ourselves. | Rejected: reaches into private attributes (`_conns`, `ws`), the "copy that drifts" of P3. |
| C | A smaller `max_queue_size`. | Rejected: shortens the stuck exit by making the overflow come sooner, and loses real ticks; it treats the symptom (P6). |
| D | A shorter ping interval and timeout to detect the drop sooner (about 40 s now). | Separate and complementary: a library keyword (`ws_kwargs`), no code change in the exit; to be decided with A, its own risk is a false drop on a slow network. |

## Regression test
Pending: the probe's scenario as a test on the real library and a local server, asserting the consumer reads again within a bounded number of messages after the drop (waiting on the arrival of the next kline, never on a sleep).

## Verification
Not run.

## Suggested next steps
After #732 merges: the owner decides A (and D); one commit with the test red first.
