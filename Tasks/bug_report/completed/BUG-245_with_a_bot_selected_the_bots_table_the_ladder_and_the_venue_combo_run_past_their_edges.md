# BUG-245 — With a bot selected, the Bots table, the Ladder table and the venue combo run past their edges

- **Reported:** 2026-10-21 (the first run of the new conformance case with a bot selected, `BOT-212`; the delivery coordinator asked for the record)
- **Severity:** 🟢 P3 — columns and a combo's text are cut off at the window sizes the suite measures; nothing is lost (a table scrolls sideways) but the person reads a clipped header or `Spot Testnet — API key saved` cut short
- **Status:** Fixed (2026-10-21)
- **Board:** With a bot selected, three things looked like one defect: the venue combo sat in a column that could shrink under its text (a combo's minimum size hint is a few letters, so the Plan column never asked for its room), the Ladder was measured while tabbed behind Orders (Qt parks such a page at its minimum width), and the Plan's checks tree wraps its words but the check read its columns as one line; fixed by the combo's `MinimumExpanding` policy and by the two checks reading the page as drawn (`tblBots` scrolls sideways by §9).
- **Context:** The Bots mode with a bot selected → `src/modules/bots/ui/bots_screen/` (`bots_view.py`, the Bots table, `bot_ladder_panel.py`, the Plan dock's venue combo) → `ui/`
- **Environment:** Qt offscreen platform under pytest, PySide6 as locked, Linux container fonts; app at `master-warrior` + PR #661. Column widths depend on the machine's font, so the sizes below are this container's; Unknown on a real Windows display.

## Reproduction
`tests/integration/presentation/ui/test_bots_mode_with_a_bot_conformance.py` boots the app over the fake exchange, creates and selects a Grid bot, and runs `MODE_CHECKS`. With `columns_shown_whole` and `combo_text_shown_whole` added to its `_MEASURED` list (the two checks it leaves out today):
1. 1024×700, Live and Backtest tab: `tblBots` columns Symbol, State, Grid profit, Cycles, Total PnL (net) run past the view's edge; `cmbBotVenue` shows 141 px of `Spot Testnet — API key saved`, which needs 170 px.
2. 1366×768: `tblBots` columns Cycles, Total PnL (net); `tblBotLadder` columns Buy at, Sell at, Step (designed) and more.
3. 1920×1080: `tblBotLadder` columns Buy at, Sell at, Step (designed), Per cycle, before fees (estimate) and more.
Frequency: every run here. Not run on CI's fonts (the case does not measure it there, on purpose).

## Symptom
```
bots~live@1024x700/columns_shown_whole: QTableView 'tblBots': column 'Symbol' runs past the view's edge; ... column 'Total PnL (net)' runs past the view's edge
bots~live@1024x700/combo_text_shown_whole: QComboBox 'cmbBotVenue' shows 141 px of 'Spot Testnet — API key saved', which needs 170 px
bots~live@1366x768/columns_shown_whole: QTableView 'tblBots': column 'Cycles' ...; QTableView 'tblBotLadder': column 'Buy at' ...
bots~live@1920x1080/columns_shown_whole: QTableView 'tblBotLadder': column 'Buy at' ...
```
Expected: every visible column and the combo's text shown whole, or the view scrolling (`ui-presentation-rule.md` §9: a table narrower than its columns scrolls horizontally).

## Root cause
Three mechanisms, none of them a column too wide for a dock that had room (read at `master-warrior` 58807d50):
1. **The venue combo** (`bot_plan_panel.py` → `BotPlanPanel`): a `QComboBox`'s `minimumSizeHint` is a few letters whatever its items, and the Plan column's minimum is its body's minimum, so at the narrowest column the layout gave the combo 141 px (165 px at 1366×768) of the 170 px `Spot Testnet — API key saved` needs. Not a stock-metrics problem: Windows fonts are wider.
2. **The Ladder** (`tblBotLadder`): a bottom dock tabbed behind Orders is not drawn and Qt keeps it "visible" at its minimum width (82 px), so `column_problems` measured seven columns "past the edge" of a view nobody sees. `combo_problems` already skipped such widgets (`workbench_text_checks.py` → `combo_problems`, `visibleRegion().isEmpty()`); `column_problems` did not, and the case never measured the Ladder with its tab in front.
3. **The Bots list and the checks tree**: `tblBots` is a 263 px dock holding five columns, and `§9` says such a table scrolls sideways (`BOT-128`); the check flagged the columns the scroll bar reaches. `tvBotChecks` (BOT-209) wraps its words in rows sized for the wrap, but the check compared its stretched column with the one-line width of the text.
4. **The Grid form's hints** (found by the fix's first gate run, on CI's fonts; reproduced here with the application font one and two points larger): `GridPanel` put each field and its wrapped hint in one form row, so `QFormLayout` measured the row's height at the full width of the panel but gave the row what is left after the label column; the hint was drawn two lines short of its text (`lblGridError_stop_loss` 38 px tall, 76 px needed at 157 px). The wider venue combo moved the Plan column into the width where the two differ; the defect was there before it, at any width narrower than the label plus the hint's one-line width (`grid_field_hints.py` → `FieldHints.under` at `master-warrior` 58807d50).

## Fix
`BotPlanPanel.venue` takes `AdjustToContents` and a `MinimumExpanding` horizontal policy (a layout keeps such a widget at its size hint, so the column asks for the room of the longest venue line; no pixel size is set). Each field's hint is a row of the form of its own across both columns (`FieldHints.hint_line`, hidden while it says nothing, following its field's row), which the form measures and lays out at the same width. `column_problems` skips a view that is not drawn, accepts a column beyond the edge where the view scrolls sideways, and reads a tree that wraps its words by its column's real width. The case measures `columns_shown_whole` and `combo_text_shown_whole`, and the Ladder with its tab in front; `_NOT_YET_MEASURED` and its test are gone.

## Regression test
`test_bots_mode_with_a_bot_conformance.py` now measures both checks on each tab at each size (red before: 141 px of 170 px, the Ladder and Bots columns, the checks tree; green after; and with the application font one to three points larger, which is how CI's fonts were reproduced: the hints two lines short) and `test_workbench_text_check_probes.py` pins the three readings of the check: a scrolling view, a view behind a tab, a wrapping tree; a table that does not scroll and is cut short is still seen.

## Verification
Local: the case, the probes and `test_workbench_conformance.py` pass, except `test_workbench_conformance[True-1024x700]`, which fails here the same way on `master-warrior` (this container's font metrics). CI: the pull request's `-Full` run.

## Suggested next steps
None.
