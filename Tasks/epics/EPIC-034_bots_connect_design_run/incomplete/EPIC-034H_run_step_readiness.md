# EPIC-034H — Run: one readiness query serves the screen and the Start handler; Save and Start

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🟡 — the last gate before orders
**Complexity:** M — a query, the progress panel, the primary action
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-034C](EPIC-034C_trading_switch_folded_into_actions.md), [EPIC-034F](EPIC-034F_design_step_constraints.md)

---

## 1. Context and problem
Five Start refusals surface only after the click (`grid_start_preconditions.py:68-109`), and "Save the changed parameters first" is never shown (`bot_action_rules.py:75-76`).

## 2. Acceptance criteria
- [ ] A `GetBotReadiness` query returns the three steps and every remaining item with its reason and its fix; the Start handler calls the same query before any order, so the screen and the handler cannot disagree.
- [ ] The Bots mode shows the three steps' progress; each missing item has a fix action (focus the field, Save, Retry).
- [ ] "Save and Start" is the primary action (D8), disabled with "N things left" that leads to the list; the other lifecycle actions stay in the Bots menu.
- [ ] No Start refusal appears after the click that was not shown before it, except a race the handler reports in the same words.
- [ ] SPEC-014 is updated; its "Proven by" tests cover the three steps.

## 3. Design
The readiness FSM started in `EPIC-034D` is completed here, with the Connect, Design and Run states in one matrix file. The query composes the snapshot, the assertions and the run preconditions; nothing is checked in two places. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/queries/` | the readiness query |
| `src/modules/bots/application/use_cases/start_bot/` | calls it |
| `src/modules/bots/ui/bots_screen/` | progress, primary action |
| `Docs/SPEC/SPEC-014*` | updated |

## 5. Testing
Unit: the handler refuses exactly what the query reports, red first by bypassing it. An integration journey from a new bot to a running bot through the three steps. Desktop E2E. A reviewer is required. Not run.

## Implementation notes (written when done)
Not started.
