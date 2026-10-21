# BUG-245 — With a bot selected, the Bots table, the Ladder table and the venue combo run past their edges

- **Reported:** 2026-10-21 (the first run of the new conformance case with a bot selected, `BOT-212`; the delivery coordinator asked for the record)
- **Severity:** 🟢 P3 — columns and a combo's text are cut off at the window sizes the suite measures; nothing is lost (a table scrolls sideways) but the person reads a clipped header or `Spot Testnet — API key saved` cut short
- **Status:** Open
- **Board:** With a Grid bot selected, `tblBots`, `tblBotLadder` and the venue combo `cmbBotVenue` are wider than their views at 1024×700 and 1366×768 (and the Ladder at 1920×1080) on the offscreen platform; the conformance case leaves these two checks out until this is fixed.
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
Not yet established. Known: the checks pass with no bot selected (the suite's Bots mode has empty tables), so the widths come from the rows or the Ladder's data; the Ladder fails even at 1920×1080, which points at a dock narrower than its content rather than a small window. Not known: whether the checks mean a sideways scroll bar (acceptable by §9) or a clipped column, and whether CI's fonts show the same.

## Fix
Pending.

## Regression test
The conformance case with the two checks added to `_MEASURED`: it holds the expectation once the bug is fixed. While this report is open the case lists the checks as not yet measured and names this id (`test_the_checks_left_out_wait_for_an_open_bug`); that test fails the day this report is fixed, so the checks cannot stay out after the fix.

## Verification
Not run.

## Suggested next steps
1. Decide what the two checks should accept for a table with a horizontal scroll bar (§9) and read each failing view's scroll policy.
2. Measure on CI's fonts (the artifact `ui-screenshots` holds the frames).
3. Fix the widths or the docks' default sizes, then add the checks to `_MEASURED` and move this report to `completed/`.
