# BUG-266 — A counter order sent before its placement is saved is adopted without its pairing, so its fill closes no cycle

- **Reported:** 2026-10-21 (review round 1 and 2 of PR 711, reproduced in the domain)
- **Severity:** 🟡 P2 — Cycles and Grid profit come out short after a restart or a faulted submit; Total PnL, which holds no grid profit, is unchanged, so it is real-money bookkeeping of the figure the owner reads as earnings
- **Status:** Open
- **Board:** A counter order is submitted after the fill that owes it is saved but before its placement (with its pairing) is saved, so a death or a faulted submit between them leaves a live order the reconcile adopts with no `paired_buy_price`; its fill books into the inventory and closes no cycle. Open; the design below is proposed, not built.
- **Context:** Run a grid bot → bots (`src/modules/bots/`) → `application/kinds/grid/grid_ladder_placer.py`, `grid_facts.py`, `recovery/grid_reconciler.py`
- **Environment:** Found by reading and a domain probe; not observed on the owner's host (its journal for 16:50-21:10 holds no `adopted` line).

## Reproduction
Pure domain at `78c7770`: a stream BUY fill with `hold=False` saves a runtime with no held order and a `PlaceOrder` for the SELL counter that carries the pairing only in memory. `GridLadderPlacer._place` sends it, then saves `placed(...)` with the pairing. If the process dies between the send and that save, or `place_limit` returns a FAULT while the order is live (`grid_order_failure.py`), the restart reconcile adopts the SELL (`GridReconciler._level_order`, no pairing; `grid_reactions.adopted`, no held order to take it from). The SELL fills: `completed_cycles` 0, `realised_profit` 0, `realised_total` +10. Not run as a regression test yet (it would be red).

## Symptom
One cycle short per such order; `FilledOrder.cycle_profit` is `None` for the completing fill; no log line says so (`BUG-264` now logs the fill).

## Root cause
Established by reading, at `78c7770`: the pairing of a counter order exists in the saved record only after the order is on the exchange. Not established: that it happened on the owner's bots.

## Fix (proposed, not built)
Write the intent ahead of the send: put the `PlaceOrder` into the saved runtime's `held` (it already carries the pairing, the quantity and the level) before `place_limit`, remove it when the outcome is known (accepted, or a definitive refusal), and leave it when the outcome is unknown (a FAULT), so `adopted` (which now carries a held order's pairing, `BUG-265`) finds it, and `release_held` places it if the order never reached the exchange. Needs: the outcome kinds that mean "may be live" named in one place, the SYMBOL_NOT_TRADING and ORDER_INVALID paths removing the entry before they hold or drop the order, and `Docs/MODULES/bots/06-runtime.md` updated (placement sequence).

## Regression test
To write first, red: the sequence above over the simulated venue with a death between send and save.

## Verification
Not run.

## Suggested next steps
Build the write-ahead intent in its own pull request (it changes the order-sending path), with the death-between-send-and-save test red first.
