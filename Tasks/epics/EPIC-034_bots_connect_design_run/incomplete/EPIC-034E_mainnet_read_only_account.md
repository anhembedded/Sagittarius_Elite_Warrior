# EPIC-034E — A mainnet key is read, never traded: balances, fees and key permissions; withdrawal keys refused

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🔴 — the first code that talks to the real exchange with the owner's key
**Complexity:** M — a separate account source, a permission check, a guard
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-003](../../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md), extended by this task
**Depends on:** [EPIC-034D](EPIC-034D_connect_step.md)

---

## 1. Context and problem
The owner's milestone (decision D4): a mainnet key shows the owner's real account. `EPIC-026` D3 keeps the lock on trading, with no mainnet `TradingVenue`; its D6 was cancelled the same day. Today a mainnet key is rejected by the testnet with `-2015` (`BUG-167`).

## 2. Acceptance criteria
- [ ] A read-only mainnet `AccountSource` reads balances, commission, open orders and the key's restrictions; it shows as "Mainnet · read only" with the real balances.
- [ ] It is not a `TradingVenue`; an architecture guard fails if any import path from it reaches a trading session factory, a trading client or `execute_order`.
- [ ] Its credentials resolve from `BINANCE_MAINNET_READONLY_API_KEY` / `_SECRET` only; a testnet key is never read as a mainnet key and the reverse.
- [ ] A key whose restrictions allow withdrawals is refused with that reason (D5, once accepted); a key that can trade is accepted with advice to create a read-only key.
- [ ] The secret is never written to `secrets.local.json`: the keyring if D10 is accepted, the environment only otherwise.
- [ ] The owner sees their real balances with their own key (manual check).

## 3. Design
A new type beside the testnet venues, owning only `IVenueAccountReader`. Reuse the Spot and Futures readers' parsing; its session factory has no trading constructor. The permissions come from `GET /sapi/v1/account/apiRestrictions`. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/binance_gateway/` | read-only mainnet endpoints and credentials |
| `src/modules/trading/adapters/binance/` | the read-only source |
| `tests/unit/architecture/` | the no-order-path guard |
| `Docs/SPEC/SPEC-003*` | the mainnet read case |

## 5. Testing
Unit with the fake server: balances parsed, a withdrawal key refused, red first. The guard with a probe. Manual: the owner's key. A reviewer is required; ask the owner before any dependency change (D10). Not run.

## Implementation notes (written when done)
Not started.
