# EPIC-035Q — The reconciler reads the executed quantity of an adopted order

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M10 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — an adopted order that already partly filled starts at zero
**Complexity:** S
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035B

---

## 1. Context and problem
Audit M10: the adopted order carries no executed quantity, so an adopted order that has partly filled starts at `executed = 0`, causing an inventory mismatch, a HALT, or a stale count. Cited: `src/modules/bots/application/services/grid_reconciler.py:322-345,415-418`. Verify.

**Re-verified on `3064fe0` (master-warrior), 2026-10-08.** The mechanism holds; the citation is stale: `grid_reconciler.py` is 314 lines (`:322-345,415-418` do not exist). `_adopt` built the adopted order with `_level_order(order)`, which starts at `executed = 0`. Reproduced before the change: a partly filled adopted SELL left the saved inventory 1.5 above the derived one and the bot HALTED `INVENTORY_MISMATCH` at the reconcile that adopted it.

**One acceptance criterion changes wording.** The task said "reads `executedQty` from the open-order record". `Order`, the contract the open-order list returns, has no executed quantity (only `OrderRecord`, from history, does) and widening a contract shared by the desk for one consumer is the wrong direction; the reconciler already reads history once for saved orders (`BUG-188`), so the adopted ids join that read.

## 2. Acceptance criteria
- [x] Adoption reads the executed quantity from the exchange's order record (history; see the note above). `_read_records` takes the saved ids and the open ids the ladder does not know in one pass. Evidence: `test_an_adopted_partly_filled_order_keeps_its_executed_quantity` (red before: HALTED).
- [x] The level's executed quantity starts from it. `_adopt` brings the adopted order level through the same `_catch_up` a saved order uses (fees, the held counter order, PAUSED). Evidence: the same test (executed 1.5, inventory 1.5 lower); `test_an_adopted_order_is_not_counted_again_by_the_next_reconcile` (red before for the same reason); boundaries that pass before and after: executed nothing, no history row yet, and a derived inventory that does not show the fill still halts (`test_an_adopted_order_that_is_more_than_the_exchange_derives_still_halts`).

## 3. Design
Shares the read with `EPIC-035B`'s gap reconcile. No history row for an adopted order (history lags the open-order list) is no evidence of a fill: the order starts at zero and the next reconcile reads again; the inventory check stays the judge of what remains.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/grid_reconciler.py` | `_read_records` (one read for saved and unknown ids); `_adopt` applies the executed quantity |

## 5. Testing
Unit tier, the real executor over the simulated venue: `test_grid_reconciler_adopts_executed.py` (5). Red before: the two that need the fix failed (HALTED; the adopted level empty); the three boundaries pass either way. Mutation (the adopt step without the catch-up) turned two red. Green after: `tests/unit/modules/bots`, `tests/unit/modules/trading`, `tests/unit/architecture`.

## Implementation notes
The history read is still one pass per reconcile, now covering the adopted ids too (no second read). A full fill of an adopted order that is still listed open settles its level and holds its counter order, as for a saved one.

## Resume
Done. Nothing owed.
