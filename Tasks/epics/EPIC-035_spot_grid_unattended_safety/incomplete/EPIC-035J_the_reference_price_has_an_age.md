# EPIC-035J — The reference price has an age

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M1 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — resume, stop slicing and the dust check can use a price hours old
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035A

---

## 1. Context and problem
Audit M1: `_price()` prefers the last tick over a fresh book read, so resume proposals, stop slicing and the dust check can use a stale price, and a confirmed proposal is never re-priced. Cited: `src/modules/bots/application/services/grid_executor.py:384-385`, `src/modules/bots/application/services/grid_resume_sequence.py` (the audit cites lines 495-532; the file is shorter in this tree, so the audit's range needs re-checking).

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] The reference price carries its timestamp.
- [ ] When older than a named limit it is refreshed from the book ticker before use.
- [ ] A confirmed resume proposal is re-priced just before placing and refused with a named reason if it moved beyond a named tolerance.

## 3. Design
Builds on the last-tick clock of `EPIC-035A`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/grid_executor.py` | as the criteria require |
| `src/modules/bots/application/services/grid_resume_sequence.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_stale_price_is_refreshed_before_a_resume_proposal` (red before)
- `test_a_proposal_that_moved_is_refused`

Not run yet.

## Resume
Not started.
