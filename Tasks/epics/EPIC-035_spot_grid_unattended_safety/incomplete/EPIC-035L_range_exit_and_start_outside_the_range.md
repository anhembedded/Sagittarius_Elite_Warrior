# EPIC-035L — Range exit, and Start with the price outside the range

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding H7 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟡 — the Start rule is an owner decision still open (D4)
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035K; the Start rule waits on D4

---

## 1. Context and problem
Audit H7: there is no domain reaction to a range exit (below the range the bot holds the full base) and Start below the range market-buys the entire capital with only an informational `OK`/`OPENING_BUY` verdict. Cited: `src/modules/bots/domain/grid/grid_plan.py:127-131`, `src/modules/bots/domain/grid/grid_account_checks.py:69`, `src/modules/bots/ui/kinds/grid/grid_panel.py:166`. Verify. **Owner decisions:** D2 — stop-loss stays optional, with no default and **no forced warning**; D4 — the Start rule is **open**: (a) REFUSED below the lower bound and WARNING above, or (b) WARNING only.

This task is specified briefly: it is Phase 3 — Alerting and transparency. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] **Range exit while running:** an alert (`EPIC-035K`) fires when the price leaves the range, once per exit and re-armed when it returns; the bot keeps its existing behaviour (no new automatic exit), because stop-loss stays the owner's optional choice (D2).
- [ ] **Start outside the range:** the verdict follows D4 once the owner answers. Until then this criterion is not implemented and the task stays Planned for that part.
- [ ] No "stop-loss is off" warning and no default stop-loss are added (D2).
- [ ] The Plan panel names the rule that fired and the figure (price, bound).

## 3. Design
The range-exit alert needs only the price from `EPIC-035A` and the notifier of `EPIC-035K`; it does not wait for D4.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_plan.py` | as the criteria require |
| `src/modules/bots/domain/grid/grid_account_checks.py` | as the criteria require |
| `src/modules/bots/ui/kinds/grid/grid_panel.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_range_exit_alerts_once_and_rearms`
- `test_no_stop_loss_warning_is_added` (guards D2)
- the Start-rule tests, written once D4 is answered

Not run yet.

## Resume
Not started.
