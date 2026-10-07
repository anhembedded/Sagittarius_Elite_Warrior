# EPIC-034F — Design: every constraint is a named assertion, shown on its field, with the account's numbers

**Status:** ✅ Done (2026-10-07)
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
- [x] Each constraint is a pure domain assertion with a name, a result and its numbers, unit-tested at and around each boundary.
- [x] New assertions: capital ≤ available quote balance; base inventory for the sell levels, or the plan says it buys it first; the key may trade the venue. They read the `EPIC-034D` snapshot.
- [x] Each assertion is blocking or advisory per D7; only blocking ones disable Start.
- [x] A violated assertion marks its field, with a sentence and a useful number (current price, minimum capital).
- [x] The plan's levels are drawn over the chart.
- [x] SPEC-014 §3.5 and §5 describe the new behaviour.

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
**Delivered** on branch `claude/epic-034-pr5-design-run-live-chart` (PR-5, with `EPIC-034H` and `EPIC-034I`).

**ADR O2, answered by reading the code: no, the base inventory is not checked, and it needs no check.** `plan()` sizes a SELL level from the base *the opening purchase buys* at the last price (`grid_plan.py`, "the opening buy"), and `GridStartSequence._buy_opening` buys it at market before the ladder is laid, out of the same capital. So the account needs no base of its own and holding some changes nothing; what it needs is quote, which the capital assertion covers. The "base inventory" assertion is therefore the plan saying it buys first (`OPENING_BUY`: how much base, for about how much quote), not a read of the holdings.

| Criterion | Evidence |
| :--- | :--- |
| Each constraint a pure, named domain assertion with its numbers, tested at and around each boundary | `GRID_CONSTRAINTS` (`grid_constraints.py`) names thirteen assertions; the existing `test_grid_checks.py` boundaries, and new `test_grid_account_checks.py` at capital = balance, one cent above, a floored cent, an unknown key flag, no account |
| Capital ≤ available quote; the opening buy; the key may trade, reading the snapshot | `grid_account_checks.py` over `AccountView` (the snapshot narrowed by `account_view_of`); `BotKindInputs.account` and `GridCheckInputs.account` carry it. Each says it did not run before the account was read |
| Blocking or advisory per D7 | The table lists, per constraint, every violation code and whether it blocks; `test_grid_constraints.py` provokes every code and holds the real verdict severity to the declaration. D7 moved two things: a stop loss at or above the lower limit and a take profit at or below the upper limit now **refuse** (they advised before), `STOP_LOSS_INSIDE_RANGE` / `TAKE_PROFIT_INSIDE_RANGE` |
| The error on the field, with a useful number | `grid_field_errors.py` maps each code to its field(s) in `ui/kinds/grid/`; `GridPanel.show_verdicts` writes "Blocks Start: …" or "Advice: …" under the field and in its tooltip; `test_grid_field_errors.py` holds every code to a field or a stated reason, `test_bots_design_step.py` runs it on the real presenter (800 USDT available against a 1,000 capital) |
| The plan's levels drawn on the chart | Already drawn by `BotChartHost.draw` since `EPIC-029G`; the Design tests now prove it on the screen (`test_the_plans_levels_are_drawn_on_the_chart_the_screen_shows`, `test_editing_the_range_redraws_the_levels`) |
| SPEC-014 §3.5, §5 and §8 | Updated; steps 4 and 5 became Design and Blocking-or-advice |

**Decisions.** The key's permission was Connect's own refusal (`start_refusal`); it is now the domain assertion `KEY_CANNOT_TRADE` alone, so Start's reason and the verdicts say it once. Useful numbers were added where the sentence lacked one: the capital that clears the minimum notional (`minimum_capital`), the current price beside a price-band violation, both break-even percentages. `BotPlanPanel`'s refresh moved out of `bots_presenter.py` into `DetailEffects`, which keeps the presenter at 393 lines.

**Not delivered here.** Start's own use case still judges without the account; `EPIC-034H`'s readiness query supplies it, so the balance and the key bind at Start too.

**Verification.** Commit tier `ci-local.ps1 -SkipTests` PASS (`logs/ci-local-20261007-084136.log`, nothing matching `FAILED|ERROR|Traceback|ResourceWarning`); `tests/unit/architecture` 674 passed; `tests/unit/modules/bots` green. Mutation checks, each turning a test red: the balance comparison `>` → `>=`, the key flag test `is False` → `is not True`, `STOP_LOSS_INSIDE_RANGE` back to a warning, `STEP_BELOW_MINIMUM` declared blocking. The owner's own look on a real display: not run.
