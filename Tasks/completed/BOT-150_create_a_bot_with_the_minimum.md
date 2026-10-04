# BOT-150 — A bot is created with the minimum; its parameters are set while it is not running

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04: "lúc tạo bot, không cần nhập hết thồng số bot đâu, nhập tối thiểu, các thông số có thể change khi bot idle nhé." In English: "When creating a bot, don't ask for all its parameters, only the minimum; the parameters can be changed while the bot is idle."
**Risk:** 🟢 — a new bot carries no parameters until the user sets them. Start already refuses a plan it cannot judge.
**Complexity:** S — one dialog, one verdict, plus SPEC-014.
**SPEC:** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None

---

## 1. Context and problem

`NewBotDialog` embedded the Grid's whole parameter panel: lower and upper price, grids, spacing, capital, stop loss and take profit (`src/modules/bots/ui/bots_screen/new_bot_dialog.py`). The user filled them before the planner had read the symbol's numbers, so the ATR and Bollinger suggestions were not available there.

Editing a bot's parameters already existed:
- `EditBotCommand` is accepted while the bot is DRAFT or STOPPED (the lifecycle's EDIT).
- The detail panel edits and saves them.
- A created bot is selected.

## 2. Acceptance criteria
- [x] New bot asks only for the kind, venue, symbol and an optional name, and saves a DRAFT with no parameters.
- [x] The dialog says the parameters are set afterwards and can be changed whenever the bot is not running.
- [x] A bot without its lower price, upper price or capital has one Refused verdict naming those parameters, in the panel's words. Start is disabled with that reason; it no longer reports "lower is missing".
- [x] The parameters typed in the draft's panel are saved, and the plan can then start.
- [x] "Idle" means not running: DRAFT, or STOPPED (which returns to DRAFT). That is the lifecycle's existing EDIT rule, unchanged.

## 3. Design

- **Reuse the existing editing path (P5).** The draft's panel already edits and saves the parameters, so the dialog simply stops asking for them. No new command and no new state.
- **Name what is missing.** `GridParams.unset_parameters` lists the parameters the panel has no starting value for (lower price, upper price, capital). These are the ones a new bot lacks.
  - The panel starts grids, spacing and both exits at visible values, which the next Save writes.
  - `evaluate_grid` turns the missing parameters into one REFUSED `PARAMETERS_NOT_SET` before parsing, so the verdict asks the user to set them instead of reporting a key error.
- **Running or paused bots stay locked.** The resting ladder was laid from the saved parameters, so editing a running or paused bot is still refused, as before.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/bots_screen/new_bot_dialog.py` | No kind panel. Adds a hint label `lblNewBotParametersHint`. The command carries no config. |
| `src/modules/bots/domain/grid/grid_params.py` | `PARAMETERS_WITHOUT_A_DEFAULT`, `unset_parameters` and `unset_parameters_reason`, the one wording. |
| `src/modules/bots/application/queries/run_grid_backtest/handler.py` | The backtest asks for the same parameters (PR #349 review, finding 1). |
| `src/modules/bots/domain/grid/grid_evaluation.py` | `PARAMETERS_NOT_SET` before parsing. |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | Steps 2 and 4, a failure row, and the proof table. |

## 5. Testing
- `test_bots_dialogs.py::test_new_bot_asks_only_the_minimum_and_saves_no_parameters`: no kind panel, an empty config, and the hint. Red before the change.
- `tests/unit/modules/bots/domain/grid/test_grid_parameters_not_set.py`: the empty and the blank cases were red before the change (`PARAMETERS_UNREADABLE`); a full set still reaches the checks.
- `test_bots_presenter.py::test_a_bot_created_with_the_minimum_is_completed_in_its_draft`, run on the real bots graph:
  - creating the bot selects it as a DRAFT;
  - Start names the three parameters;
  - typing them and pressing Save stores the full config;
  - Start is then enabled.

## Implementation notes (written when done)
- Bots unit tests plus integration tests: 1035 passed; architecture, script, board and bots tests: 1546 passed; sanity (sequential): 34 passed. `ci-local.ps1 -SkipTests` PASS. The `-Full` run is the pull request's check.
- **Not yet run:** creating a bot in the real app on the user's display.
