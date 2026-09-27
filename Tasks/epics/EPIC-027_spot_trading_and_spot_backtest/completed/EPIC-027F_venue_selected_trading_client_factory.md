# EPIC-027F — Every order-path handler gets its trading client from one venue-selected factory

**Status:** ✅ Done (2026-09-27)
**Source:** found while measuring the Spot gap, 2026-09-26. It is a prerequisite for the user's *"giao dịch spot"* ("trade spot").
**Risk:** 🔴 — touches the live order path (execute, cancel, enable, emergency stop, positions, user data stream).
**Complexity:** M — six call sites move to one port. Pure refactor, no behavior change.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** None. Coordinate with `EPIC-026P`, which needs the same factory parameter for mainnet Futures.

---

## 1. Context and problem
- `ITradingClient` is bound in DI (`src/modules/trading/module.py:312-322`), but the binding is
  effectively bypassed. Six places construct `FuturesTradingClient(...)` directly:
  - `application/orders/execute_order/handler.py:159`
  - `application/orders/cancel_order/handler.py:80`
  - `application/session/enable_trading/handler.py:113`
  - `application/session/emergency_stop/handler.py:118`
  - `application/queries/get_open_positions/handler.py:60`
  - `adapters/binance/futures_user_data_stream.py:233`
- A second market cannot be added through composition. Every handler would have to be edited
  again, and again for mainnet (`EPIC-026P`). This is the closed-design tell in
  `architecture-rule.md` §7.2.1.

## 2. Acceptance criteria
- [x] A factory port (`ITradingClientFactory.create(mode) -> ITradingClient`) is the only
      way the application layer gets a trading client. `grep "FuturesTradingClient("` in
      `src/modules/trading/application/` returns nothing. (No `venue` parameter on `create()` —
      see §3's design note on why venue selects the *factory implementation*, not an argument to it.)
- [x] The Futures implementation of the factory produces exactly what the six sites produced before.
      The existing order-path tests and the fake-server integration tests pass unchanged.
- [x] An architecture guard fails if an application-layer file constructs an adapter client directly.
- [x] `tests/unit/architecture/test_order_submission_mode_live_is_restricted.py` still holds: `LIVE`
      mode is still allowed in the same two places only.

## 3. Design
- Named pattern: Abstract Factory behind a port (`architecture-rule.md` §2, DI over hard-coded
  construction).
- **Design deviation from the task's original sketch:** `create()` takes only
  `OrderSubmissionMode`, not `(venue, mode)`. Venue selection happens by which *concrete factory* is
  bound in `adapter_bindings.py` (`FuturesTradingClientFactory` today), not by an argument passed at
  call time — the composition root already decides venue once, at boot, the same way it already
  decides every other Futures-only adapter; a `venue` parameter on `create()` would let a caller
  request a venue the container never wired, an invalid state `code/errors.md` §8 says to keep
  unrepresentable. `OrderSubmissionMode` stays a call-time parameter because it is genuinely
  call-site-specific (`VALIDATE_ONLY` for reads, `LIVE` for the two real submission paths), unlike
  venue. `EPIC-027K` adds a Spot row by binding a second `ITradingClientFactory` implementation
  behind the same venue-selection decision `TradingModule`/`adapter_bindings.py` already make
  elsewhere (§7.2.1: the seam now, the variant later).
- Behavior-preserving; one PR. No Spot code lands here.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_trading_client_factory.py` | new port |
| `src/modules/trading/adapters/binance/futures_trading_client_factory.py` | Futures implementation (file named for the venue it serves, matching `futures_session_factory.py`/`futures_account_reader.py`'s own naming, not the task's original `trading_client_factory.py` sketch) |
| the six sites above | resolve the factory instead of constructing the client |
| `src/modules/trading/composition/adapter_bindings.py` | binds `ITradingClientFactory` unconditionally (several handlers must stay constructible while trading is disabled) |
| `src/modules/trading/module.py` | `_bind_trading_client_if_enabled` now resolves the factory instead of constructing `FuturesTradingClient` itself |
| `scripts/epic021h_user_stream_probe.py` | updated to the new `FuturesUserDataStream` constructor shape (found via mypy, not the original grep — it lives under `scripts/`, outside the six `application/`+`adapters/` sites) |
| `tests/unit/architecture/test_only_the_factory_constructs_futures_trading_client.py` | new guard: only the factory may construct `FuturesTradingClient`, scanning `src/`+`scripts/` |
| `tests/unit/architecture/scanned_roots_registry.py` | registry row for the new guard |
| six `tests/unit/modules/trading/...` test files | updated to build a real `FuturesTradingClientFactory` from the same mock collaborators, instead of passing them to the handler directly (`pitfalls/source.md` #3 — the class discovered this pass was `scripts/epic021h_user_stream_probe.py`) |

## 5. Testing
- `tests/unit/modules/trading` — 794 passed (was 730 passed / 64 failed on the first run after the
  refactor, all failures old constructor signatures in test fixtures; fixed per §4's last row).
- `tests/unit/architecture` — 451 passed, including the new guard and its own
  `test_guard_actually_detects_a_violation` mutation test.
- `tests/unit` (full) — 5626 passed.
- `tests/sanity` — 32 passed.
- `ruff check src tests tools scripts` — all checks passed. `ruff format --check` — all formatted.
- `mypy` over `src`+`scripts` — Success: no issues found in 713 source files (caught the
  `futures_user_data_stream.py` `credentials_provider` dual-use and the probe script's stale call
  site before any test run did).
- Guard mutation: `test_guard_actually_detects_a_violation` (in the new guard file itself) proves the
  scanner fires on a real violation shape and ignores a type-annotation-only import — verified
  passing as part of the 451-test architecture run above.
