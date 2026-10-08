# EPIC-035I — OS sleep is detected and reconciled

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M8 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — after wake the bot behaves as in a stream gap and a stop-loss crossed in sleep goes unnoticed
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035B

---

## 1. Context and problem
Audit M8: sleep and hibernate are not detected; after wake missed fills are not recovered and a crossed SL waits for the next tick.

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] A gap in the monotonic clock larger than a named threshold is detected by one service.
- [ ] On detection every running bot runs the gap reconcile of `EPIC-035B` and an SL/TP check against a fresh price read (not the last tick).
- [ ] The event is logged and shown on the bot.

## 3. Design
Reuse `EPIC-035B`'s reconcile entry point; add only the detector.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/ (a new clock-gap service)` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_clock_gap_triggers_a_reconcile_and_an_exit_check` (fake clock)

Not run yet.

## Resume
Not started.
