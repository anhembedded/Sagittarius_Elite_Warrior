# EPIC-035G — A failed store write still parks the ladder

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M2 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — memory says ERROR while the disk disagrees and the ladder stays live
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035C

---

## 1. Context and problem
Audit M2: in-memory state mutates before the save; when the save fails the fault handler saves again, fails again, and the error escapes the guard, so parking is skipped. Cited: `src/modules/bots/application/services/bot_run_state.py:200-220`, `src/modules/bots/application/services/grid_task_guard.py:87-97`. Verify.

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] A store write failure (disk full, permissions) never skips parking: the guard parks before it tries to record the new state, or catches the write error around the park.
- [ ] A distinct storage-failure state or reason is raised and shown; it does not masquerade as the original fault.
- [ ] On the next successful write the true state is persisted.

## 3. Design
Same family as `EPIC-035C`'s H4: parking is a safety effect and must not depend on persistence succeeding.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/bot_run_state.py` | as the criteria require |
| `src/modules/bots/application/services/grid_task_guard.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_failed_save_does_not_skip_parking` (red before: orders left)
- `test_a_storage_failure_is_named`

Not run yet.

## Resume
Not started.
