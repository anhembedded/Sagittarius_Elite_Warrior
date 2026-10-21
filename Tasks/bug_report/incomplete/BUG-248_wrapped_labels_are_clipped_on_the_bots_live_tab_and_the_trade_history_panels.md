# BUG-248 — Word-wrapped labels are shorter than their text on the Bots Live tab and the Trade history panels

- **Reported:** 2026-10-21 (found while fixing BUG-246)
- **Severity:** 🟡 P2 — a sentence is cut off where its label is given less height than its text needs
- **Status:** Open
- **Board:** `lblBotLadderSummary` (the Bots mode's Ladder dock) is 43 px tall and needs 105 px at 82 px wide, `lblBotFillsNote` and the fills table's empty text are clipped likewise, and the Trade mode's `lblOrderHistoryScope`, `lblOrderHistoryNotices`, `lblTradeHistoryScope` and `lblTradeHistoryNotices` are 33–39 px tall against 60–120 px; no check read this until `wrapped_text_problems` (BUG-246).
- **Context:** Bots mode (`src/modules/bots/ui/bots_screen/`, the Live tab's Ladder and Fills docks) and the Trade mode's order and trade history panels (`src/modules/trading/ui/`)
- **Environment:** Qt offscreen platform, the conformance suites' frames at 1024×700, 1366×768 and 1920×1080; not seen on a real display.

## Reproduction
Run `wrapped_text_problems` (`tests/integration/presentation/ui/workbench_layout_checks.py`) over each mode's page at the three sizes: `test_bots_mode_with_a_bot_conformance.py` for Bots, `test_trade_mode_conformance.py` for Trade. Expected: no word-wrapped label is shorter than its text; actual: the labels above.

## Symptom
See the Board line.

## Root cause
Not yet established. The same mechanism as BUG-246 is the suspect (a label in a pane whose layout a splitter or dock squeezes below `heightForWidth`); not verified per label.

## Fix
Pending.

## Regression test
`workbench_layout_checks.py` → `wrapped_text_problems`, added by BUG-246, run on the Bots mode's Live Plan and Backtest page only; the Ladder and Fills docks and the Trade history panels are what it finds.

## Verification
Not run.

## Suggested next steps
1. Read each label's parent layout and the pane that holds it. 2. Fix at the shared mechanism (one scroll at the panel, or a layout that asks `heightForWidth`). 3. Add the check to `MODE_CHECKS` once the modes pass.
