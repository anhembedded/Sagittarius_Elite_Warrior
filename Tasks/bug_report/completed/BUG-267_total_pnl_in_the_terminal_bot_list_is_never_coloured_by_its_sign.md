# BUG-267 — `bot list` at a terminal prints Total PnL plain while Grid profit and Realised are coloured

- **Reported:** 2026-10-22 (review of PR #716, finding 5, and the coordinator session)
- **Severity:** 🟢 P3 — a loss in the Total PnL column is not red at a terminal; the figure and its sign are still printed, so nothing is hidden.
- **Status:** ✅ Fixed (2026-10-22)
- **Board:** The terminal `bot list` never coloured its Total PnL column because the renderer looked the colour up by the head text `TOTAL PNL` and the real head is `TOTAL PNL (NET)`; a money cell now carries its kind (`CellKind.MONEY`) and the renderer colours by that, so a renamed head cannot drop it.
- **Context:** `bot list` / `bot show` at a terminal → `shell/` (`rich_text_report_renderer.py`) and `core/contracts/report.py`; the commands in `src/modules/bots/cli/`
- **Environment:** Linux offscreen test run at `dbe9895` (master-warrior after #716); any terminal that wants colour.

## Reproduction
1. Seed a stopped bot with a total of 1,230.25 and a Futures bot with a total of -1,430.87 (the fixtures of `test_bot_earnings_reports.py`).
2. Render the real `bot list` report with `TerminalAwareTextRenderer` at 200 and at 80 columns.
3. Expected: the Grid profit, Realised and Total PnL figures coloured by their sign. Actual: Grid profit and Realised were green, Total PnL (30.00 and -1,430.87) carried no escape code, in the table and in the stacked layout.

## Symptom
The 200-column output of the real list, at `dbe9895`: `\x1b[32m20.00   \x1b[0m   30.00 ` (Realised coloured, Total PnL plain); the loss row printed `-1,430.87` with no `\x1b[31m`.

## Root cause
`src/shell/rich_text_report_renderer.py:63` (`_MONEY_HEADS`) and `:64` (`_MONEY_LABELS`) at `dbe9895` held `"TOTAL PNL"`, and `_style_of` (`:79`, `if kind in money` at `:92`) matched the column head or label text against them. The list's head is `TOTAL_PNL_HEAD`, `"TOTAL PNL (NET)"` (`src/modules/bots/contracts/run_earnings.py:39`, used at `src/modules/bots/cli/bot_status_reports.py:74`), so the real column never matched. The mechanism is the design: what a cell is was inferred from the words around it, so any rename silently drops the colour. The tests hid it because they built their own report with the short head `"TOTAL PNL"` (`test_wide_report_on_a_terminal.py`, `test_terminal_report_text.py`), never the real command's head. The gate was green while the defect was live; no case study, because the same blind spot is not open for money any more, and the state and side columns, still found by head text, are named in `CellKind`'s docstring as the next members.

## Fix
`ReportCell` gains `kind: CellKind = CellKind.TEXT` (`src/core/contracts/report.py`); the commands set `CellKind.MONEY` on their money cells (`bot_status_reports.py` `_row`, `bot_earnings_rows.py` `_row` for Realised, Grid profit and Total PnL); the renderer colours a `MONEY` cell by its sign and no longer holds money head or label sets (`_style_of`, `_block`). The stacked layout keeps the value cell's kind, so it needs no separate lookup. The renderers that ignore colour (plain text, JSON) are untouched.

## Regression test
`tests/unit/modules/bots/cli/test_bot_report_colours_at_a_terminal.py::test_the_real_bot_list_colours_every_money_column_by_its_sign` (200 and 80 columns) renders the real list through the terminal renderer; it failed before the fix on `Total PnL, a profit` at both widths, and passes after. The defect lived on the list's head path only: `bot show` matched its labels (`Grid profit`, `Realised`, `Total PnL`) and was already coloured, so `::test_the_real_bot_show_colours_realised_grid_profit_and_total_pnl_by_their_sign` passed before the fix too; it guards the new mechanism for `bot show` (it fails when one of those rows loses `CellKind.MONEY`). `tests/unit/shell/test_money_cell_colour_follows_its_kind.py::test_a_money_cell_is_coloured_whatever_its_column_is_called` locks the rename. Mutations that now fail a test: the list's money cell not `MONEY`, the renderer ignoring the kind, `bot show`'s Total PnL, Grid profit or Realised not `MONEY`.

## Verification
Regression tests red before the fix (the list test at both widths), green after; `tests/unit/shell` and `tests/unit/modules/bots/cli` 403 passed; the commit tier (`ci-local.ps1 -SkipTests`) passes. The full gate is the GitHub run on the PR's head.
