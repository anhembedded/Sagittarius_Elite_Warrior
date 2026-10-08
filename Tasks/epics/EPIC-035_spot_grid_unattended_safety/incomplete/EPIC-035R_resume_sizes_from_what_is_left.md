# EPIC-035R — Resume sizes from what is left

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M9 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — the audit marks this finding as inferred
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit M9 (inferred): on resume from HALTED, inventory beyond the SELL levels is left unplaced and the BUY side is still sized from the original `capital_quote` after losses. Cited: `src/modules/bots/domain/grid/grid_ladder.py:75-90`. First step: reproduce it with a test; if it does not hold, say so in this task and close it.

This task is specified briefly: it is Phase 4 — Accuracy. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] Resume sizes the BUY side from the actual remaining equity.
- [ ] Inventory in excess of the SELL levels is placed or reported, not silently kept.

## 3. Design
Domain function over the resume plan.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_ladder.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_resume_after_a_loss_does_not_oversize_the_buy_side` (must be red before, or the finding is withdrawn)

Not run yet.

## Resume
Not started.
