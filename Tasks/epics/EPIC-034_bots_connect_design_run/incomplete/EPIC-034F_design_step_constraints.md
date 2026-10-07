# EPIC-034F — Design: every constraint is a named assertion, shown on its field, with the account's numbers

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🟡 — the rules that decide whether real orders are allowed
**Complexity:** L — new checks, blocking versus advice, field errors, the grid overlay
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-034D](EPIC-034D_connect_step.md)

---

## 1. Context and problem
The plan's checks exist (`src/modules/bots/domain/grid/grid_checks.py`: break-even, minimum and maximum notional, open orders, price band, step, ATR, stop loss, take profit, spacing) but show only as a list of verdicts. The balance is checked only at Start (`application/services/grid_start_preconditions.py:100`). Whether the sell levels' base inventory is checked is open (ADR O2).

## 2. Acceptance criteria
- [ ] Each constraint is a pure domain assertion with a name, a result and its numbers, unit-tested at and around each boundary.
- [ ] New assertions: capital ≤ available quote balance; base inventory for the sell levels, or the plan says it buys it first; the key may trade the venue. They read the `EPIC-034D` snapshot.
- [ ] Each assertion is blocking or advisory per D7; only blocking ones disable Start.
- [ ] A violated assertion marks its field, with a sentence and a useful number (current price, minimum capital).
- [ ] The plan's levels are drawn over the chart.
- [ ] SPEC-014 §3.5 and §5 describe the new behaviour.

## 3. Design
Extend `GridCheckInputs` with the snapshot; keep one `run_checks` list that the screen and `EPIC-034H`'s readiness query both call. The field mapping lives with the kind (`ui/kinds/grid/`), not in the generic Bots screen. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/` | the assertions |
| `src/modules/bots/ui/kinds/grid/` | field errors, overlay |
| `Docs/SPEC/SPEC-014*` | updated |

## 5. Testing
Boundary-value unit tests per assertion with mutation checks; presenter tests for field errors. A reviewer is required. Not run.

## Implementation notes (written when done)
Not started.
