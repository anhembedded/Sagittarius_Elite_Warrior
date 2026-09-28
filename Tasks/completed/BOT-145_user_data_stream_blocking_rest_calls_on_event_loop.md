# BOT-145 — User-data-stream handlers stop blocking the asyncio event loop on REST calls

**Status:** ✅ Done (2026-09-28)
**Source:** Independent PR review, PR #285 (`EPIC-027L`), 2026-09-27 — "Should fix" finding, not blocking that PR: *"`_refresh_equity` runs blocking synchronous network I/O directly on the stream's asyncio event loop."*
**Risk:** 🟡 — a fill/account-update event delays processing of the next queued websocket message (and anything else sharing the loop) for as long as the blocking REST round trip takes; does not corrupt data, degrades responsiveness under load.
**Complexity:** S — one wrapping call per affected handler, no design change.
**Depends on:** None

---

## 1. Context and problem
Both `FuturesUserDataStream._handle_account_update()` (`futures_user_data_stream.py:344-386`) and the new `SpotUserDataStream._refresh_equity()` (`spot_user_data_stream.py:242-268`, `EPIC-027L`) call a synchronous, `requests`-backed port method directly from `_handle_message()`, itself called from `_run_stream()`'s async read loop:
- Futures: `self._trading_client.get_positions(symbol)`.
- Spot: `self._account_reader.check_connection()` — several blocking calls (`ping`, `get_server_time`, `get_account`, one `get_symbol_ticker` per non-dust holding).

Neither is wrapped in `asyncio.to_thread` or run on an executor, so each call blocks the same event loop driving `stream.recv()` for its full duration. Both docstrings note this fires on every fill on an active session. The Futures instance of this predates `EPIC-027L`; `EPIC-027L` extended the same shape to a second venue rather than introducing it, per `fix-bug-rule.md` §1 ("never patch only the single call site reported when the same defect can recur elsewhere — move shared logic up to the one layer that serves every consumer").

## 2. Acceptance criteria
- [x] Neither stream's `_handle_message()` path blocks the event loop for longer than a negligible dispatch cost; the REST call itself runs off-loop (e.g. `asyncio.to_thread`).
- [x] A concurrent `stream.recv()` await is not starved by an in-flight equity/position refresh (test: a slow-to-return fake account reader/client does not delay a second queued message's dispatch).
- [x] No behavior change to *what* gets fetched or reported — same equity/position values, same events — only *where* the blocking call runs.

## 3. Design
`_handle_message()` and its two blocking sub-calls (`_handle_account_update` on Futures,
`_refresh_equity` on Spot) all became `async def`, with the blocking REST call itself wrapped in
`await asyncio.to_thread(...)` — exactly the shape sketched above. `_run_stream()`'s own call site
(`await self._handle_message(res)`) is the only other change; `_handle_order_trade_update`/
`_handle_execution_report` (no blocking call) stayed synchronous, called plainly from the now-async
`_handle_message`. No shared helper: only two call sites, each a one-line wrap
(`architecture-rule.md` §7.2.1 — do not build for a third case that does not exist).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/futures_user_data_stream.py` | `_handle_message`/`_handle_account_update` are now `async def`; `get_positions()` call wrapped in `asyncio.to_thread` |
| `src/modules/trading/adapters/binance/spot/spot_user_data_stream.py` | `_handle_message`/`_refresh_equity` are now `async def`; `check_connection()` call wrapped in `asyncio.to_thread` |
| `tests/unit/modules/trading/adapters/binance/test_futures_user_data_stream.py` | every `_handle_message` call site converted to `await` inside an `async def test_...`; new regression test |
| `tests/unit/modules/trading/adapters/binance/spot/test_spot_user_data_stream.py` | same conversion; new regression test with a `_SlowFakeTradingAccountReader` |

## 5. Testing
- `test_account_update_s_get_positions_call_does_not_stall_the_event_loop` (Futures) and
  `test_outbound_account_position_s_check_connection_does_not_stall_the_event_loop` (Spot): a
  concurrently-scheduled `asyncio.sleep(0.01)` coroutine finishes before a real, blocking
  `time.sleep(0.2)`-under-a-thread REST call does — proves the call runs off the loop, not merely
  that it eventually returns. Mutation-verified: reverting either `asyncio.to_thread` wrap makes its
  test fail (`['slow', 'quick']` instead of `['quick', 'slow']`), confirmed by temporarily reverting
  each fix and re-running.
- Full `tests/unit/modules/trading/adapters/binance/{,spot/}test_*user_data_stream.py`: 35/35
  passed — no existing routing/event/logging assertion changed behavior.
- Full `tests/unit/modules/trading` (980 tests) and `tests/unit/architecture` (464 tests, including
  the shrink-only god-file ratchet — `futures_user_data_stream.py` trimmed to 408 lines, under its
  409-line baseline): all passed.
- `ruff check`/`ruff format --check` on `src tests tools scripts`: clean.
- `mypy` at the real gate invocation (`src`/`scripts` only): unchanged at the 584-error baseline —
  `tests/` is outside its scanned paths.
