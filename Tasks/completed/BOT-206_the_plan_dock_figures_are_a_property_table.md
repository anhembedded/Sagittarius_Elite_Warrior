# BOT-206 — The Plan dock's figures are a grouped property table, not one long label/value list

**Status:** ✅ Done (2026-10-20)
**Board:** The Plan dock's readiness steps and figures are one grouped property tree (stock `QTreeView`, Engine `configure_item_view`; words unchanged, a word left and a figure right by the kind of its row) instead of a 22-row label/value form; Margin mode and Liquidation (est.) stay in the Grid editor.
**Source:** the owner, 2026-10-20: "Phần đó, UI nên đưa vào table đi chứ nhỉ?" (shouldn't that part be a table?), about the Plan dock's long label/value list; handed down by the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu).
**Risk:** 🟢 — presentation only: the words are still built in `run_earnings.py`, `bot_facts.py`, `bot_ladder_facts.py` and `readiness_words.py`; tests that read the old labels change to read the table.
**Complexity:** M — one new widget over a stock `QTreeView`, the panel rewired to it, four tests rewritten, three preview frames.
**Epic (optional):** none; EPIC-040 reshapes the Bots screen's centre in parallel and this task stays inside the Plan dock.
**SPEC (optional):** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** BOT-202 (the Total PnL wording), BOT-193 (the ladder rows).

---

## 1. Context and problem
`BotPlanPanel` (`src/modules/bots/ui/bots_screen/bot_plan_panel.py`, `FACT_SPECS`) shows the selected bot as one Engine `ReadoutForm`: 22 label/value rows with no grouping, under a three-line readiness label. Margin mode sits in the kind's editor, the steps in a label, the figures in the form: three shapes for what is one property list, and the panel scrolls. The owner asked for a table.

## 2. Acceptance criteria
- [x] The Plan dock shows the bot's properties as a two-column tree (property, value) built from stock Qt (`QTreeView` over `QStandardItemModel`), configured by the Engine's `configure_item_view`, with four collapsible group headings: **Readiness** (Connect, Design, Run), **Plan** (venue, symbol, capital, grid step, profit per cycle, lower and upper edge, stop loss, take profit, liquidation price), **Results** (running time, profit from completed cycles, cycles, average per cycle, Total PnL with its net-of-fees wording, unrealised, HODL benchmark, commissions, funding) and **Holdings** (held with its average, left from earlier runs, last price heard with its age).
- [x] Every property title and value is the text it was before (same words, same formatter); no figure is new or computed differently.
- [x] The blocking reason ("Start: N things left" and each item with its fix) is text above the table, with the platform's stop sign beside it while something blocks Start; it is never a cell.
- [x] A value reads by the kind of its row (owner, 2026-10-20: "căn như đề xuất"): words (venue, symbol, step states, liquidation sentence) left, figures (capital, prices, percentages, PnL, durations) right and, where digits line up, in the platform's fixed-pitch font; rows are selectable, several at once, and Ctrl+C on the table puts "property⇥value" lines on the clipboard.
- [x] A group heading collapses and expands and keeps its state while the figures refresh; a Spot bot shows no commissions, funding or liquidation rows, a bot with a run shows no Readiness group, and a group with no row to show is hidden.
- [x] The workbench conformance suite (item views, alignment, digit font, scroll areas) stays green with the table in the Bots mode.
- [x] Preview frames for a draft bot with a blocking reason, a running Futures bot with a position, and a Spot bot.

## 3. Design
**Widget.** The Engine configures a grouped `QTreeWidget` in place, but the conformance suite reads a view's column kinds from a `SpecProxyModel` in its model chain and a `QTreeWidget` has none ("its column kinds cannot be read"). So the table is a `QTreeView` over a `QStandardItemModel` with `configure_item_view(view, model, specs, sortable=False)` (the order of a property list is its meaning), the same call every table makes (`ui-presentation-rule.md` §9). `setRootIsDecorated(True)` is switched back on after it, because group headings collapse.

**Right-aligned values.** A column's kind decides its alignment and the suite fails a text column that is right-aligned, so the Value column is `ColumnKind.QUANTITY`: right-aligned, written in the fixed-pitch font by the model's `FontRole` (`kind_font`), and a string is written "as given" by `APP_VALUE_FORMATTER`, so a sentence the screen's words already built is untouched. Property titles are `ColumnKind.TEXT`, left.

**Rows are data.** `plan_property_rows.py` lists groups and rows (key and title); the panel writes `bot_facts` and `ladder_facts` values by key as it wrote them into the form. The three readiness steps come from `readiness_words.step_rows`, which `step_lines` now numbers, so the words exist once.

**The blocking reason stays outside.** `readiness_header` and `readiness_items` stay labels above the table (they were), with the stop sign `ui-presentation-rule.md` and `grid_panel._mark` use ("a sign beside the sentence, from the platform's own icons").

**Left as is, on purpose.** The kind editor's read-only *Margin mode* and *Liquidation (est.)* rows stay in the Grid editor: the second is a live estimate of the plan being edited (`grid_liquidation.py`, fed by the guard's verdicts), not a recorded figure, and moving them would change the kind-panel contract (`BotKindPanel`, nine tests) that EPIC-040 does not touch and this task was told to stay clear of. The table's *Liquidation price* row is the ladder's, as before.

## 3a. Reuse
- Table configuration: used the Engine's `configure_item_view` (`Selection.EXTENDED`, `sortable=False`) and `APP_VALUE_FORMATTER`; `SpecTable` is a flat `QTableView` and cannot group, so a `QTreeView` is the stock control that can.
- Fixed-pitch digits: used `kind_font`.
- Empty case: the panel's existing `empty_page`.
- Words: used `bot_facts`, `ladder_facts`, `readiness_words`, `run_earnings.TOTAL_PNL_BASIS`; nothing re-worded.
- Sign beside a blocking sentence: the platform's `QStyle.standardIcon`, as `grid_panel._mark`.
- Text in a label: `plain_label`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/bots_screen/plan_property_rows.py` | new: the groups and rows as data |
| `src/modules/bots/ui/bots_screen/plan_property_grid.py` | new: the tree, its model, visibility, copy |
| `src/modules/bots/ui/bots_screen/bot_plan_panel.py` | the form and the steps label give way to the grid |
| `src/modules/bots/ui/bots_screen/readiness_words.py` | `step_rows`, shared by `step_lines` |
| `src/modules/bots/ui/bots_screen/bot_ladder_facts.py` | docstring names the rows' new home |
| `src/modules/bots/ui/bots_screen/plan_table_frames.py` | new: the three preview frames |
| `tests/unit/modules/bots/ui/bots_screen/…` | see 5 |

## 5. Testing
Unit tier, QtWidgets offscreen; the conformance suite is the integration proof.
| Criterion | Proof |
| :--- | :--- |
| groups, rows, titles | `test_plan_property_grid.py` |
| same words | `test_bot_facts.py`, `test_bots_view.py`, `test_bot_ladder_panel.py` read the table instead of the form |
| blocking reason above | `test_bots_view.py::test_the_plan_shows_the_three_steps…` |
| alignment, font, copy, collapse | `test_plan_property_grid.py` |
| conformance | `tests/integration/presentation/ui/` booted suite (CI) |
| frames | `test_plan_table_frames.py` |

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (the Plan panel's figures are a property tree); `Docs/HLD/11_desktop_workbench.md` §11.2.1 (Plan row).

## Implementation notes (written when done)
**Evidence at the author's first head (later heads: the PR's review comments and `-Full` runs)** (the `-Full` run on GitHub is the gate authority and is recorded on the PR, not here):
- Commit tier: `ci-local.ps1 -SkipTests` PASS (ruff, format, mypy over 1968 files, reference check); `tests/unit/architecture` 984 passed.
- Bots unit and integration tier plus `tests/unit/support/ui_kit` and `tests/integration/presentation/ui`: 5768 passed, 3 skipped, 1 failed. The failure, `test_workbench_conformance[True-1024x700]` ("backtest@1024x700/fits_the_window: needs 719x706"), is the Backtest mode and reproduces identically on the untouched base (`03e5dc5`) in this container, so it is not this change; the Bots mode passes the same suite at 1024×700, 1366×768 and 1920×1080, including the column, alignment and digit-font checks the table is held to.
- Mutation checks on the table (each turns exactly one test red, then restored): drop the `sectionResized` wiring (row heights), drop the Ctrl+C connection, stop hiding an empty group, keep the vertical scroll bar, Value column kind `TEXT`, re-expand every group on each refresh.

**Decisions taken.**
1. *`QTreeView`, not `QTreeWidget`.* The Engine configures a grouped `QTreeWidget` in place, but the conformance suite reads a view's column kinds from a `SpecProxyModel` in its model chain and flags a configured `QTreeWidget` ("its column kinds cannot be read"). `QTreeView` over `QStandardItemModel` goes through the same `configure_item_view` call as every table.
2. *Alignment by row kind.* First built as a `QUANTITY` column (everything right); the owner then decided text left and numbers right. The Engine's `KindDelegate` aligns by column kind only, so `RowKindDelegate` (`row_kind_delegate.py`) is that delegate with the alignment of the kind a row names (`PropertyRow.kind`, answered in `ROW_KIND_ROLE`); the font follows the same kind (`kind_font`). The column stays declared `QUANTITY`, which is what its first row (a heading holding no value) shows the conformance checks; the formatter writes a string as given, so sentences are untouched.
3. *Rows wrap.* `QTreeView` paints wrapped text but sizes a row from one line (the long Total PnL title was clipped to its first line). Each row's height is asked of its wrapped text (`SizeHintRole`) and asked again on every resize. Both columns share the width equally: the last stretches and the first is held at half, because `setSectionResizeMode` is banned per view (`test_stock_controls_only`, `item_view_config`).
4. *No scroll bar on the table.* The panel scrolls once (§3). `test_bots_view.py::test_no_push_button_of_the_mode_and_no_scroll_area_inside_another` counts any `QAbstractScrollArea` inside the Plan's scroll area; it now skips an item view that has both bars off and is sized to its contents (`_is_grown_to_its_rows`), and `test_plan_property_grid.py` holds both properties. This narrows a guard on purpose: **the reviewer and the owner should look at that one clause.** Any nested view that can scroll is still reported: round 1 of the review asked the exemption to also require no scroll range (a hidden bar does not stop the wheel), and that check found a real defect: inside the real Bots window at 1024×700 the panel's scroll area squeezed the `Expanding` table to 70 px of its 429 px hint and it scrolled by itself (my frames were 1500 px tall and hid it). The table now has a `Minimum` vertical size policy, so its hint is the least height it gets and the panel scrolls once.
5. *Copy.* Ctrl+C on the focused table (a `QShortcut` with widget context, `QKeySequence.StandardKey.Copy`) puts the selected rows on the clipboard as `property⇥value` lines. It is the list view's own standard command, so it has no menu entry; the rule "no command reachable only by a shortcut" is about the application's commands.
6. *Margin mode and Liquidation (est.) stay in the Grid editor,* and the table's Plan group has the ladder's *Liquidation price* row, as the dock always had. The estimate is the guard's live verdict on the plan being edited, and moving the two rows changes the `BotKindPanel` contract and nine tests on a surface EPIC-040 does not touch. A follow-up can move them: it is one read-only row each. This is the one place the owner's list ("Plan: …, margin mode, …, liquidation estimate") is not followed to the letter.
7. `readiness_words.step_lines` (numbered "1. Connect: done") became `step_rows` (step and words); the numbers were redundant with the row order.
8. Two member names the duplicate-members guard counts (`value_text`, `_lay_out`) are named `shown_value` and `_set_up_view` in the grid, so the baseline did not move.

**Frames** (`plan_table_frames.py`; `python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_table_frames <frame> [--png path]`): `Tasks/completed/BOT-206_assets/draft_blocked.png`, `futures_running.png`, `spot_running.png`, rendered offscreen on Linux; on Windows the same command without `--png` opens each in the platform's own look.
