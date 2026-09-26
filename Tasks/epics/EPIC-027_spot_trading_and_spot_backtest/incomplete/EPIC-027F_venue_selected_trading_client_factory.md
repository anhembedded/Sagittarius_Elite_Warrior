# EPIC-027F — Every order-path handler gets its trading client from one venue-selected factory

**Status:** 🔵 Backlog
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
- [ ] A factory port (e.g. `ITradingClientFactory.create(venue, mode) -> ITradingClient`) is the only
      way the application layer gets a trading client. `grep "FuturesTradingClient("` in
      `src/modules/trading/application/` returns nothing.
- [ ] The Futures implementation of the factory produces exactly what the six sites produced before.
      The existing order-path tests and the fake-server integration tests pass unchanged.
- [ ] An architecture guard fails if an application-layer file constructs an adapter client directly.
- [ ] `tests/unit/architecture/test_order_submission_mode_live_is_restricted.py` still holds: `LIVE`
      mode is still allowed in the same two places only.

## 3. Design
- Named pattern: Abstract Factory behind a port (`architecture-rule.md` §2, DI over hard-coded
  construction). The factory owns the (venue → adapter) table. The Spot row is added by
  `EPIC-027K` as one entry, and the Futures-mainnet row by `EPIC-026P` as another (§7.2.1: the seam
  now, the variant later).
- Behavior-preserving; one PR. No Spot code lands here.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_trading_client_factory.py` | new port |
| `src/modules/trading/adapters/binance/trading_client_factory.py` | Futures implementation |
| the six sites above | resolve the factory instead of constructing the client |
| `tests/unit/architecture/` | guard against direct construction in `application/` |

## 5. Testing
- Existing unit, integration (fake server) and sanity tiers pass unchanged — this is the proof.
- Guard mutation: re-add one direct construction and the guard must go red.
- Not run yet.
