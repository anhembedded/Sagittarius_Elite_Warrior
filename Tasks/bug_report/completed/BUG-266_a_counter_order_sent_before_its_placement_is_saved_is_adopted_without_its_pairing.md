# BUG-266 — A counter order sent before its placement is saved is adopted without its pairing, so its fill closes no cycle

- **Reported:** 2026-10-21 (review round 1 and 2 of PR 711, reproduced in the domain)
- **Severity:** 🟡 P2 — Cycles and Grid profit come out short after a restart or a faulted submit; Total PnL, which holds no grid profit, is unchanged, so it is real-money bookkeeping of the figure the owner reads as earnings
- **Status:** ✅ Fixed (2026-10-22)
- **Board:** The pairing of a counter order lived only in memory between the send and the save of its placement, so a death or a request that raised while the order was live left a SELL the reconcile adopted with no `paired_buy_price` and its fill closed no cycle; the counter is now listed as owed in `held` in the save that precedes the send, and settled in the save that records the placement.
- **Context:** Run a grid bot → bots (`src/modules/bots/`) → `application/kinds/grid/grid_ladder_placer.py`, `grid_facts.py`, `recovery/grid_reconciler.py`
- **Environment:** Found by reading and a domain probe; not observed on the owner's host (its journal for 16:50-21:10 holds no `adopted` line).

## Reproduction
Pure domain at `78c7770`: a stream BUY fill with `hold=False` saves a runtime with no held order and a `PlaceOrder` for the SELL counter that carries the pairing only in memory. `GridLadderPlacer._place` sends it, then saves `placed(...)` with the pairing. If the process dies between the send and that save, or `place_limit` returns a FAULT while the order is live (`grid_order_failure.py`), the restart reconcile adopts the SELL (`GridReconciler._level_order`, no pairing; `grid_reactions.adopted`, no held order to take it from). The SELL fills: `completed_cycles` 0, `realised_profit` 0, `realised_total` +10. Not run as a regression test yet (it would be red).

## Symptom
One cycle short per such order; `FilledOrder.cycle_profit` is `None` for the completing fill; no log line says so (`BUG-264` now logs the fill).

## Root cause
Established by reading, at `78c7770`: the pairing of a counter order exists in the saved record only after the order is on the exchange. Not established: that it happened on the owner's bots.

## Fix
The runtime saved with a fact lists every order about to be sent as owed, in `held` (`grid_owed_orders.owing`, called from `GridLadderPlacer.save_owing` at the fill, the end and the release of held orders): the same save that already followed the fact, so no write is added and `test_grid_storage_pause.py`'s save count holds. `GridLadderPlacer._place` settles the entry in the one save that records the placement (accepted), or in the save of a definite refusal, a pause or a rung left empty. A `FAULT` (`OrderOutcome.may_be_live`, the one kind that may be live) leaves it: `adopted` (`BUG-265`) moves its pairing onto the order the reconcile finds, and `release_held` places it on a resume if it never reached the exchange. Design: `Docs/MODULES/bots/06-runtime.md` ("A fill").

## Regression test
`tests/unit/modules/bots/application/services/test_a_counter_order_is_written_down_before_it_is_sent.py`: a counter SELL whose request raised after the BUY filled is in the saved record with its pairing (110); adopted and filled, it closes the cycle (`completed_cycles` 1, profit booked). Red before (the saved `held` was empty), green after. Two companions: an accepted counter leaves no entry and keeps its pairing; an order refused for its numbers leaves no entry.

## Verification
The new test red on `origin/master-warrior` and green with the fix; the bots unit tier and `tests/unit/architecture` (6693 passed). Not verified: a restart over a real exchange; the full gate is GitHub Actions'.

## Known limit
An order that reached the exchange and filled while the app was down is not in the open list the reconcile reads, so its entry is not found by `adopted`; the inventory check halts the bot on the difference, as before this fix. That path (a tagged order that ended with no record of it) is not changed here.
