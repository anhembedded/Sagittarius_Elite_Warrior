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
- [x] The Futures maximum (`futures_max_quantity`) floors to the lot step and is never an order Binance refuses for margin or notional, given the balance, prices and headroom it is handed. Its cost is Binance's: initial margin at the assuming price plus open loss, with the taker fee on top.
- [x] The Spot maximum (`spot_max_buy_quantity`) floors to the lot step and never exceeds the quote balance for a limit buy.
- [x] `estimated_fee`, `futures_order_cost`, `spot_buy_cost`.
- [x] `estimated_liquidation_price` for isolated/cross one-way positions, returned as `LiquidationPriceEstimate`, whose `is_estimate` is always `True` for the UI to display.
- [x] Every policy rejects NaN/inf/negative input and is mutation-verified (`testing-rule.md` §2).

## 3. Design (as built)
- **Shared where the rules are shared, separate where they differ** (ADR D1). `contracts/order_estimates.py` holds what both venues share: `estimated_fee` and `largest_fitting_quantity`, which rounds through `OrderQuantityRoundingPolicy` and corrects the one-step boundary error a non-terminating quotient can cause. The cost and the maximum are per venue, because Binance's rules differ.
- **Futures follows Binance's published rules** (`contracts/futures_order_estimates.py`):
  - cost = initial margin + open loss;
  - initial margin = assuming price × quantity ÷ leverage. The assuming price is last × 1.0015 for a market order, the order's price for a limit long, and max(last × 1.0015, mark, order price) for a limit short;
  - open loss = quantity × |min(0, direction × (mark − order price))|;
  - the notional after the order may not exceed the bracket's limit. `FuturesOrderTerms.notional_headroom` is that limit less what is already open, and the maximum fits it at the higher of the assuming and mark prices.
  - The fee is added to the cost when sizing, so the maximum can read up to one fee below Binance's own, never above it.
- **Spot** (`contracts/spot_order_estimates.py`): a buy costs its notional plus the fee, both in the quote. Binance takes a Spot buy's fee from the base received, so the maximum reads at most one fee low. For a market buy the price is the caller's expectation (the best ask). A book that moves can still refuse it, and `EPIC-028H` should size market buys by quote amount (`quoteOrderQty`).
- **The fee rate is the taker rate.** A negative rate (a maker rebate) is refused, because a rebate is never certain before the fill.
- **The liquidation estimate** (`contracts/liquidation_estimate.py`) uses Binance's one-way formula for a single position: `LP = (WB + cum − side × Q × EP) ÷ (Q × MMR − side × Q)`.
  - It is exact for isolated margin.
  - For cross margin it is optimistic whenever other positions carry maintenance margin or losses: the real price is closer to entry.
  - The bracket's `maintenance_margin_rate` and `maintenance_amount` are inputs, because brackets are not read yet.
  - A long backed by at least its notional has no liquidation price (`price is None`; Binance shows `--`).
- **One place for the input checks.** `contracts/estimate_inputs.py` holds the three checks (finite, not negative, positive).
- **Placement.** All of it lives in `contracts/`, beside `OrderQuantityRoundingPolicy`, the same kind of payload-free sizing arithmetic. Its consumer is the order panel (`EPIC-028H`, `028I`).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/order_estimates.py` | new: the shared fee and step-fitting |
| `src/modules/trading/contracts/futures_order_estimates.py` | new: `FuturesOrderTerms`, assuming price, open loss, cost, fee, maximum |
| `src/modules/trading/contracts/spot_order_estimates.py` | new: `SpotOrderTerms`, buy cost, maximum |
| `src/modules/trading/contracts/liquidation_estimate.py` | new: `LiquidationTerms`, `LiquidationPriceEstimate`, the formula |
| `src/modules/trading/contracts/estimate_inputs.py` | new: the shared input checks |
| `tests/unit/modules/trading/contracts/test_order_estimates.py`, `test_futures_order_estimates.py`, `test_spot_order_estimates.py`, `test_liquidation_estimate.py` | worked examples, boundary values, properties, refusals |
| `Docs/VOCABULARY/README.md` | the Order estimate row |

## 5. Testing
- **Binance's worked example.** At 20× and 9 253.30, the limit long costs its initial margin, 462.66. The limit short costs initial margin 463.64 plus open loss 6.54, a total of 470.18.
- **Each rule branch.**
  - Each assuming-price branch.
  - Open loss on a long above the mark and on a short below it, and none on the other side or on a market order.
  - The fee at the assuming price.
- **The Futures maximum's defining property.** An independently transcribed copy of the FAQ is the oracle. The maximum's cost plus fee fits the balance and its notional fits the headroom, and one more step breaks one of the two. The cases are the PR #300 review's rejections:
  - a market order at 1×, 2× and 5×;
  - a long above the mark and a short below it;
  - 125× with and without a binding cap;
  - the cap measured at the mark, and at the buffered last.
- **Step fitting.** Exact and a-hair-short budgets both give the right quantity. So do the two rounding hazards, a quotient rounded up onto a step and one rounded down off a step, and the review's non-terminating budget.
- **Liquidation, checked against its definition.** At the estimate, the margin plus unrealised PnL equals the maintenance margin. Margin equal to or above the notional gives no price.
- **Refusals.** NaN, infinity, negative values, a zero price, step or unit cost, leverage 0, and a maintenance rate of 1 or below 0.
- **Mutation check.** 43 targeted mutations, all killed: 32 on the order estimates and 11 on the liquidation and input checks. The first pass left the two step-boundary corrections and the notional price surviving, and the cases above were added to kill them.

## Implementation notes
- **The review changed the design.** The first version (cost = notional ÷ leverage + fee) claimed to "err low, never high". The PR #300 review showed that the claim was false for Futures: it overshot at 1× and 2×, ignored open loss and ignored the bracket cap. The rewrite models Binance's own rules, above. They are transcribed from Binance's FAQ and not checked against a live order, because egress to Binance is blocked in the build environment.
- **No screen shows these yet.** The order-entry panel (`EPIC-028H`, `028I`) is the first consumer. It reads the rates from `GetCommissionRateQuery`, the balance from the account summary, and the headroom from `LeverageSetting.max_notional` less the open notional.
- **The leverage brackets are still an input.** `IFuturesAccountControl` names `GET /fapi/v1/leverageBracket` as its next read, and until then a caller passes the first bracket.
