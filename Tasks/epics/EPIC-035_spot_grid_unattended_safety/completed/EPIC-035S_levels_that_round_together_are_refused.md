# EPIC-035S — Levels that round to one price are refused

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L3 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟢 — the plan is refused before any order
**Complexity:** S
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit L3: tick rounding can merge two levels; it is detected only indirectly by the fee break-even warning, and `level_at()` returns the first match. Cited: `src/modules/bots/domain/grid/grid_plan.py:96-112`, `src/modules/bots/domain/grid/grid_runtime.py:167`. **Verified 2026-10-08 against `d563c0f`:** the claim holds; the lines moved (`plan()` is at `grid_plan.py:96`, `GridRuntime.level_at` at `grid_runtime.py:204`, returning the first level whose price equals the argument, used by `grid_reconciler.py:267` to book an adopted order).

This task is specified briefly: it is Phase 4 — Accuracy. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [x] A plan in which two levels round to the same price is REFUSED with a named reason and the colliding levels shown.

## 3. Design
A verdict in the plan's rule list.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_plan.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_two_levels_that_round_to_one_price_are_refused` (red before)

## Implementation notes
- `check_distinct_levels` (`src/modules/bots/domain/grid/grid_level_checks.py`), constraint `every_level_has_its_own_price`, violation `LEVELS_ROUND_TO_ONE_PRICE` (blocks, D7: the plan certainly breaks level identity). It compares the plan's *rounded* level prices, EMPTY level included, because `level_at` matches by price over every level. The sentence names up to three colliding groups ("levels 0, 1 and 2 at 100.00, levels 3, 4 and 5 at 100.05") and counts the rest, and tells the user to use fewer grids or a wider range. The field map points it at Grids, Lower and Upper price.
- The fee break-even warning stays as it was; this verdict is independent of it.
- Red first: all four new tests failed (no such verdict) at `d563c0f`; green after. `test_the_report_example_has_distinct_levels` and the distinct case pin the OK side so the check cannot start refusing every plan.
- Evidence: `tests/unit/modules/bots/domain/grid/test_grid_level_checks.py`, `test_grid_constraints.py`, `test_grid_field_errors.py`.
- Not changed: `GridRuntime.level_at` still returns the first match; with colliding plans refused it can no longer be handed two rungs at one price by a fresh plan. A ladder saved before this task and resumed is not re-judged here.

## Resume
Done. Delivered in the EPIC-035L/035S pull request.
