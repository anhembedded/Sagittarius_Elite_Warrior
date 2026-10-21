# BUG-263 — A host stop prints `Unclosed client session` after "App stopped"

- **Reported:** 2026-10-21 (the owner's VPS output of `sudo sew-update`, relayed by coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`)
- **Severity:** 🟢 P3 — a leaked HTTP session at process exit; no order or money affected, but it is a resource the app opened and did not close
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** A stream cancelled while its `AsyncClient.create` was awaiting the ping left the `aiohttp` session open, because the library closes it only for `Exception`, not for the `CancelledError` of a host stop; the three streams now create their client through `create_closing_on_cancel`, which finishes the creation and closes the client.
- **Context:** Host stop → trading (`src/modules/trading/adapters/binance/`) user-data streams, market data (`src/modules/market_data/adapters/binance/`) kline stream → `src/support/binance_gateway/adapters/`
- **Environment:** Owner's VPS host, 2026-10-21 21:03:31 (+07), `sew-update`. Which stream held the session is not in the output.

## Reproduction
Output at the host's stop:
```
2026-10-21 21:03:31,699 - App.UserDataStream - INFO - FuturesUserDataStream task was cancelled.
2026-10-21 21:03:31,702 - App - INFO - AsyncRuntime event loop stopped.
2026-10-21 21:03:31,702 - App - INFO - App stopped.
Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x7fc5dd7f23c0>
```
Reproduced on the library: `AsyncClient.create(...)` cancelled while its ping is pending, then collected, prints the same two lines (`test_the_library_alone_leaks_the_session_of_a_cancelled_creation`). That the owner's session was this one is inferred, not observed: the only `aiohttp` sessions in the app are python-binance `AsyncClient`s, and `AsyncClient.create` is the one place whose cleanup does not cover cancellation.

## Symptom
See above. The gate scans for `ResourceWarning` but runs the streams against a mock client (`tests/sanity/fake_exchange/stream_transport.py`), never a real `aiohttp` session, so nothing saw it.

## Root cause
`AsyncClient.create` (python-binance, `async_client.py`) constructs the client, whose `__init__` opens the session, then awaits `ping()` and `get_server_time()` inside `try ... except Exception: await self.close_connection(); raise`. `CancelledError` is a `BaseException`, so a task cancelled there skips the cleanup and the caller, still awaiting `create`, holds no reference to close. The three call sites (`futures_user_data_stream.py` and `spot_user_data_stream.py` `_run_session`, `binance_websocket_service.py` `_run_stream`) closed the client only in a `finally` that runs after `create` returned. A Stop opens the order session to cancel a bot's orders, which starts the user stream; a host stop a moment later cancels that stream inside the ping.

## Fix
`create_closing_on_cancel` (`src/support/binance_gateway/contracts/closing_on_cancel.py`) passes the library its own `aiohttp` connector as `session_params` and closes it on any exit before the client is returned (a cancel included); a session is closed exactly when its connector is (`ClientSession.closed`), so nothing is left to warn. After the client is returned the session owns the connector. A first version ran the creation as a shielded helper task and waited for it; review round 1 found `AsyncRuntime._drain` cancels every task, the helper's included, so it leaked at host stop, and it was replaced. The three streams use it. `tests/unit/architecture/test_async_clients_are_created_closing_on_cancel.py` fails on any use of `AsyncClient.create` outside the helper.

## Regression test
The real library's `AsyncClient` with only its ping held back (no network), the session read from the session itself (`tests/aiohttp_sessions.py`): `test_a_cancelled_client_creation_leaves_no_session.py` (the helper, including the real `AsyncRuntime.stop()` drain), `test_a_stream_cancelled_while_connecting_leaves_no_session.py` (Spot and Futures), and the market-data counterpart. Red before: each stream test leaves one open session; green after.

## Verification
Targeted unit tiers and `tests/unit/architecture` locally; the full gate is GitHub Actions'. Not done: the boot-the-real-composition-against-a-local-stub test the coordinator asked for; the sanity tier's client is a mock by design (`testing-rule.md` §1), so a real-client boot is a new harness, not a guard, and the per-site tests plus the architecture scan cover the mechanism found. Not verified: that this was the owner's leaked session (see Reproduction).
