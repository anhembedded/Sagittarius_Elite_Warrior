# BOT-231 — The summary tables show the Realised figure

**Status:** ✅ Done (2026-10-22)
**Board:** The owner read the profit a LONG grid takes as the price climbs (selling its opening inventory level by level) as "not counted in any column"; it is in `realised_total`, but `bot list` and the Bots tab table showed only Grid profit, Cycles and Total PnL, so both now carry a Realised column between Cycles and Total PnL, no book and no total changed.
**Source:** Coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, 2026-10-22, from the owner's reading of a LONG grid: the profit from selling opening inventory "is not counted in any column".
**Risk:** 🟢 — display only; the figure is `RunEarnings.realised` / `PnlSummary.realised`, read as before.
**Complexity:** S — one column in two tables, one legend clause, tests, frames.
**Depends on:** BOT-229 (done): the figure and its words exist.

---

## 1. Context and problem
BOT-229 made `bot show`, the Bots tab Results group and `--json` list every earnings figure. The two summary surfaces the owner reads daily, the `bot list` table and the Bots tab's bots table, still showed Grid profit, Cycles and Total PnL (`bot_status_reports.py` → `_EARNINGS_HEADS`, `bots_table_models.py` → `BotsTableModel.COLUMNS` at `cc64f3d`). `--json` already carries `realised` (`bot_status_report.py` → `_earnings_payload`).

## 2. Acceptance criteria
- [x] `bot list` prints a `REALISED` column between `CYCLES` and `TOTAL PNL (NET)`, `realised_total` net of fees in quote units, written like the neighbouring money columns; `—` when the run was not judged.
- [x] The Bots tab's bots table has a `Realised` column in the same place, a signed money column coloured by the meaning table.
- [x] `bot list --json` carries `earnings.realised` (already true; the existing test locks the exact key).
- [x] The `bot list` legend gains a line: Realised is everything sold so far against the average cost, includes Grid profit's cycles, so Grid profit is part of it, not an addition.
- [x] The narrow terminal fallback (stacked one block per bot, BOT-198) carries the Realised field.
- [x] No book and no total changes.
- [x] The Bots tab table's width: reported, nothing shrunk (see Implementation notes).

## 3. Design
`REALISED_HEAD`, `REALISED_COLUMN_TITLE` and `REALISED_LEGEND` live in `run_earnings.py` beside the other earnings words, the one place the tab and the commands take them from; `realised_text` already existed (BOT-229). The terminal renderer's money heads gain `REALISED` so its sign colour follows the other money columns.

## 3a. Reuse
`RunEarnings`, `realised_text`, `plain_money`, `Tone`/`sign_tone`, `signed_key`, `ColumnSpec`/`ColumnKind.MONEY` (the tab's existing money column), `_stacked` of the terminal renderer (the block layout takes every head, so no new code): used. No new widget.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/run_earnings.py` | `REALISED_HEAD`, `REALISED_COLUMN_TITLE`, `REALISED_LEGEND` |
| `src/modules/bots/cli/bot_status_reports.py` | the `REALISED` column in the list's head and rows, the legend line |
| `src/modules/bots/ui/bots_screen/bots_table_models.py` | the `Realised` column, its value and tone |
| `src/shell/rich_text_report_renderer.py` | `REALISED` is a money head (sign colour) |
| `Docs/OPERATIONS/headless_runbook.md`, `Docs/MODULES/bots/07-deployment.md` | the list's columns and legend |

## 5. Testing
Unit tier. `test_bot_earnings_reports.py` (column order, both cells, legend, JSON key), `test_wide_report_on_a_terminal.py` (the eleven-column list at 120/100/80/40/30 columns loses no field), `test_bot_facts.py` (the tab's column order, value, blank while not judged), `test_bots_tables_colour_by_meaning.py` (sign colour, light and dark). Frames: `BOT-231_assets/bots-tab-{light,dark}.png` (`plan_dock_frames running_bot`; a dark Fusion palette stands in for the Windows scheme on the offscreen platform).

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` (`bot list` paragraph), `Docs/MODULES/bots/07-deployment.md` (the earnings paragraph).

## Implementation notes
- Width of the Bots tab table: its columns sum to 731 px with the new column, 656 px before (+75 px: the header and a signed money cell); at the frame's size they all fit. The table has no minimum width of its own (its minimum size hint is 70 px, unchanged), so a narrower list is cut or scrolled by the same mechanism as before; no other column was shrunk or hidden. A narrow-width check in the offscreen harness was not conclusive, so that part is reported, not claimed.
- Review round 1 (reviewer session `session_016SBVmXdzx5n6DLD1oLwqqm`): the stacked 80-column layout looked the colour up in `_MONEY_LABELS`, not `_MONEY_HEADS`, so Realised had no sign colour there; it is now in both, with a test at 200 and 80 columns. The `bot list` test used a fixture whose realised equalled its total; bot `ffffff` now has grid profit 1,234.50, realised 20.00 and total 30.00, and the reviewer's three mutations (Realised cell prints the total; `REALISED` out of the heads; out of the labels) each fail a test.
- The reviewer measured the column sums with a negative figure: 615 px before, 702 px after (viewport 563 and 638); the cost is about 75-90 px and grows with the digits of the figures, not a fixed width. At the 1024x700 window the Bots dock's table area is about 638 px, so with a bot listed Total PnL may need a horizontal scroll; the owner's call whether that is acceptable.
- Existing, not caused here: the list's real head is `TOTAL PNL (NET)` but the renderer's money sets hold `TOTAL PNL`, so the real Total PnL column is never sign-coloured in the terminal; the test head hides it. Left for its own task.
