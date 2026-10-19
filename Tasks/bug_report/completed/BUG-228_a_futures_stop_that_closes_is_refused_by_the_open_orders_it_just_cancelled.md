# BUG-228 — A Futures bot's stop with the close-position option halts with `exit_slice_failed ... owner_budget_open_orders` and leaves the position open

- **Reported:** 2026-10-19 (coordinator session, from the owner's VPS: bot `e2zeyr` BNBUSDT, Futures Testnet, beside bot `puhy4o` ETHUSDT)
- **Severity:** 🔴 P1. A stop that must close a leveraged position is refused its own close and halts with the position open; the same path stops mainnet bots.
- **Status:** ✅ Fixed (2026-10-19)
- **Board:** `bot stop --close-position` halted with `3.30 unsold after slice 2: owner_budget_open_orders`. Cause: the bot's close slices were sent as entries (`purpose` ENTRY), so the owner budget counted them among the open orders, which a re-registration had just refilled from a lagging open-orders list. Fix: a bot's reduce-only close is sent as `OrderPurpose.CLOSE`, which the budget does not count.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (stop a grid bot) → `bots` → `application/services/orders/` (`BotOrderGateway.market_reduce_only`), `application/kinds/grid/stop/`; the rule it meets is `trading` → `domain/policies/trading_limit_policy.py`
- **Environment:** VPS headless, Futures Testnet, 2026-10-19 15:38 UTC, `159fbfd`. Reproduced on the fake Futures exchange at `159fbfd`.

## Reproduction
Integration test `tests/integration/modules/bots/test_a_stop_that_closes_on_a_lagging_order_list_on_the_fake_exchange.py`: a BTC grid and an ETH grid run on one Futures venue; the venue's open-orders list is made to lag (`MatchFaults.stale_open_orders`: a cancelled order is still listed); the BTC bot is stopped with the close option. Before the fix: `STOPPING -> HALTED on halt (exit_slice_failed: 0.006 unsold after slice 2: owner_budget_open_orders)`, the same text as the owner's alert.

## Symptom
Owner's first alert, 15:38:02 UTC: `Bot halted ... Was STOPPING. Reason: exit_slice_failed (3.30 unsold after slice 2: owner_budget_open_orders)`.

## Root cause
At `159fbfd` `BotOrderGateway.market_reduce_only` (`bot_order_gateway.py:191`) sent a reduce-only market order with the default purpose ENTRY (`_request`, `:309`). `TradingLimitPolicy._budget_checks` (`trading_limit_policy.py:127`) exempts an order from the open-order count only when `purpose.only_reduces`, so every close slice answered to `OWNER_BUDGET_OPEN_ORDERS` (`:151`, `open_order_count + 1 <= max_open_orders`, a cap of `grid_count + 1`). The stop registers the budget again between its cancels and its close (`grid_stop_sequence.py:117`), which rebuilds the owner's book from the open orders the exchange lists (`owner_resting_orders.py:33`, `owner_position_registrar.py:115`): orders the stop had just cancelled but the list still showed were counted again, so slice 1 passed at the cap and slice 2 was refused. A protective stop was already sent as PROTECTIVE for this reason (`EPIC-039L`); the close was not.
Established: the code path above, and that it reproduces the alert on the fake with a lagging list. **Not established:** why the real exchange's list still showed the cancelled orders (testnet lag is the working hypothesis; the owner's journal for 15:36–15:40 UTC would settle it). The ETH bot played no part: the ledger, the registration read and the cancel are scoped by symbol and by tag.

## Fix
`BotOrderGateway.market_reduce_only` sends `OrderPurpose.CLOSE` (`_request` takes a `purpose`). Trading's rule is unchanged: a CLOSE still answers to the exposure checks, is refused on a venue that does not enforce reduce-only, and the exchange refuses a reduce-only order that would grow the position. Every bot close goes through this one method (stop, halt close, parking, mark exit), so the family is closed at the one place.

## Regression test
`tests/integration/modules/bots/test_a_stop_that_closes_on_a_lagging_order_list_on_the_fake_exchange.py::test_a_close_is_not_refused_for_orders_the_list_still_shows_and_the_stop_waits_for_the_list` — red before the fix (the bot passed through HALTED), green after; with only this fix reverted it fails on the HALTED state. Unit: `tests/unit/modules/bots/application/services/test_bot_order_gateway_close_and_cancel.py::test_a_reduce_only_market_close_is_sent_for_the_close_purpose`.

## Verification
Regression tests green; the commit tier (ruff, format, reference check, architecture guards) green. Positive proof the new mechanism ran: the integration test observes no HALTED or ERROR state on the way and the exchange position at 0 before the list catches up. The full gate is the PR's `ci-local.ps1 -Full` run.

## Suggested next steps
Spot's stop sells through `market_sell` with no reduce-only to stand on, so the same refusal is possible there: filed as BUG-230.
