# BUG-265 — An order the reconcile adopts loses the entry its held counter order carried, so its fill closes no cycle

- **Reported:** 2026-10-21 (review round 1 of PR 711, from the investigation of `BUG-264`)
- **Severity:** 🟡 P2 — cycle count and Grid profit come out short on a restart; Total PnL is unchanged, so nothing is lost from the books of money, but the figure the owner reads as earnings is wrong
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** `grid_reactions.adopted` replaced the held counter order of a level with the order the reconcile found on the exchange and dropped the pairing the held order carried, so the adopted SELL's fill booked into the inventory but closed no cycle; the pairing now moves onto the adopted order. This covers only a level that still has its held order; the running path (counter submitted, process dies before the `placed` save) is open as [BUG-266](../incomplete/BUG-266_a_counter_order_sent_before_its_placement_is_saved_is_adopted_without_its_pairing.md).
- **Context:** Run a grid bot → bots (`src/modules/bots/`) → `domain/grid/grid_reactions.py`, `application/kinds/grid/recovery/grid_reconciler.py`
- **Environment:** Found by reading and a pure-domain probe (the reviewer of PR 711); not observed on the owner's host, whose journal for 16:50-21:10 holds no `adopted` line.

## Reproduction
A narrow case, honestly: a held order and a live tagged order at the same level need the earlier process to have sent a held counter without clearing it from the saved runtime, which `release_held` and `grid_facts._apply_fill` normally prevent (they save before they send), so the route is a failed store write or a replayed missed fill. Pure domain, a five-level ladder: a BUY at L1 (110) fills while the bot is paused (`hold=True`), so its SELL counter at L2 (120) is held, paired with 110. The reconcile finds that SELL on the exchange (it was sent before the app died and never saved) and adopts it: `adopted(runtime, 2, LevelOrder(id, SELL, 120, 1))`. The SELL fills.
Expected: `completed_cycles` 1, `realised_profit` 10. Actual: `completed_cycles` 0, `realised_profit` 0, `realised_total` 10.

## Symptom
Cycles and Grid profit one short per such order; `FilledOrder.cycle_profit` is `None` for the completing fill. Total PnL (`realised_total + unrealised + funding`) is identical, so a check of Total PnL against the exchange cannot see it.

## Root cause
`GridReconciler._level_order` builds the adoptee as `LevelOrder(id, side, price, quantity)` with no `paired_buy_price`, and `grid_reactions.adopted` then drops the held order for the level, the one record that still carried the pairing (read at `d11a20f3`). `completes_a_cycle` is side-based on a LONG grid, but `book_cycle` returns the runtime unchanged when `paired_buy_price` is `None`, silently.

## Fix
`adopted` moves the dropped held order's `paired_buy_price` and `paired_buy_fee_quote` onto the adopted order. With no held order nothing is invented: the exchange's list says nothing of a pairing, and an adopted opening-ladder SELL is not a cycle's completion. That case still closes no cycle, and it is the common one: on the running path the saved runtime holds no held order when the counter is sent, so there is nothing to take the pairing from (`BUG-266`, open). Whether the pairing can be derived from the saved entry fill is open and not guessed here.

## Regression test
`tests/unit/modules/bots/domain/grid/test_an_adopted_order_keeps_the_pairing_it_was_held_with.py` (the adopted SELL closes the cycle and books 10; the held order is still dropped; no pairing is invented without a held order). Red before: `completed_cycles` is 0.

## Verification
The new test and the bots unit tier locally; the full gate is GitHub Actions'. Not verified: that this path ran on the owner's `6tszoz` (its journal says it did not in the window); a reconcile over a real exchange.
