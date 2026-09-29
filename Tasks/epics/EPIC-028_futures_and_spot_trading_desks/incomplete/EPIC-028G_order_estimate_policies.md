# EPIC-028G — Max quantity, cost, fee and liquidation estimates are pure, tested domain policies

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟢 — pure functions; the risk is a wrong number shown as if exact
**Complexity:** S — four policies, no I/O
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028D](EPIC-028D_account_summary_reader.md), [EPIC-028F](EPIC-028F_commission_and_futures_account_controls.md)

---

## 1. Context and problem
- The screenshots show *Max buy*, *Cost*, *Estimated fee*, *Liquidation price*; no code computes any of them.

## 2. Acceptance criteria
- [ ] `max_order_quantity(available, price, leverage, fee_rate, step)` floors to the lot step and never exceeds what the available balance can pay including the fee.
- [ ] `order_cost` (Futures: initial margin = notional / leverage + fee; Spot: notional + fee) and `estimated_fee`.
- [ ] `estimated_liquidation_price` for isolated/cross one-way positions, returned with an `is_estimate=True` flag the UI must display.
- [ ] Every policy rejects NaN/inf/negative input and is mutation-verified (`testing-rule.md` §2).

## 3. Design
Pure functions over `Decimal` in `trading/contracts/` (reachable from UI and strategy, like `OrderQuantityRoundingPolicy`). Liquidation uses Binance's published maintenance-margin formula for the first bracket only, labelled estimate.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/order_estimates.py` | new |
| `tests/unit/modules/trading/contracts/test_order_estimates.py` | boundary values + mutation |

## 5. Testing
Unit, boundary value analysis, mutation-verified.
- Not run.

## Implementation notes (written when done)
Not started.
