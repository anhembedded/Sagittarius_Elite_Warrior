# BOT-176 — The desktop app writes a bot plan file that a server can apply

**Status:** ✅ Done (2026-10-14)
**Board:** Bots → Export plan… writes the selected or every bot as a `sew.bot-plan/1` file through the one `ExportBotPlanQuery` and the one never-overwrite writer `bot export` now shares; *All stopped* is the default whenever a mainnet bot is in scope, so a copied plan starts no real money under `--start-planned`.
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
- [x] The Bots menu has **Export plan…**. It is enabled when at least one bot exists. It opens a dialog with:
  - scope: *Selected bot* (enabled only with a selection) or *All bots*, defaulting to the selection when there is one;
  - desired state: *Keep each bot's wanted state* or *All stopped*. The default is *All stopped* whenever the scope contains a bot on a mainnet venue, otherwise *Keep*;
  - one line of text saying the plan holds no key, and that the server judges it again with its own account (`bot apply --dry-run` and the pre-flight);
  - **Save…** and **Copy JSON**.
- [x] **Save…** asks for a path through a native save dialog suggesting `bot-plan-YYYYMMDD.json`, and writes the file only if it does not exist. An existing path is refused with a message naming it; the file is untouched. The native dialog's own overwrite prompt is turned off, so the person is never asked "replace?" for a file the writer will refuse anyway.
- [x] After a save, the person sees the path and the number of bots written, and the two commands to run on the server (`bot apply <file> --dry-run`, then `bot apply <file>`).
- [x] **Copy JSON** puts exactly the text a save would write on the clipboard.
- [x] The exported text for a bot is identical to what `bot export --bot-id <id>` writes for the same stored state (with *Keep*). With *All stopped*, every entry's `desired_state` is `stopped` and nothing else differs.
- [x] `bot export` behaves exactly as before (its existing tests pass unchanged) and now uses the same query and writer.
- [x] A write failure (permission, disk) is shown as a message with the reason; the app keeps running.

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
Delivery state: draft PR; the `ci-local.ps1 -Full` run on GitHub is the full-gate authority and is pending. Not run here: a look at the dialog on a real display (offscreen only; the `build_export_plan_preview()` frame in `preview.py` is the owner's visual check), and a real save through the native `QFileDialog` (the dialogs are injected in every test).

**Evidence per criterion**
| Criterion | Evidence |
| :--- | :--- |
| Menu command, enabled while a bot exists; dialog scope / state / note / Save… / Copy JSON; defaults | `test_bots_export_plan.py::test_export_plan_is_disabled_without_a_bot_and_says_why`, `test_export_plan_dialog.py` (mainnet default, Selected disabled with no selection, default follows scope until a state is picked), `test_bot_action_rules.py`, `test_bots_mode_catalogue.py` row |
| Save… never overwrites; existing path refused by name, file untouched; native overwrite prompt off | `test_plan_file.py`, `test_bots_export_plan.py::test_an_existing_file_is_refused_by_name_and_left_untouched`; `QFileDialog.Option.DontConfirmOverwrite` in `bots_dialogs.py` (not exercised by a test: it is a native dialog) |
| After a save: path, count, the two server commands | `test_the_success_message_names_the_file_the_count_and_the_server_commands` |
| Copy JSON equals what a save writes | `test_plan_export_flow.py` (clipboard double), `test_copy_json_puts_exactly_the_text_a_save_would_write` (real clipboard) |
| Text identical to `bot export`; *All stopped* changes only `desired_state` | `test_export_bot_plan_query.py`, `test_save_writes_what_bot_export_would_write`, `test_all_stopped_writes_every_entry_stopped` |
| `bot export` unchanged | `test_bot_plan_verbs.py` passes with no edit to a test (24 CLI tests) |
| Write failure shown with the reason, app keeps running | `test_a_write_failure_shows_its_reason_and_the_screen_keeps_running` |
| Desktop export applies cleanly | `test_export_plan_from_the_desktop_on_the_fake_exchange.py` (composed app: export through the screen, parse, `PlanApplier.preview` finds no change) |

**Mutation checks (testing-rule §2)**, each broken, run, restored: `all_stopped` ignored (3 red), `all_stopped` writing RUNNING (3 red), exclusive create changed to overwrite (3 red), Copy JSON altering the text (2 red), the flow not passing `all_stopped` (2 red); wiring: the `ExportBotPlanQuery` binding removed (9 failed, 7 errors) and the `export_plan_requested` connection removed (8 red).

**Decisions where the design met the code**
- **Presenter size ratchet.** `bots_presenter.py` was at 398 of 400 lines, so the flow is the collaborator the task allowed, `plan_export_flow.py` (`PlanExport`). It connects itself to `export_plan_requested` and reads the view model's bots and selection, so the presenter gained one construction line and one import (exactly 400, not over).
- **Result vs. report.** Failures go through `INotifier` as a command failure (modal box, reason behind Details…); the success is the status line plus a toast whose detail carries the two server commands. A status line holds one line, and `ui-presentation-rule.md` §10 routes "something happened" to a toast.
- **`_recorded` left the CLI.** Only `export` used it; the unreadable-record rule now lives once in `ExportBotPlanQueryHandler`. `ExportBotPlanVerb` dispatches the query. The CLI's tests built the verb world with the dispatcher and the record store as separate objects, so `tests/unit/modules/bots/cli/verb_world.py` (a helper, not a test) routes the query to the handler over the world's own record store, as the app's container does.
- **`all_stopped` as a bool on the query** is the task's design; a per-bot editor stays the plan file itself.
- **Access key.** Every letter of "Export plan…" was another Bots command's key, and the Engine refuses a command with no key. "Export pl&an…" takes A from *Suggest from ATR*, which moves to G (`Su&ggest from ATR`), which Bollinger frees by moving to B (`Suggest from &Bollinger`). HLD §11.2.3 and the catalogue row changed with them.
- **Menu position.** Last among the Bots commands before Live stream (the menu groups Live stream last); not on the toolbar.
- **File name.** The suggested `bot-plan-YYYYMMDD.json` is built from `date().isoformat()`, not `strftime`, because `test_display_values_go_through_the_formatter.py` forbids formatting in UI code and a file name is not a value a person reads.
- **Duplication ratchet.** The new method names were renamed (`export_plan`, `_report_refusal`) rather than the baseline raised: `run` and `_refused` were already defined in other UI packages.
- **Test tier.** The task's "integration" row for the desktop round trip is `tests/integration/modules/bots/`, on the booted app, so it also proves the query is bound in the real container.

Out of scope, unchanged: importing or applying a plan from the desktop.

