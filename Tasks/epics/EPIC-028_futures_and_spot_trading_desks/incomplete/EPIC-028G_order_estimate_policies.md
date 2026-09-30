# EPIC-028G — Max quantity, cost, fee and liquidation estimates are pure, tested domain policies

**Status:** 🟡 Implemented — awaiting review
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟢 — pure functions; the risk is a wrong number shown as if exact
**Complexity:** S — four policies, no I/O
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028D](../completed/EPIC-028D_account_summary_reader.md), [EPIC-028F](../completed/EPIC-028F_commission_and_futures_account_controls.md)

---

## 1. Context and problem
- The screenshots show *Max buy*, *Cost*, *Estimated fee*, *Liquidation price*; no code computes any of them.

## 2. Acceptance criteria
- [x] `max_order_quantity(available, terms, step)` floors to the lot step and never exceeds what the available balance can pay including the fee. `terms` is `OrderTerms(price, leverage, fee_rate)`: five inputs would exceed the four-argument limit (`code/quality.md` §7).
- [x] `order_cost` (Futures: initial margin = notional / leverage + fee; Spot: notional + fee, as leverage 1) and `estimated_fee`.
- [x] `estimated_liquidation_price` for isolated/cross one-way positions, returned as `LiquidationPriceEstimate`, whose `is_estimate` is always `True` for the UI to display.
- [x] Every policy rejects NaN/inf/negative input and is mutation-verified (`testing-rule.md` §2).

## 3. Design (as built)
- **One set of formulas for both venues.** `contracts/order_estimates.py` holds `OrderTerms`, `estimated_fee`, `order_cost` and `max_order_quantity`. Spot is leverage 1, so the Spot numbers come from the same code ("share what can be shared", ADR D1). They live in `contracts/`, beside `OrderQuantityRoundingPolicy`, so the desks and `strategy` can reach them.
- **Conservative by design.** The fee is always counted in the quote asset. On a Spot buy the fee is actually taken from the base asset received, so the Spot maximum reads at most one fee low. That is the safe side: a maximum that is too high is rejected by the exchange. The fee rate is the taker rate, and a negative rate is refused, because a maker rebate is never promised in advance.
- **The liquidation estimate** (`contracts/liquidation_estimate.py`) uses Binance's one-way formula for a single position: `LP = (WB + cum − side × Q × EP) ÷ (Q × MMR − side × Q)`. The margin is the isolated margin, or for cross the wallet balance. The bracket's `maintenance_margin_rate` and `maintenance_amount` are inputs: brackets are not read yet, so a caller passes the first bracket. A long backed by at least its notional has no liquidation price (`price is None`; Binance shows `--`).
- **One place for the input checks.** `contracts/estimate_inputs.py` holds the three checks (finite, not negative, positive) that every estimate uses.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/order_estimates.py` | new: `OrderTerms`, fee, cost, maximum |
| `src/modules/trading/contracts/liquidation_estimate.py` | new: `LiquidationTerms`, `LiquidationPriceEstimate`, the formula |
| `src/modules/trading/contracts/estimate_inputs.py` | new: the shared input checks |
| `tests/unit/modules/trading/contracts/test_order_estimates.py`, `test_liquidation_estimate.py` | boundary values, properties, refusals |
| `Docs/VOCABULARY/README.md` | the Order estimate row |

## 5. Testing
- **Boundary values for the maximum:**
  - a balance paying exactly the maximum's cost;
  - one a hair short, which buys one step less;
  - zero, and one step that does not fit.
- **The maximum's defining property:** over four sets of terms, the maximum's cost fits and one more step does not. This is checked instead of hand-worked figures (`pitfalls/tests.md` #1).
- **Liquidation, checked against its definition:** at the estimate, the margin plus unrealised PnL equals the maintenance margin. This covers long and short, thin margin and a maintenance amount. It is cross-checked against Binance's isolated closed forms.
- **Boundary cases for liquidation:** margin equal to the notional and margin above it both give no price.
- **Refusals:** NaN, infinity, negative values, a zero price, step or quantity, leverage 0, and a maintenance rate of 1 or below 0.
- **Mutation check:** 22 targeted mutations, all killed. The first pass left one survivor (`price > 0` against `>= 0`); the margin-equals-notional case now covers it.

## Implementation notes
- **No screen shows these yet.** The order-entry panel (`EPIC-028H`, `028I`) is the first consumer. It reads the rates from `GetCommissionRateQuery` and the balance from the account summary.
- **The leverage brackets are still an input.** `IFuturesAccountControl` names `GET /fapi/v1/leverageBracket` as its next read, and until then a caller passes the first bracket.
- **Scope of the liquidation estimate.** It sees one position. Under cross margin the exchange's figure also counts the other positions' maintenance margin and unrealised PnL, which is why the type always says "estimate".
