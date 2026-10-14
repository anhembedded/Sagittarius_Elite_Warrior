# BUG-143 — Stopping the app with the Spot user-data stream live leaves its tasks pending and its HTTP session unclosed

- **Reported:** 2026-10-04 (the user's `-TestnetOnly` run on `master-warrior` `e5ca8226`, pasted in chat)
- **Severity:** 🟢 P3. No order or state is lost; the process prints asyncio and aiohttp warnings at shutdown, and the stream's connection is dropped rather than closed.
- **Status:** ✅ Fixed (2026-10-14)
- **Board:** Stopping the app with the Spot user-data stream live printed `Task was destroyed but it is pending!` and, once the engine drained first, `1 task(s) did not finish cancelling within 5.0s ... SpotUserDataStream` plus `async generators did not close within 5.0s`. Two causes: the engine stopped the loop before cancelling (engine `BUG-017`), then the Spot socket's exit waited the library's 10 s for an unsubscribe reply that the already-cancelled `ws_api` read loop could not deliver. Fixed here: both user streams leave their socket and close their client through `websocket_teardown` (bounded steps, the read loop cancelled), and the supervisor re-raises cancellation.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (run a Grid bot on Spot) → `Sagittarius_Engine` `runtime/async_runtime/async_runtime.py` (`AsyncRuntime.stop`); seen through `src/modules/trading/adapters/binance/spot/spot_user_data_stream.py`
- **Environment:** Windows, Python 3.14.6, `python-binance` 1.0.37, `websockets` 17.2, engine `engine.ref` `ea2d330c`. Spot Testnet only enabled.

## Reproduction

1. Run `tests/testnet/test_grid_bot_round_trip.py` (`$env:SEW_TESTNET_TESTS=1; .\scripts\ci-local.ps1 -TestnetOnly`). Its fixture turns trading on through `EnableTradingCommand`, which starts `SpotUserDataStream`, and calls `engine.stop()` at teardown.
2. The test passes. At teardown the console prints the lines below.

Expected: the stream's task is cancelled and awaited, its `finally` closes the `AsyncClient` connection, and nothing is reported pending or unclosed.

Seen once, on the first run in which the app's Spot stream ran live and was stopped. Not yet reproduced elsewhere; the app's own window close takes the same `engine.stop()` path, so it is expected there too.

## Symptom

```
Task was destroyed but it is pending!
task: <Task cancelling name='Task-1' coro=<TaskManager._wrap_coro() running at ...\sagittarius_engine\runtime\tasks\task_manager.py:190> wait_for=<Future cancelled> ...>
Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x00000227F2732120>
Task was destroyed but it is pending!
task: <Task cancelling name='Task-4' coro=<Connection.keepalive() running at ...\websockets\asyncio\connection.py:815> wait_for=<Future cancelled>>
Task was destroyed but it is pending!
task: <Task cancelling name='Task-5' coro=<ReconnectingWebsocket._read_loop() done, defined at ...\binance\ws\reconnecting_websocket.py:184> wait_for=<Future cancelled>>
```

The run-log scan stayed green: these are interpreter warnings on stderr, not log records.

## Root cause

Established on engine `ea2d330c` (3.0.0), reproduced without Binance:

- `SpotUserDataStream.stop()` cancels the task's `concurrent.futures.Future`, which schedules `task.cancel()` on the runtime's loop and returns at once. The task still needs loop iterations to unwind its `finally` (`await client.close_connection()`).
- `AsyncRuntime.stop()` (`sagittarius_engine/runtime/async_runtime/async_runtime.py`, `stop`) then calls `loop.stop` and joins the thread. Only after the loop has stopped does it call `task.cancel()` on what is still pending, and then `loop.close()`. A task cancelled after its loop has stopped never runs again, so every pending `finally` is dropped and the coroutine is garbage-collected while `cancelling`.
- Reproduction: a coroutine awaiting `sleep(3600)` inside `try/finally`, whose `finally` awaits once and records a flag. It is spawned with `AsyncRuntime.run_coroutine`; its future is cancelled; then `stop()` runs. The flag is never set, and the run prints `Task was destroyed but it is pending!`, the same line as the user's run.
- The mechanism is in the Engine, so every async task the app spawns has it, not just the Spot stream: the Futures stream and the live market stream too.

**Fix direction, proved on the same reproduction:** before stopping the loop, `stop()` schedules a drain coroutine on the loop. The drain cancels every other task that is not already `cancelling()`, awaits them with `asyncio.wait(..., timeout)`, then calls `loop.shutdown_asyncgens()`. With that, the flag is set and nothing is reported pending. The `cancelling()` check matters: cancelling a task a second time aborts the `await` inside its `finally`, which was the first draft's mistake.

## Fix

In `Sagittarius_Engine` (engine `BUG-017`), with the user's confirmation for both the Engine change and the bump:

- Engine PR #227 (`c62fb42`): `AsyncRuntime.stop()` drains the loop before stopping it. The drain cancels every task not already `cancelling()`, awaits them, then shuts down async generators.
- Engine PR #228 (`934b830`): `stop(timeout)` is one deadline. The drain may use half of it and the join gets the rest. Tasks that never finish cancelling are named in a WARNING. `TaskManager` names each asyncio task after the task it spawned.

This repository's `engine.ref` now pins `934b830f5b4e6c0a5442b94833edacf443f87c79`.

## Second cause (found 2026-10-15 from the owner's Spot Mainnet shutdown log)

With the engine fix in place the owner's close printed, for the Spot stream, none of its own lines, then `1 task(s) did not finish cancelling within 5.0s ... SpotUserDataStream` and `async generators did not close within 5.0s`. The two `App.LiveStream` lines in that log were the kline stream's (`binance_websocket_service.py`), which closes cleanly; the Spot stream never reached its `finally`'s log line.

- `AsyncRuntime.stop()` cancels **every** task at once, `ws_api`'s read loop (a library task) included.
- Spot's `bsm.user_socket()` is a `KeepAliveWebsocket` on a `ws_api` subscription. Its `__aexit__` (`binance/ws/keepalive_websocket.py:39`) sends `userDataStream.unsubscribe` through `ws_api.request` and waits `TIMEOUT` = 10 s for the reply (`websocket_api.py`, `request`). The reply is delivered by `ws_api`'s read loop, already cancelled, so the wait always runs the full 10 s: past the 5 s drain.
- `async generators did not close` is a consequence: the drain's budget was spent on that task.
- A related wait, found while reproducing: `ReconnectingWebsocket.__aexit__` (so `close_connection()` for `ws_api`, and a Futures socket's exit) sets `EXITING` and polls until its read loop notices, between receives, up to 10 s on an idle connection. It shows when one stream is stopped while the loop keeps running (a reconnect, trading switched off), with the read loop alive. The Futures stream shares this; it does not share the unsubscribe (no `ws_api` subscription), so the Futures stream was not hitting the runtime-drain case.
- The supervisor also swallowed `CancelledError` (`break`), so a cancelled stream task ended as a normal return.

Hypotheses ruled out: a swallowed `CancelledError` in the stream loop (the loop does not catch it; only the supervisor did, harmlessly for timing); a blocking listen-key DELETE (Spot uses no listen key); an un-`aclose()`d generator (the second warning follows from the first).

## Fix (second cause)

`src/modules/trading/adapters/binance/websocket_teardown.py`, used by `ManagedUserDataStream` for both venues:

- `close_socket(socket)`: the read loop of that socket is cancelled (the library's own shutdown path for it), then `socket.close()` runs under a 1.5 s bound. A timeout is logged at INFO: the courtesy unsubscribe could not be answered, and closing the connection ends the subscription on the exchange.
- `close_client(client)`: `ws_api`'s read loop is cancelled, then `close_connection()` runs under the same bound; a timeout is a WARNING.
- `UserStreamSupervisor.run` re-raises `CancelledError` after logging it.
- Spot and Futures `_run_session` enter the socket explicitly and leave it through `close_socket` in a `finally`, and close the client through the base class.

The runtime's 5 s timeout is unchanged and no warning is filtered: the steps now end inside the drain.

## Regression test

Engine `BUG-017`'s tests, as before, plus here `tests/unit/modules/trading/adapters/binance/test_user_stream_unwinds_within_the_runtime_drain.py` (library classes over a loopback peer, `quiet_loopback_exchange.py`):

- `test_stopping_the_runtime_with_the_spot_stream_live_prints_no_warning`: real `AsyncRuntime.stop()`; red before the fix with exactly the owner's two WARNINGs, green after.
- `test_spot_stream_over_an_idle_connection_unwinds_within_the_drain`, `test_futures_stream_over_an_idle_connection_unwinds_within_the_drain`: one stream task cancelled while the loop keeps running; red before (10 s library wait), green after.
- `test_cancelling_a_stream_ends_its_task_as_cancelled`: the supervisor propagates cancellation.

Mutation-checked: removing either `stop_read_loop` call, the timeout bound, or the supervisor's re-raise turns exactly one test red each.

## Verification

- Engine fix: with engine `934b830`, sanity (35) and integration (292) passed and printed neither `Task was destroyed but it is pending!` nor `Unclosed client session`.
- Second cause: the four tests above green; `tests/unit/modules/trading/adapters/binance` and `tests/unit/architecture` green; the commit tier (`ci-local.ps1 -SkipTests`) green with a clean log.
- Positive proof the new path ran, in the runtime test's log: `User data stream AsyncClient connection closed.` and `SpotUserDataStream task was cancelled.`, the two lines the owner's log lacked.
- Not run: a live Mainnet shutdown (no orders or mainnet traffic from this session). The owner's next stop of the desktop app should show both lines and neither WARNING.

## Same pattern elsewhere

`binance_websocket_service.py` (kline stream) has the same `close_connection()` in its `finally`; it is fast in practice because candles arrive every second, and was clean in the owner's log. Left unchanged: a different module, and no failure observed.
