# EPIC-035Q — The reconciler reads the executed quantity of an adopted order

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M10 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — an adopted order that already partly filled starts at zero
**Complexity:** S
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035B

---

## 1. Context and problem
Audit M10: the adopted order carries no executed quantity, so an adopted order that has partly filled starts at `executed = 0`, causing an inventory mismatch, a HALT, or a stale count. Cited: `src/modules/bots/application/services/grid_reconciler.py:322-345,415-418`. Verify.

This task is specified briefly: it is Phase 4 — Accuracy. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] Adoption reads `executedQty` from the open-order record.
- [ ] The level's executed quantity starts from it.

## 3. Design
Shares the read with `EPIC-035B`'s gap reconcile.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/grid_reconciler.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_an_adopted_partly_filled_order_keeps_its_executed_quantity` (red before)

Not run yet.

## Resume
Not started.
