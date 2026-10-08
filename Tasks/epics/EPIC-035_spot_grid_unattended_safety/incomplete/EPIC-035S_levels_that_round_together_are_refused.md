# EPIC-035S — Levels that round to one price are refused

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L3 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟢 — the plan is refused before any order
**Complexity:** S
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit L3: tick rounding can merge two levels; it is detected only indirectly by the fee break-even warning, and `level_at()` returns the first match. Cited: `src/modules/bots/domain/grid/grid_plan.py:96-112`, `src/modules/bots/domain/grid/grid_runtime.py:167`. Verify.

This task is specified briefly: it is Phase 4 — Accuracy. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] A plan in which two levels round to the same price is REFUSED with a named reason and the colliding levels shown.

## 3. Design
A verdict in the plan's rule list.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_plan.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_two_levels_that_round_to_one_price_are_refused` (red before)

Not run yet.

## Resume
Not started.
