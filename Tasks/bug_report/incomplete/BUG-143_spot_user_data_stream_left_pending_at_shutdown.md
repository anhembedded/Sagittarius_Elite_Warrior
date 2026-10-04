# BUG-143 — Stopping the app with the Spot user-data stream live leaves its tasks pending and its HTTP session unclosed

- **Reported:** 2026-10-04 (the user's `-TestnetOnly` run on `master-warrior` `e5ca8226`, pasted in chat)
- **Severity:** 🟢 P3. No order or state is lost; the process prints asyncio and aiohttp warnings at shutdown, and the stream's connection is dropped rather than closed.
- **Status:** Open
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (run a Grid bot on Spot) → `src/modules/trading/` → `adapters/binance/spot/spot_user_data_stream.py`, and the engine's `AsyncRuntime` stop order
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

Not yet established. The suspicion is that each task is in state `cancelling` when destroyed: the cancel reached it, but the event loop stopped before the task could run its cancellation, so `_run_stream`'s `finally` (`spot_user_data_stream.py`, `await client.close_connection()`) never ran. Whether the stop order lives in the stream's `stop()` (not awaiting its task) or in the engine's `AsyncRuntime` shutdown (stopping the loop without draining cancelled tasks) is not yet read.

## Fix

Pending.

## Regression test

Pending. It needs a tier where the stream's task really runs on the runtime's loop and the app is stopped; a fake server without the websocket cannot reach it (`test_dev_board_f9_against_fake_server.py`'s docstring records that limit).

## Verification

Not run.

## Suggested next steps

- Read `SpotUserDataStream.stop()` and the engine's `AsyncRuntime` stop path, and establish which side drops the cancelled task.
- Check whether `FuturesUserDataStream` has the same shape; the user's Futures key is rejected today, so no live run shows it.
- If the engine side owns it, the fix is an Engine change, which needs separate confirmation (`ONBOARDING.md` §2).
