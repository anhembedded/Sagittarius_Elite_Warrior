# BUG-143 — Stopping the app with the Spot user-data stream live leaves its tasks pending and its HTTP session unclosed

- **Reported:** 2026-10-04 (the user's `-TestnetOnly` run on `master-warrior` `e5ca8226`, pasted in chat)
- **Severity:** 🟢 P3. No order or state is lost; the process prints asyncio and aiohttp warnings at shutdown, and the stream's connection is dropped rather than closed.
- **Status:** Open
- **Board:** Stopping the app with the Spot user-data stream live prints `Task was destroyed but it is pending!` and `Unclosed client session`: the stream's tasks are destroyed while cancelling, so its connection is dropped, not closed. Seen in the user's first live grid round trip. Cause: the engine's `AsyncRuntime.stop()` stopped the loop before cancelling tasks. Fixed in the engine (`934b830`, engine `BUG-017`) and pinned by `engine.ref`; awaiting a live run that stops cleanly. Waiting on: User's `-TestnetOnly` run (`EPIC-029H`).
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

## Regression test

In the Engine, `tests/runtime/test_async_runtime_stop_drains_tasks.py`. Its first two tests were red on `ea2d330c` with the reproduction's symptom:

- a cancelled task's awaited `finally` runs before `stop()` returns;
- a task `stop()` cancels itself runs its cleanup too;
- a task that ignores cancellation is named, and `stop()` returns within its timeout;
- `App.stop()` leaves the loop closed;
- `stop()` called from the loop thread does not wait on its own loop.

No test in this repository reaches the live websocket, for the reason the reproduction gives: a fake server without the websocket cannot reach it (`test_dev_board_f9_against_fake_server.py`'s docstring).

## Verification

- With engine `934b830` installed, this repository's sanity tier passed (35) and its integration tier passed (292). Neither run printed `Task was destroyed but it is pending!` or `Unclosed client session`.
- The one `ResourceWarning: gc: 9 uncollectable objects at shutdown` in the sanity run also appears on `ea2d330c`, unchanged.
- **Not yet run:** a live run that stops the app with the Spot user-data stream open. This report stays Open until that run shuts down cleanly.

## Suggested next steps

- The user reruns `tests/testnet/test_grid_bot_round_trip.py` (`-TestnetOnly`) on a tree carrying this `engine.ref`, with the engine reinstalled. Close this report when the teardown prints none of the lines above.
