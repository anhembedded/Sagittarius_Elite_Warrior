# BOT-179 — Export plan… is on the Bots toolbar, and its path is proven kind-neutral

**Status:** ✅ Done (2026-10-14)
**Board:** Export plan… joins the Bots toolbar beside the lifecycle commands as the same one `QAction` as the menu entry; the export path (command, query, document, writer) is proven to name no bot kind, by a second-kind round-trip test and an import-direction guard.
**Source:** The owner, 2026-10-14: *"giờ làm cái nút export plan đi. chức năng này phải là common nhé"* (make the export-plan button now; this function must be common to every bot kind).
**Risk:** 🟢 — one flag on an existing command; the dialog, flow and writer are unchanged.
**Complexity:** S — a toolbar flag, one round-trip test, one guard extension.
**SPEC (optional):** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None. Builds on `BOT-176` (the command, dialog, flow, query, writer) and `BOT-177` (the shell-versus-kind guard).

---

## 1. Context and problem
`BOT-176` registered Export plan… with `on_toolbar=False` (`src/modules/bots/ui/bots_screen/bots_commands.py`). The owner looked for a button and found none: the command lived only in the Bots menu. The owner also wants the function common to every bot kind, not a Grid feature.

## 2. Acceptance criteria
- [x] The Bots mode toolbar shows **Export plan…** after the lifecycle commands, as the same `QAction` (same command id, availability, dialog) the menu holds; no second action. The 1024×700 conformance suite stays green; the bots_screen preview shows it.
- [x] The export path names no bot kind: the command sits in the shared bots screen, the query, `plan_export.py` and the writer treat `kind` and `config` as opaque, the parser asks `IBotKindCatalog`. Recorded below from the code.
- [x] A bot of a second, fake kind registered in a test catalog exports, and the file round-trips with `bot apply --dry-run` as "no changes".
- [x] A guard fails when a file under `application/plan/`, `application/queries/export_bot_plan/` or the export UI imports a kind (`application/kinds/`, `domain/grid/`, `ui/kinds/`); it has a probe and no baseline entry.
- [x] `BOT-176`'s behaviour and tests are unchanged: Selected/All, Keep/All stopped (default for mainnet), Save… never overwrites, Copy JSON, access key A.
- [x] `Docs/MODULES/bots.md`, HLD §11.2.3 and SPEC-014 say where export lives, that it is on the toolbar and that it is kind-neutral.

## 3. Design
One flag: `on_toolbar=True` on the existing `EXPORT_PLAN` contribution. The Engine builds menu item and toolbar button from the one descriptor, so they are one `QAction` by construction. Command order already puts it after Stop…, so the menu order is unchanged and the toolbar reads `… Stop…, Export plan…`.

The kind-neutrality guard extends BOT-177's `files_importing_a_kind` helper over the export path instead of copying its AST walk.

## 3a. Reuse
- Toolbar action: used the Engine's `CommandContribution.on_toolbar` (`bots_commands.py`); no new widget.
- Import-direction scan: used `files_importing_a_kind` from `tests/unit/architecture/test_bots_services_stay_grouped.py`.
- Second-kind test: used `StubKind`, `CommandWorld`, `BotKindCatalog` from `plan_world.py`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/bots_screen/bots_commands.py` | Export plan… on the toolbar |
| `tests/integration/presentation/ui/test_bots_mode_catalogue.py` | toolbar list gains Export plan… |
| `tests/unit/modules/bots/application/plan/test_export_of_a_second_kind.py` | second-kind round trip |
| `tests/unit/architecture/test_bots_export_path_names_no_kind.py` | import-direction guard and probe |
| `Docs/HLD/11_desktop_workbench.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/MODULES/bots.md` | wording |

## 5. Testing
Unit (second-kind round trip, guard and probe), integration (toolbar catalogue, conformance at 1024×700), preview frame by eye.

## Implementation notes (written when done)
**Criterion 2, from the code: the export path is common, nothing moved.**
- The command is `EXPORT_PLAN` in the shared `ui/bots_screen/bots_commands.py`; `ui/kinds/` holds none of it.
- `application/queries/export_bot_plan/handler.py` lists `BotSnapshot`s and calls `export_plan`; `plan_export.py` and `adapters/plan_file.py` read `kind` and `config` as opaque values; their import lines and text name no Grid type.
- `bot_plan_parser.py` checks a plan's kinds against `IBotKindCatalog`, so a new kind needs no change on the path.
- No import of `application/kinds/`, `domain/grid/` or `ui/kinds/` anywhere on it, so no file was moved. The guard `test_bots_export_path_names_no_kind.py` now holds that (BOT-177's `files_importing_a_kind`, whose kind list gains `ui/kinds`); its probe turns it red for each of the three kind packages.

**Evidence.**
- `test_export_of_a_second_kind.py`: a bot of `second_kind` with its own config goes through the real query and writer; the parsed file applies as "no changes" with `diff_plan`, and a catalog without that kind refuses the file.
- Toolbar: `test_bots_mode_catalogue.py` (toolbar list now ends `Stop…`, `Export plan…`; menu unchanged). A grab of the real Bots toolbar at 1024×700 shows it beside Stop… with no overflow chevron; greyed while no bot exists, per `BOT-176`'s availability.
- `test_workbench_conformance.py`: Bots passes at 1024×700, 1366×768 and 1920×1080. `backtest@1024x700/fits_the_window` fails (needs 719×706) in this Linux container with and without this change; it is not Bots.
- Commit tier and the touched suites: see the PR. The `-Full` run is GitHub Actions'.
