# EPIC-035H — One app instance per data root

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M6 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — two instances place duplicate orders against one account
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit M6: there is no single-instance lock and the symbol leases live in one process; the best case of two instances is a `DUPLICATE_LEVEL_ORDER` halt. Verify by searching `src/` for any lock file.

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] A second app instance on the same data root detects the first through an exclusive lock file and opens read-only, saying so.
- [ ] The lock is released on a clean exit and on a crash (the OS releases it).
- [ ] A read-only instance places and cancels nothing.

## 3. Design
Exclusive lock file (an OS advisory lock) on the data root; a vetted pattern, no network coordination.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/shell/ (the composition root)` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_second_instance_is_read_only`
- `test_the_lock_dies_with_the_process`

Not run yet.

## Resume
Not started.
