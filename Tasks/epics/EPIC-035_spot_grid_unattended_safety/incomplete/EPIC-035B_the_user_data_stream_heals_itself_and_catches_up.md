# EPIC-035B — The user-data stream heals itself and catches up

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, findings H2 and H3 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 1 approved the same day (D1).
**Risk:** 🔴 — this stream is the only source of fills; without it the ladder freezes with real orders resting
**Complexity:** L — retry policy and handle lifecycle in an adapter, a health event, a periodic and a post-reconnect reconcile, a HALT rule
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), extended by this task
**Depends on:** None

---

## 1. Context and problem
**H3 (the stream ends for good), verified ✅ on `3bbe243` by reading the code:**
- `src/modules/trading/adapters/binance/spot/spot_user_data_stream.py:148-189` (`_run_stream`): the inner `try` catches `asyncio.CancelledError` and `(OSError, ReadLoopClosed)`. Any other exception propagates out of the loop, through `finally` (which closes the client), and ends the task.
- `_task_handle` is set in `start()` (line 121) and cleared only in `stop()` (line 139). When the task ends by itself the handle stays set, so `start()` (line 114) answers "already running" and returns `False` for good. Nothing observes the dead task.
- **Not reproduced here:** the audit says python-binance 1.0.37's `KeepAliveWebsocket` raises `ValueError` from its subscribe step (`binance/ws/keepalive_websocket.py:66-75`) and `BinanceWebsocketUnableToConnect` on a failed connect. The library is not installed in this session's environment (`requirements.lock:132` pins `python-binance==1.0.37`), so those two exception types are *the audit's reading of the library*, not something re-checked. The defect does not depend on them: **any** exception outside the two caught types ends the task, and an API error while creating the client (outside the loop, line 163) does as well. The task's first step is to read the library source at the pinned version and record the exception types it raises.

**H2 (fills missed in a gap are never fetched), verified ✅ by the absence of any catch-up:**
- After `OSError` / `ReadLoopClosed` the loop sleeps `_RECONNECT_DELAY_SECONDS` and reopens `bsm.user_socket()`, with no query of order history, so a fill or an order end during the gap never reaches the executor.
- `GridReconciler` (`src/modules/bots/application/services/grid_reconciler.py`) holds the missed-fill logic, but it runs only for RECOVERING, from `GridExecutor._apply_switch` (`grid_executor.py:318`) when the trading session opens, and on resume. Binance cuts every websocket at 24 h, so the gap is routine.

**Futures:** `src/modules/trading/adapters/binance/futures_user_data_stream.py:261` has the same `except (OSError, ReadLoopClosed)` and the same handle lifecycle (lines 182, 211). The Spot task fixes the mechanism; this task checks Futures and either shares the fix or files a bug with the evidence (the Futures grid is `EPIC-029K`, out of scope).

## 2. Acceptance criteria
- [ ] Any exception (except cancellation) inside the stream loop, and any failure while creating the client or the socket, is caught at the loop, logged once per attempt without the secret or a signed URL, and retried with exponential backoff and a cap (the constant and its jitter are named and tested). `_RECONNECT_DELAY_SECONDS` stops being a fixed delay.
- [ ] When the task ends for any reason other than `stop()`, `_task_handle` is reset, so `start()` works again; `is_running` reports what is true.
- [ ] The stream publishes a **health event** (a `BaseEvent` subclass in the trading contracts: connected, reconnecting, down since T) that the bots module can subscribe to without importing the adapter.
- [ ] After **every** reconnect, the bots module reconciles each running bot's ladder against the exchange's open orders and recent trades, reusing `GridReconciler`'s missed-fill logic, so a fill missed in the gap places its counter order. The same reconcile runs periodically while the stream is up (the interval is a named constant).
- [ ] The reconcile after a reconnect is idempotent: running it when nothing was missed changes nothing and places nothing (an order already adopted or already countered is not placed twice; the client order id scheme guarantees it).
- [ ] If the stream has been down longer than N seconds (named constant, with a default recorded here), every bot holding orders on that venue goes HALTED with a named reason (for example `USER_STREAM_DOWN`), through `GridTaskGuard`, so the ladder is parked.
- [ ] A stream that comes back after a HALT does not resume the bot by itself.
- [ ] Futures: either the same fix lands in `futures_user_data_stream.py` under the same tests, or `Tasks/bug_report/` gets a bug report per `create-bug-report-rule.md` naming the mechanism, and this task records its ID.

## 3. Design
- **Pattern:** a supervisor loop with exponential backoff and a state-machine for connection health is the vetted shape (the library's own reconnect is bounded to 5 attempts, which is why `ReadLoopClosed` exists). The existing loop already fences by generation (`BUG-094`); keep the fence, change what the loop catches and what it does after the exit.
- **Lifecycle cohesion (`code/quality.md`, FSM lifecycle cohesion):** the stream's states (STOPPED, CONNECTING, CONNECTED, RECONNECTING, DOWN) are an explicit small state set emitted by the one class, not booleans spread over `start`, `stop` and the loop. The handle is cleared in one place: a `finally` of the spawned coroutine, guarded by the generation so a superseded task never clears a newer one's handle.
- **Catch-up lives in the bots module, not the adapter:** the adapter publishes `UserStreamHealthEvent`; a bots event handler turns "connected after a gap" into `executor.reconcile_after_gap()`, which posts one task onto the executor's queue. That task calls the reconciler in a **read-only-plus-counter** mode: adopt resting orders, replay fills from order history by client order id, place the missing counter orders, never cancel a healthy order. A mismatch it cannot resolve HALTs (existing behaviour) rather than guessing.
- **Periodic reconcile** shares the same entry point and the same guard; the timer is an application service with an injected clock, not a sleep.
- **Why not poll instead of streaming:** polling at the needed frequency spends the REST weight budget (`EPIC-035D`); the stream stays primary, the reconcile is the safety net, as `GridReconciler` already is on restart.
- **Secrets:** nothing new is logged; the client is created with the credentials resolver as today (`BUG-180`'s sanitiser, `EPIC-035O`, covers URLs).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/spot/spot_user_data_stream.py` | Catch-all with backoff; reset the handle on exit; publish health |
| `src/modules/trading/contracts/` (a new `user_stream_health_event.py`) | The health event, inheriting `BaseEvent` |
| `src/modules/trading/adapters/binance/futures_user_data_stream.py` | Same fix, or a filed bug |
| `src/modules/bots/application/event_handlers/` (new handler) | Health event → `reconcile_after_gap`; down longer than N s → HALT |
| `src/modules/bots/application/services/grid_reconciler.py`, `grid_executor.py` | A gap-mode entry point reusing the missed-fill logic; a periodic task |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | The journeys "the connection drops" and "the stream is down too long" |
| `tests/unit/modules/trading/adapters/binance/spot/test_spot_user_data_stream.py`, `tests/unit/modules/bots/**`, `tests/integration/modules/**` | The tests named in §5 |

## 5. Testing
| Criterion | Test | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Any exception is retried | `test_spot_user_data_stream.py::test_a_value_error_from_the_socket_is_retried_with_backoff` — red before: the task ends and nothing retries | Unit, with a fake `BinanceSocketManager` raising `ValueError`, `BinanceWebsocketUnableToConnect` and an API error in turn | The stream reconnects after the backoff; the delays grow and are capped |
| Handle reset | `test_a_stream_that_died_can_be_started_again` — red before: `start()` returns `False` forever | Unit | `start()` returns `True` after the task ended by itself |
| Handle not clobbered | `test_a_superseded_task_never_clears_a_newer_handle` | Unit | The newer handle survives |
| Health event | `test_the_stream_publishes_connected_reconnecting_and_down` | Unit | The event sequence matches the transitions |
| Catch-up after reconnect | `tests/unit/modules/bots/application/services/test_grid_reconciler_gap.py::test_a_fill_missed_in_the_gap_places_its_counter_order` — red before: no catch-up path | Unit | One counter order placed |
| Idempotent | `test_a_reconcile_with_nothing_missed_places_nothing` | Unit | No new order |
| Down too long | `test_a_stream_down_past_the_limit_halts_bots_and_parks_the_ladder` | Unit with a fake clock | HALTED, `USER_STREAM_DOWN`, tagged orders cancelled |
| No auto-resume | `test_a_stream_that_returns_does_not_resume_a_halted_bot` | Unit | Still HALTED |
| Journey | integration: fake Binance server drops the socket, fills an order during the gap, the socket returns | Integration | The counter order exists |
| Futures | the same unit tests on `futures_user_data_stream.py`, or the bug report's ID | Unit / doc | Per the chosen branch |

Required first step, recorded in Implementation notes: the exception types raised by python-binance 1.0.37, read from its source. Not run yet.

## Resume
Not started. First action: read python-binance 1.0.37's `ws/keepalive_websocket.py` and write the first red test against `_run_stream`.
