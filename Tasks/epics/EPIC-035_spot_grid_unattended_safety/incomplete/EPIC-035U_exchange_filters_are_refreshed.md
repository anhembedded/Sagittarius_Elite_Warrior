# EPIC-035U — Exchange filters are refreshed during a run

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L5 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — a tick/step change otherwise surfaces as `-1013` and ERROR
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035E

---

## 1. Context and problem
Audit L5: symbol terms are read once per executor, so a mid-run filter change surfaces as `-1013` and the bot goes to ERROR (Binance terminates its own grids in this case). Cited: `src/modules/bots/application/services/grid_run_context.py:44-55`. Verify.

This task is specified briefly: it is Phase 4 — Accuracy. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] `exchangeInfo` for the bot's symbol is refreshed on a named interval.
- [ ] A change in tick size, step size or notional HALTs the bot with a named reason and the old and new values; the symbol status of `EPIC-035E` is refreshed by the same read.

## 3. Design
One refresh service feeding `EPIC-035E` and this task.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/grid_run_context.py` | as the criteria require |
| `src/modules/bots/application/services/bot_exchange_terms.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_tick_size_change_halts_the_bot_with_the_old_and_new_values` (red before: ERROR)

Not run yet.

## Resume
Not started.
