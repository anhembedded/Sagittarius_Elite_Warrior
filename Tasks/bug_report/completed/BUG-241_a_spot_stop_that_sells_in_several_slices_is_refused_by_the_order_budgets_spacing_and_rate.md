# BUG-241 — A Spot Stop, stop loss or take profit that sells its base in more than one slice is refused by the order budget's spacing or rate and halts with the base unsold

- **Reported:** 2026-10-20 (the delivery coordinator, from the reviewer's note on PR #633 for BUG-238; found on `master-warrior` at `506de4a`)
- **Severity:** 🔴 P1 — a stop loss is refused by the bot's own order budget and the bot halts holding the rest of its base; no loss is known yet (the owner's run was Futures, which is exempt).
- **Status:** ✅ Fixed (2026-10-20)
- **Board:** A Spot exit of two or more slices (a base worth more than the 500 USDT per-order cap) was refused `owner_budget_spacing` on its second slice, or `owner_budget_rate` past 60 a minute, and the bot halted `exit_slice_failed` with the remainder unsold. Cause: exit slices carry no purpose, so trading judges them like placements; fixed by sending them as a close that answers to the inventory check only ([decision](epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-20_a_spot_exit_is_judged_by_the_inventory_not_by_the_pacing.md)).
- **Context:** Bots → Stop / stop loss / take profit on a Spot grid → `src/modules/bots/` → `application/` (`services/positions/closer_spot.py`, `services/orders/bot_order_gateway.py`) against `src/modules/trading/` → `domain/policies/` (the owner budget) and `application/orders/execute_order/`
- **Environment:** Linux CI container, app at `506de4a`, the strict Binance fake (Spot), production limits (250 ms spacing, 60 orders a minute). Never include credentials.

## Reproduction
1. Spot grid whose bought base is worth more than the per-order cap (two or more exit slices).
2. Stop with sell base (or let the stop loss or take profit trigger it).
3. Expected: every slice is sent and the bot is STOPPED. Actual: slice 2 is refused and the bot is HALTED with the remainder unsold.

Frequency: every time the exit has more than one slice and the next slice is sent less than 250 ms after the previous; certain on a fake that answers in milliseconds, intermittent on a real exchange whose round trip is near 250 ms. Past 60 slices the rate refuses regardless of latency.

## Symptom
Red on the strict fake exchange before the fix (`tests/integration/modules/bots/test_a_stop_that_sells_in_slices_is_not_refused_by_the_order_budgets_pacing_on_the_fake_exchange.py`):

```
(HALTED, exit_slice_failed, '0.01598 unsold after slice 2: owner_budget_spacing')
(HALTED, exit_slice_failed, '0.01598 unsold after slice 2: owner_budget_rate')
```

Expected instead: a stop loss is never refused by the bot's own order budget.

Found while reviewing BUG-238: the reviewer's note was that a Spot Stop right after a 60-order minute could be refused. That exact path is not the defect: the stop registers the bot's budget again before it sells, and the new book's window is empty (probe at `506de4a`: `orders_in_window` 0 and no previous order at the first slice). The defect is inside the exit's own slices.

## Root cause
At `506de4a`:

- `src/modules/bots/application/services/orders/bot_order_gateway.py:190` (`market_sell`) builds the exit slice as an ordinary entry-purpose order and sends it with `_submit` (no pacer turn, by design: `_submit_paced` at `:325` explains that a stop must not wait behind a neighbour's ladder).
- `src/modules/bots/application/kinds/grid/stop/grid_exit_slices.py:50` sends the slices one request after the other.
- `src/modules/trading/domain/policies/trading_limit_policy.py:127` (`_budget_checks`) exempts a reducing order from the open-order count, the spacing and the rate only when the owner has a **position** (Futures); a Spot owner's exit falls through to `_owner_budget_checks` (`:140`) and meets all five checks.
- `src/modules/trading/application/orders/execute_order/command.py:73` (`ExecuteOrderCommand.__post_init__`) refuses a close on a venue without reduce-only, so the bot could not have marked the slice as one.

The gate was green while the defect was live: the journeys' configuration sets `min_order_spacing_ms` to 0 (`grid_fake_exchange.app_config`), so no journey met the production spacing. Not a case study: the blind spot is the one configuration, closed by the new journey and the world's `limits` option.

## Fix
[Decision](../../epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-20_a_spot_exit_is_judged_by_the_inventory_not_by_the_pacing.md) D1-D3, chosen over a priority pacer turn (it would wait for the window) and a reserved window (an exit can be 20 slices):

- `application/orders/execute_order/command.py`: `ExecuteOrderCommand.is_inventory_exit` admits a **tagged market SELL** sent as a close on a non-Futures venue; a BUY, an untagged order or a protective order on Spot stays refused.
- `domain/policies/trading_limit_policy.py`: `_budget_checks` judges a reducing SELL of a Spot owner by the notional cap and the inventory check (ADR D6 check 3) and skips the open-order count, the spacing and the rate. The book still records it and it counts in the window.
- `bots/application/services/orders/bot_order_gateway.py`: `market_sell` sends `OrderPurpose.CLOSE`.

The Futures exit path was checked for the same family: `market_reduce_only` already sends `CLOSE` and a position owner's close answers to the exposure checks only (`EPIC-039L`); the journey keeps that true.

## Regression test
`tests/integration/modules/bots/test_a_stop_that_sells_in_slices_is_not_refused_by_the_order_budgets_pacing_on_the_fake_exchange.py::test_a_spot_stop_that_sells_the_base_in_slices_is_not_refused_by_spacing_or_rate[spacing|rate]` — failed before the fix with the two halts above; passes after (STOPPED, the base sold). The Futures twin passes before and after. Policy tests (`TestSpotExit`) and command tests (`test_a_spot_exit_is_a_close_of_the_owners_inventory.py`) pin the boundaries; flipping the inventory check or exempting a BUY turns them red.

## Verification
Local, at the fix commit: the journey red before and green after (above); the policy and command unit tests and their mutations; the commit tier. The full gate is GitHub Actions' `ci-local.ps1 -Full` run on the pull request's head.
