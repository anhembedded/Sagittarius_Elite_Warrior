# BOT-145 — User-data-stream handlers stop blocking the asyncio event loop on REST calls

**Status:** 🔵 Backlog
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
- [ ] Neither stream's `_handle_message()` path blocks the event loop for longer than a negligible dispatch cost; the REST call itself runs off-loop (e.g. `asyncio.to_thread`).
- [ ] A concurrent `stream.recv()` await is not starved by an in-flight equity/position refresh (test: a slow-to-return fake account reader/client does not delay a second queued message's dispatch).
- [ ] No behavior change to *what* gets fetched or reported — same equity/position values, same events — only *where* the blocking call runs.

## 3. Design
{To be filled at implementation: likely `await asyncio.to_thread(self._account_reader.check_connection)` / `await asyncio.to_thread(self._trading_client.get_positions, symbol)` at each call site, keeping `_handle_message` itself synchronous (called from the loop) but making its two blocking sub-calls async-aware. Shared reasoning belongs in one place if a third stream is ever added — evaluate whether a small shared helper in a common base/module pays for itself with only two call sites (`architecture-rule.md` §7.2.1: don't build the third case pre-emptively).}

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/futures_user_data_stream.py` | `_handle_account_update`'s `get_positions()` call moves off the event loop |
| `src/modules/trading/adapters/binance/spot/spot_user_data_stream.py` | `_refresh_equity`'s `check_connection()` call moves off the event loop |

## 5. Testing
- Unit: a fake account reader/trading client whose call blocks (a short `time.sleep` under a real thread) does not delay a concurrently-queued second message's dispatch, proven via `asyncio` timing assertions rather than a sleep-based race.
- Not run yet — this task is backlog only.
