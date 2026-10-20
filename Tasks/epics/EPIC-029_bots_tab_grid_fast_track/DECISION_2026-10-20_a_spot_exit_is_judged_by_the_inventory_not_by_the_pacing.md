# ADR — A Spot exit slice is judged by the owner's inventory, not by the pacing of placements

**Epic:** [EPIC-029](README.md)
**Date:** 2026-10-20
**Status:** Proposed — the owner's merge of the pull request that carries it ratifies it
**Decided by:** Pending: owner. The agent chose the mechanism at the delivery coordinator's request ([BUG-241](../../bug_report/completed/BUG-241_a_spot_stop_that_sells_in_several_slices_is_refused_by_the_order_budgets_spacing_and_rate.md)), but D1 revises the owner's 🟢 ADR D6 ("whatever the order's `purpose`") and changes which real-money orders the limits let through (ONBOARDING §7)
**Supersedes / superseded by (optional):** refines [`DECISION_2026-10-03_bots_module_and_grid_bot.md`](DECISION_2026-10-03_bots_module_and_grid_bot.md) D6 (§3.2 "The checks") and D21 (§3.4 "Exits")

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at `506de4a` and by a test red before the change |
| 🔵 Proposed | an option awaiting the owner; not accepted |

## 1. Context
- ✅ A Spot Stop that sells the base (`CLOSE_AT_MARKET`, a stop loss, a take profit) sends its slices one request after the other and takes no pacer turn, so that a stop never waits behind a neighbour's ladder (`BotOrderGateway._submit_paced`). Trading judged every slice by ADR D6's five checks "whatever the order's `purpose`": open orders, inventory, **spacing (250 ms)** and **rate (60 a minute)**.
- ✅ With the production limits the second slice, sent a request after the first, is refused `owner_budget_spacing` (or `owner_budget_rate` once the exit has more slices than the minute allows), and the bot halts `exit_slice_failed` with the rest of its base unsold (`BUG-241`: red on the strict fake, `HALTED ... 0.01598 unsold after slice 2: owner_budget_spacing`). A stop loss must never be refused by the bot's own order budget.
- ✅ The book is registered again at the start of every Stop, so the busy minute of the ladder does not carry into the exit; the failure is inside the exit's own slices.
- ✅ Futures already treats a reducing order this way (`EPIC-039L`): a reduce-only close or protective order answers to the exposure checks only and is still counted in the book (`TradingLimitPolicy._budget_checks`).

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | A budgeted owner's **SELL on a venue without reduce-only, sent as a close** (`OrderPurpose.CLOSE`) answers to ADR D6 check 3, the inventory (open sells plus this order within the inventory), and to the per-order notional cap; it skips the open-order count, the spacing and the rate. It is still recorded in the book and counts in the window. | Proposed | Pending: owner | A Spot exit of any number of slices is sent; a SELL can reduce nothing but the base the owner holds, which check 3 bounds, so it can add no exposure. |
| D2 | `ExecuteOrderCommand` admits that order as a close (`is_inventory_exit`): a **tagged market SELL** on a non-Futures venue (a resting order would stay on the book beyond the open-order cap, so a LIMIT is refused). A BUY, an untagged order and a protective order on Spot stay refused before the handler, as before. | Proposed | Pending: owner | The limits are never passed by an order that could grow exposure; the Spot mapper still never sends `reduceOnly`. |
| D3 | The bot sends its Spot exit slices with `OrderPurpose.CLOSE` (`BotOrderGateway.market_sell`). They stay unpaced. | Proposed | Pending: owner | One place decides what an exit is; the pacer is not asked to know about exits. |

## 3. Alternatives considered
- **Exits take a pacer turn ahead of placements.** Loses: a turn honours the rate window, so an exit made after a busy minute (or of many slices) waits up to a window; a stop loss that waits leaves the base held. It also needs a priority lane in a pacer shared by the venue's bots. Pattern: priority queue.
- **A reserve of the window kept free for exits** (the pacer stops placements `R` short of the rate). Loses: an exit can be as long as `inventory / cap` slices (20 or more), so the reserve wastes a third of the budget or still falls short.
- **Exempt every reducing order from the whole budget, counting nothing.** Loses: the budget would not know the exit orders (rate and book truth, `domain-truth-rule`); D1 counts them.
- **Exempt `CLOSE` on any venue without the inventory check.** Loses: Spot has no exchange-side reduce-only; check 3 is the only thing that makes the exemption safe (ADR D6 already says a Spot SELL marked CLOSE must still pass check 3).

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Should an exit still be spaced from the previous order by a smaller floor (a few tens of ms) to protect the exchange? | Nothing | 2026-10-20 |
| O2 | Does the owner accept D1 (it revises 🟢 D6 for Spot exits)? | The merge of the pull request | 2026-10-20 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1-D3 | [BUG-241](../../bug_report/completed/BUG-241_a_spot_stop_that_sells_in_several_slices_is_refused_by_the_order_budgets_spacing_and_rate.md) | Verified in code; awaiting the owner | `tests/integration/modules/bots/test_a_stop_that_sells_in_slices_is_not_refused_by_the_order_budgets_pacing_on_the_fake_exchange.py` red before, green after; unit tests of the policy and the command |
