# BOT-176 — The desktop app writes a bot plan file that a server can apply

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** The Bots mode gains Export plan…: the selected or every bot written as a `sew.bot-plan/1` file, through the same query and writer as `bot export`, so a bot designed on the desktop reaches the VPS with `scp` and `bot apply`.
**Source:** The owner, 2026-10-14: *"I need a feature, UI will have ability to gen json bot plan file"*; after the design note: *"OKI, gen design cho task nay, sao do cho subsection dev"* (OK, write the design for this task, then hand it to a sub-session to develop).
**Risk:** 🟡 — a plan exported as "running" starts real money on a server that runs `--start-planned`; the dialog must make that a deliberate choice.
**Complexity:** M — one application query shared with the CLI, one file writer shared with the CLI, one dialog, one command.
**Depends on:** None. Builds on `EPIC-038I` (`plan_export.py`, `bot_plan_document.py`, `bot export`).

---

## 1. Context and problem
A plan file is how a headless server's bots are defined (`Docs/OPERATIONS/headless_runbook.md`, "Plan files and version control"). Today it can only be written by the CLI: `ExportBotPlanVerb` (`src/modules/bots/cli/bot_plan_verbs.py:102-134`) lists the bots, reads the applied record, calls `export_plan` (`src/modules/bots/application/plan/plan_export.py`) and writes the text with an exclusive create. The owner designs and backtests bots in the desktop app, then has to recreate them by hand in JSON on the VPS. The format, the export rule and the round-trip property (`export` then `apply --dry-run` is "no changes") already exist; only the desktop has no way in.

Two pieces of the CLI verb are logic the desktop needs too, and must not be copied (the owner's standing preference: generalise shared code):
- choosing the bots and building the document (query + `export_plan` + the applied record, tolerating an unreadable record);
- writing the text without ever overwriting a file.

## 2. Acceptance criteria
- [ ] The Bots menu has **Export plan…**. It is enabled when at least one bot exists. It opens a dialog with:
  - scope: *Selected bot* (enabled only with a selection) or *All bots*, defaulting to the selection when there is one;
  - desired state: *Keep each bot's wanted state* or *All stopped*. The default is *All stopped* whenever the scope contains a bot on a mainnet venue, otherwise *Keep*;
  - one line of text saying the plan holds no key, and that the server judges it again with its own account (`bot apply --dry-run` and the pre-flight);
  - **Save…** and **Copy JSON**.
- [ ] **Save…** asks for a path through a native save dialog suggesting `bot-plan-YYYYMMDD.json`, and writes the file only if it does not exist. An existing path is refused with a message naming it; the file is untouched. The native dialog's own overwrite prompt is turned off, so the person is never asked "replace?" for a file the writer will refuse anyway.
- [ ] After a save, the person sees the path and the number of bots written, and the two commands to run on the server (`bot apply <file> --dry-run`, then `bot apply <file>`).
- [ ] **Copy JSON** puts exactly the text a save would write on the clipboard.
- [ ] The exported text for a bot is identical to what `bot export --bot-id <id>` writes for the same stored state (with *Keep*). With *All stopped*, every entry's `desired_state` is `stopped` and nothing else differs.
- [ ] `bot export` behaves exactly as before (its existing tests pass unchanged) and now uses the same query and writer.
- [ ] A write failure (permission, disk) is shown as a message with the reason; the app keeps running.

## 3. Design
**One query, two callers (CQRS, as every Bots read).** A new `ExportBotPlanQuery(bot_ids: tuple[str, ...], all_stopped: bool)` in `bots/application`, handled by `ExportBotPlanHandler`. It dispatches `ListBotsQuery`, reads `IAppliedPlanStore` (an unreadable record counts as none, as `_recorded` does today), calls `export_plan`, and, when `all_stopped`, replaces each `desired_state` with `DesiredState.STOPPED` (a `dataclasses.replace` on the frozen `PlannedBot`). It returns `BotPlanDocument`; `UnknownBotsError` propagates as today. `ExportBotPlanVerb` dispatches this query instead of assembling the parts itself, and `_recorded` stays for `apply`, or moves to the handler if `apply` no longer needs it.

**One writer, two callers.** The exclusive create (`open("x")`) moves out of the CLI verb into one function, `write_new_plan_file(path: Path, text: str) -> PlanFileWritten | PlanFileRefused` (a result value, not exceptions across the boundary; `code/errors.md`), in `bots/adapters/plan_file.py`. `PlanFileRefused` carries `reason: Literal["exists", "os_error"]` and the OS message. The CLI maps it to its existing two messages; the presenter maps it to its message box. File IO stays in the adapter layer, not in `application`.

**Why `all_stopped` and not a per-bot choice.** The risk is one direction only: a bot running on the desktop arriving as "running" on a server that starts planned bots. One switch covers it, defaults safe for real money, and keeps the dialog to stock controls. A per-bot editor is the plan file itself.

**UI (QtWidgets only, `ui-presentation-rule.md`).**
- `export_plan_dialog.py` in `bots/ui/bots_screen/`: a stock `QDialog` with two `QRadioButton` groups, a `QLabel` note, and a `QDialogButtonBox` holding Save… / Copy JSON / Close. It knows nothing about files or the dispatcher; it returns the person's choice (`ExportPlanChoice(scope, all_stopped, action)`) or `None`.
- The question is injected through `BotsDialogs` (`bots_dialogs.py`, the `EPIC-029F` shape): a new `ask_export_plan` field, plus `ask_plan_save_path` (wrapping `QFileDialog.getSaveFileName` with `QFileDialog.Option.DontConfirmOverwrite`, the shape of `backtesting/ui/logic/report_file_dialogs.py`). Tests hand in plain functions.
- The command is one `QAction` in `bots_commands.py` (Bots menu, not the toolbar), enabled by a rule next to the others in `bot_action_rules.py`. `test_bots_mode_catalogue.py` gets its row.
- The presenter dispatches `ExportBotPlanQuery`, calls the writer or `QGuiApplication.clipboard().setText`, and reports the outcome through the screen's existing message path. The work is a local read and a write of a few kilobytes, so it runs on the UI thread; no coordinator is needed (`async-ui-action-rule.md` covers network and long work). If the presenter's size ratchet objects, put the export flow in its own small `plan_export_flow.py` collaborator the presenter owns.
- Mainnet detection uses `TradingVenue.is_mainnet`, not a list of names.

**Out of scope (later task):** opening a plan in the desktop and showing what `apply` would change; applying a plan from the desktop; editing a plan.

## 3a. Reuse
- Plan format and export rule: used `BotPlanDocument.to_json_text`, `export_plan`, `desired_state_of` (`bots/application/plan/`).
- Listing bots: used `ListBotsQuery`.
- Applied record: used `IAppliedPlanStore`.
- Injectable questions: used `BotsDialogs` (`bots_dialogs.py`).
- Save dialog shape: mirrored `ReportFileDialogs` (`backtesting/ui/logic/report_file_dialogs.py`); not imported, because that class is the Backtest screen's.
- Risky-action wording: checked `VerbQuestion` / `ask_with_verbs` (`support/ui_kit/verb_confirmation.py`); not used because the dialog asks for options, not a yes/no.
- Mainnet test: used `TradingVenue.is_mainnet`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/queries/export_bot_plan/` | `ExportBotPlanQuery` and its handler; registered where the other Bots queries are |
| `src/modules/bots/adapters/plan_file.py` | `write_new_plan_file` and its two result types |
| `src/modules/bots/cli/bot_plan_verbs.py` | `ExportBotPlanVerb` dispatches the query and calls the writer; same exit codes and messages |
| `src/modules/bots/ui/bots_screen/export_plan_dialog.py` | The dialog and `ExportPlanChoice` |
| `src/modules/bots/ui/bots_screen/bots_dialogs.py` | `ask_export_plan`, `ask_plan_save_path` |
| `src/modules/bots/ui/bots_screen/bots_commands.py`, `bot_action_rules.py` | The Export plan… action and its enablement |
| `src/modules/bots/ui/bots_screen/bots_presenter.py` (or `plan_export_flow.py`) | The flow: ask, query, write or copy, report |
| `src/modules/bots/ui/bots_screen/preview.py` / `preview_frames.py` | A frame for the dialog |
| `Docs/OPERATIONS/headless_runbook.md` | One line under "Plan files": the desktop's Export plan… writes the same file |
| `Docs/SPEC/` (the Bots use case that lists its commands) | Export plan… added |

## 5. Testing
| Criterion | Test (tier) |
| :--- | :--- |
| Query output equals the CLI's for the same state; `all_stopped` changes only `desired_state`; unknown id raises; unreadable record counts as none | Handler unit tests with an in-memory store (unit) |
| Never overwrites; OS error returned as a value | `write_new_plan_file` on `tmp_path` (unit) |
| `bot export` unchanged | Existing CLI tests unchanged and green (unit/integration) |
| Desktop export applies cleanly | Export through the presenter with injected dialogs to `tmp_path`, then parse and `PlanApplier.preview` reports no change (integration) |
| Default *All stopped* for a mainnet bot; *Keep* otherwise; Selected disabled with no selection | Dialog unit tests (unit, offscreen) |
| Copy JSON equals saved text | Presenter test with a clipboard double (unit) |
| Menu row and enablement | `test_bots_mode_catalogue.py` row; action-rule test (unit) |
| Look | `preview.py` frame (eye) |

A mutation check per `testing-rule.md`: break the `all_stopped` replacement and the exclusive create, and see a test turn red.

## Implementation notes (written when done)
_Pending._
