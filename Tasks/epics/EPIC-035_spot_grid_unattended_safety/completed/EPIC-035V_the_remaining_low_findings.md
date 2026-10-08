# EPIC-035V — The remaining low findings

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L4, L6, L7, L8, L9 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟢 — five small, independent items; slice into child PRs if any grows
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit L4: a top-level BUY fill gets no counter SELL (`src/modules/bots/domain/grid/grid_reactions.py:336`). L6: the real-money confirmation is enforced only in the UI (`src/modules/bots/ui/bots_screen/bot_commands.py:77`). L7: foreign open orders on the symbol are not refused or warned about (`src/modules/trading/application/session/session_readiness.py:113-121`). L8: shutdown joins workers without a timeout (`src/modules/bots/adapters/thread_bot_work_queue.py:190-194`). L9: Stop is queued behind a long Start (`src/modules/bots/application/services/grid_executor.py:201-202`). Verify each path first: some are in files other than the audit's names.

This task is specified briefly: it is Phase 4 — Accuracy. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] L4: documented as intended in the SPEC, or the SELL is placed at the upper bound (decided in the PR).
- [ ] L6: the Start use case requires the real-money confirmation; the UI only collects it.
- [ ] L7: foreign open orders on the symbol produce a warning that counts them against the order cap.
- [ ] L8: shutdown joins each worker with a timeout, then logs.
- [ ] L9: a Stop cancels a running Start cooperatively between slices.

## 3. Design
Five independent changes; if any needs more than a screen of design it becomes its own child with a new letter.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_reactions.py` | as the criteria require |
| `src/modules/bots/ui/bots_screen/bot_commands.py` | as the criteria require |
| `src/modules/bots/application/services/grid_executor.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- one regression test per item, red before

Not run yet.

## Resume
Not started.
