# EPIC-028B — Every order, cancel, enable, emergency stop and arm names the venue it acts on

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🔴 — the safety gates move from a global venue to a per-command venue; a missed call site is an order on the wrong exchange
**Complexity:** L — every trading handler, `OrderSubmissionService`, strategy arming
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028A](EPIC-028A_venue_context_and_registry.md)

---

## 1. Context and problem
- `ExecuteOrderCommand` (`application/orders/execute_order/command.py`) carries `order_request`,
  `live`, `owner_id` — no venue; the handler uses the one bound `ITradingClientFactory`.
- Cancel, Enable/Disable trading, Emergency Stop, Arm/Disarm handlers resolve single-venue ports;
  one armed strategy per process (`disarm_strategy/command.py`).

## 2. Acceptance criteria
- [ ] `ExecuteOrderCommand`, cancel one / cancel all, `EnableTradingCommand`, `DisableTradingCommand`, `EmergencyStopCommand`, `ArmStrategyCommand`, `DisarmStrategyCommand`, `GetOpenPositionsQuery`, `GetHoldingsQuery`, `GetExchangeConnectionStatusQuery` each carry `venue: TradingVenue` (no default).
- [ ] With both venues enabled, Emergency Stop on Futures leaves Spot's session, orders and baseline untouched, and vice versa (test).
- [ ] One strategy can be armed per venue at the same time; arming on Spot still refuses SHORT-capable strategies (EPIC-027N) and Futures still allows them.
- [ ] `supports_order_submission`, trading limits and the Spot baseline are checked against the command's own venue.
- [ ] The Phase-1 single-venue shim from `EPIC-028A` is deleted; an architecture guard fails if any trading handler resolves a venue-specific port directly instead of through `IVenueContexts`.

## 3. Design
Handlers take `IVenueContexts` and call `contexts.get(command.venue)` once at the top — the Resolve-once pattern `EmergencyStopCommandHandler` already uses for `TradingVenue.market_type`. `OrderSubmissionService` gains a `venue` argument. The Dev Board keeps working by passing its configured venue.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/**/command.py`, `query.py`, `handler.py` | `venue` field; resolve context |
| `src/modules/trading/application/orders/order_submission_service.py` | `venue` argument |
| `src/modules/strategy/…/arm_strategy`, `disarm_strategy` | one arming slot per venue |
| `src/modules/trading/ui/**` | callers pass their venue |
| `tests/unit/architecture/` | guard: handlers only reach venue ports via `IVenueContexts` |

## 5. Testing
Unit per handler (right context used, other untouched); integration: both venues on the fake exchange, Emergency Stop isolation.
- Not run.

## Implementation notes (written when done)
Not started.
