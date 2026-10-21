# BOT-219 — The Strategies dock is removed from the Bots mode, and arming a strategy stays possible

**Status:** ✅ Done (2026-10-21)
**Board:** The Bots mode has no Strategies dock: the owner chose option A (2026-10-21, "A"), so Arm strategy… asks what to arm and on which venue in one dialog that lists what is armed, Disarm strategy… asks which armed venue unless one is armed, and each arm and disarm is told in the Output pane's Bots channel; EPIC-040G D11 is superseded for the Bots screen.
**Source:** the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu), 2026-10-21, quoting the owner: "… xóa cái strategy luôn đi" ("… and delete the Strategies one"), with the instruction to verify where arming lives first and to stop before deleting if the dock is the only way.
**Risk:** 🟡 — the only UI to arm and disarm changes shape; the arming ports, the saved selection and the session are untouched
**Complexity:** M — the commands act on the panel's selected venue today
**Epic (optional):** [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** [BOT-218](../completed/BOT-218_one_plan_column_on_the_live_and_backtest_tabs.md)

---

## 1. Context and problem
Verified at `4eade242`: the Trade desk has no Strategy panel (`desk_view.py`: "arming a strategy is the Bots mode's"); `Bots → Arm strategy…` and `Disarm strategy` (`bots_commands.py` `ARM_STRATEGY`, `DISARM_STRATEGY`) act on the selected venue of the Strategies dock (`strategies/strategy_rows.py` `StrategiesPanel`, HLD §11.2 row 126); the only other entry is the `trade-once` CLI, which neither arms nor disarms. Deleting the dock as it is would delete the feature. EPIC-040G D11 ("the Strategies panel keeps working unchanged until G5") is superseded for the Bots screen by the owner's request, to be recorded in the decision file when this is done.

## 2. Acceptance criteria
- [x] The Bots mode has no Strategies dock, and a saved layout that had it restores without it (`test_the_plan_belongs_to_the_live_tab.py`).
- [x] A strategy can still be armed and disarmed from the app on each venue, and what is armed is still told: in the Arm dialog and in the Output pane (`test_venue_strategies.py`, `test_strategy_commands_on_the_bots_screen.py`, `test_saved_strategy_restores_disarmed.py`).
- [x] EPIC-040G D11 is marked superseded for the Bots screen (`DECISION_2026-10-20_strategy_bot_kind.md`).

## 3. Design
The owner chose option A, 2026-10-21 ("A", through the coordinator). `VenueStrategies` loses its panel and its selected row: `can_arm` is "some venue has nothing armed", `can_disarm` "some venue is armed", both while nothing is in flight. Arm opens `ArmStrategyDialog` over every armable venue's form, with a Venue row (shown while more than one venue can arm) that switches the fields to that venue's form, and a list of what is armed; the real-money question for a mainnet venue now comes after the dialog, since the venue is chosen in it (`bots_dialogs._ask_arm`). Disarm asks `venue_chooser` (a stock `QInputDialog`, the command's verb on its button) unless one venue is armed. What is told comes from `ArmedStrategyChangedEvent`, the one source of truth, so an arm from the strategy module's boot restore is told too; `BotsView` is now an `OutputSourceView` with a Bots channel.
Not done: the two commands keep their ids and menu place; "Disarm strategy" gains its ellipsis because it can ask (`needs_input`).

## 3a. Reuse
`OutputSourceView`, `OutputChannel`, `LogListModel` (the Output pane's channels), `StrategyFormViewModel` and `StrategyArmingCoordinator` unchanged, `QInputDialog`: used. `StrategiesPanel`, `StrategyRowsModel` and `StrategyRow` are deleted with the dock.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/strategies/venue_strategies.py` | no panel; `arm`, `disarm`, what is told |
| `src/modules/bots/ui/strategies/arm_strategy_dialog.py` | `ArmQuestion`; a Venue row; the armed-now list |
| `src/modules/bots/ui/strategies/disarm_choice.py` | new: `VenueQuestion`, `venue_chooser` |
| `src/modules/bots/ui/strategies/strategy_rows.py` | deleted with the dock |
| `src/modules/bots/ui/bots_screen/{bots_view,bots_presenter,bots_dialogs,bots_commands}.py` | no dock; an Output channel; the questions; "Disarm strategy…" |
| tests | the strategy tests re-pointed; `test_strategy_state_look.py` (the deleted table's look) removed; `test_strategy_commands_on_the_bots_screen.py` new |

## 5. Testing
Unit: `test_venue_strategies.py`, `test_arm_strategy_dialog.py`, `test_strategy_commands_on_the_bots_screen.py`, `test_bots_real_money.py` (consent after the dialog), `test_the_plan_belongs_to_the_live_tab.py` (a layout saved with the Strategies dock). Integration: `test_saved_strategy_restores_disarmed.py`. Frames: `dialog~arm-strategy.png` and `dialog~disarm-strategy.png`, and the Bots mode frames of BOT-218, in the pull request's CI artifact.

## 6. Docs touched
`Docs/HLD/11_desktop_workbench.md` (the Bots row, the arming sentence, the menu row, the strategy-card row), `Docs/MODULES/bots/05-building-blocks.md`, `Docs/VOCABULARY/README.md` (Arm strategy form), EPIC-040G decision D11. SPEC-010 is only a planned row (`EPIC-026C` has not written it), so there is no spec file to update.

## Implementation notes (written when done)
- `test_strategy_state_look.py` guarded the table's armed look (`EPIC-043E`) and is deleted with the table; the armed state is told in words now.
- Real money: the question about a mainnet venue is asked after the dialog, never skipped (`test_bots_real_money.py`).
