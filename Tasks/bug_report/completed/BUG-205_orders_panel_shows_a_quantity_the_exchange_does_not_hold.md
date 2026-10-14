# BUG-205 — The Orders panel shows level 6 at 0.0022 while Binance holds that order at 0.0021

- **Reported:** 2026-10-14 (owner, on the real-money Spot Mainnet bot `Test_real_cash`, id ke95g7, via the coordinator session)
- **Severity:** 🔴 P1 — real money: the bot's books for a resting order (what a full fill completes, the counter order's size, the profit) can rest on a quantity the exchange does not hold
- **Status:** Fixed (2026-10-14)
- **Board:** The Orders panel showed L6 at 0.0022 while Binance held 0.0021. Cause: the ladder saved the unrounded quantity 0.00219090; the exchange took it floored to the lot step (0.0021); the panel rounded it to 0.0022; and neither placement nor the restart reconcile read the exchange's quantity back. Fix (#507): save the accepted quantity; the reconcile adopts a smaller one and halts on a larger one.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → Module `bots` (`application/services/`: ladder placing, reconcile) and `trading` (`adapters/binance/`: the placement answer) → Application / Adapters
- **Environment:** Spot Mainnet, ETHUSDT, grid 2348–2667, 6 grids, capital 35 USDT; ladder laid 2026-10-14 about 08:35 (Binance local time); app commit not captured (Unknown). No secret in this report.

## Reproduction
Not reproduced. On the fake exchange a fresh start with this repository's code saves, for every order, exactly the quantity the exchange lists (`origQty`), so the difference did not arise from the start path as it stands.
1. Start a Grid on the fake Spot exchange; compare `runtime.open_orders[*].quantity` with the exchange's open orders: equal.
2. Make the exchange hold one order at another quantity (`SpotAccountState.resize_resting`), or accept every LIMIT for less than it was sent (`accept_limits_for_less`): before the fix the saved ladder, and so the Orders panel, kept the sent quantity.

## Symptom
Owner, 2026-10-14. Orders panel: L6 `Sell 2,667.00 0.0022`, client id `SEW-ke95g7-fb52e1da7a`. Binance open orders: the same order at 0.0021. L0 Buy 2348 0.0024, L1 Buy 2401.16 0.0024, L3 Sell 2507.50 0.0022, L4 Sell 2560.67 0.0023, L5 Sell 2613.84 0.0023 match. After a restart: "5 saved order(s) rest, 1 filled while the app was closed, 0 missing, 0 not saved by the bot". Expected: both show 0.0021, or the app says that they differ.

## Root cause
Established (two missing reads of the exchange's quantity):
- `SpotTradingClient.place_order` and `FuturesTradingClient.place_order` returned the order they were given and dropped the response's `origQty`; `classify_submit` (`bots/application/services/orders/order_outcome.py`) therefore carried only the id, and `kinds/grid/start/grid_start_sequence.py` `_place` and `kinds/grid/grid_ladder_placer.py` `_place` saved `action.quantity`, the quantity asked for, as the order's quantity.
- `kinds/grid/recovery/grid_reconciler.py` `compare_with_exchange` matched saved orders to the exchange's open orders by client id only (`_apply_missed_fills`, `_adopt`); a listed order's `quantity` was never compared.

Refuted from the code: the hypothesis that the initial L6 sell was re-sized at placement while the ladder kept the planned quantity. The ladder is sized net of the opening fee before it is placed and that net action is what is both sent and saved (`grid_start_sequence.py`, `sells_net_of_opening_fee`); trading rounds by the lot step with `Decimal` (`order_quantity_rounding_policy.py`) and the adapter sends `order.quantity` unchanged; nothing in `src/` amends an order. The owner's numbers fit the net-of-fee sizing for L4 to L6 (gross 0.0024, 0.0024, 0.0023 for a per-level capital near 6.3 USDT, net 0.0023, 0.0023, 0.0022), so the panel's 0.0022 is what the bot sent.

Not established: why the exchange holds 0.0021. Candidates, none proven: the running build differs from this code; a partial fill shown by Binance as a remaining quantity; an edit on the exchange. The fix makes any such difference visible and corrected, whichever it was.

Booking: a fill is booked from the executed quantity of the exchange's own report (`on_fill`, `_missed_fill`), not from the saved order quantity. What a saved quantity decides is whether a fill completes the order (`LevelOrder.is_filled`) and the size of the counter order, so a wrong saved quantity could mis-complete a level.

Same family, scanned: the Futures client had the identical discard (fixed together); algo (stop) orders return `order` from `_place_algo_order` and no Grid places them; the manual order desk shows `submitted_order`, which now carries the accepted quantity too.

## Fix
- `trading/adapters/binance/accepted_order.py` (new): `as_accepted(order, response)` returns the order with the response's `origQty`, logs `[order-quantity]` when it differs, and never raises on an unreadable answer. `SpotTradingClient.place_order` and `FuturesTradingClient.place_order` return it.
- `bots/application/services/orders/order_outcome.py`: `OrderOutcome.quantity` carries the accepted quantity; `grid_start_sequence.as_accepted` applies it to the action both placers save.
- `bots/application/kinds/grid/recovery/grid_order_quantities.py` (new) and `GridReconciler.compare_with_exchange`: **before** any missed fill is applied, each saved order takes the quantity the exchange holds for it: the open-order list's for an order still resting, history's `origQty` for one that is gone (the review of this PR found that an order held for less and filled whole while the app was closed was otherwise read as "ended without filling" and its remainder laid again). A smaller quantity is adopted with a WARNING `[order-quantity]` naming both numbers. A **larger** quantity is never adopted: the bot halts with `order_quantity_mismatch`, because the order could trade base the books do not cover. Decision under `domain-truth-rule.md`: the exchange's record is the truth, a shortfall is safe to adopt, an excess is exposure the bot cannot account for.
- Live path (a mismatch first seen while the bot runs): the stream's fill does not carry the order's quantity, so a level can show PARTIAL until the next reconcile, which runs on a stream gap and every five minutes while the stream is up; that reconcile now reads the quantity from history and settles the level. A change to the stream contract was judged out of proportion; the claim of this report is the reconcile's, not the stream's.
- `Docs/SPEC/SPEC-014_run_a_grid_bot.md`: a row for the new behaviour.
- Fake exchange (`tests/sanity/fake_exchange/`): `resize_resting`, `accept_limits_for_less`; the two small records moved to `spot_account_records.py` to stay under the file ceiling.

## Regression test
`tests/integration/modules/bots/test_a_restart_trusts_the_exchanges_order_quantity_on_the_fake_exchange.py`
- `test_a_restart_adopts_the_quantity_the_exchange_holds_for_a_saved_order` — failed before the fix: the saved L-top order stayed 0.00799 while the exchange held 0.00798; passes after, with the `[order-quantity]` line.
- `test_a_ladder_saves_the_quantity_the_exchange_accepted_for_each_order` — failed before the fix (saved 0.00799, exchange 0.00798000 for every order); passes after.
- `test_a_restart_settles_an_order_held_for_less_that_filled_whole_while_closed` — failed before the fix: the order stayed PARTIAL and its remainder was laid again at the same price; passes after. (The following counter BUY may then be refused by the budget, because base the exchange did not take stays in the inventory; the test pins the settled order.)
- `test_a_restart_halts_when_the_exchange_holds_an_order_for_more_than_saved`; unit tests `test_grid_order_quantities.py` (smaller open, smaller from history, open list wins, equal or unknown unchanged, larger refused), `test_accepted_order.py` (every branch of `as_accepted`) and `TestAcceptedQuantity` in `test_futures_trading_client.py`.

## Verification
Initial run, unit, integration and sanity tiers: 13 871 passed; after the review round, unit (architecture, all modules) and the bots and trading integration tiers: 9 744 passed. Failures that also fail on the base commit and are unrelated: `test_workbench_conformance[True-1024x700]` (window size) and `test_ci_local_checkout_name_guard` (`pwsh` is not installed here). `ruff check`, `ruff format --check` clean; `mypy` clean on the touched files. The full gate is the PR's GitHub Actions `ci-local.ps1 -Full` run. The owner's real order is not reproduced: this fix cannot say why it differed.

## Closure (2026-10-14)
The fix merged in PR #507, with its regression tests green and an independent review PASS.

**Cause of the owner's 0.0021, established after the merge.** The 08:35 log is lost, but the first restart on the fixed build logged:

`Bot ke95g7: SEW-ke95g7-fb52e1da7a at L6 is held by the exchange for 0.00210000, the ladder had 0.00219090; the exchange's quantity is adopted [order-quantity]` (owner's log, 2026-10-14 23:40:48)

So the saved ladder held an **unrounded** quantity, 0.00219090, the net-of-fee action. The order that reached the exchange was floored to the 0.0001 lot step, giving 0.0021, and the Orders panel rounded the saved value to four places, giving 0.0022. The Root cause section above refuted a re-size *after* placement; that refutation stands. The difference arose at placement, between the saved action and the rounded order that was sent. The fix covers it: placement now saves the exchange's `origQty`, and the reconcile adopted the 0.0021 for this order with the WARNING above.

The owner's follow-up on the halt reason for a large shortfall is [PRO-010](../../proposal/PRO-010.md).
