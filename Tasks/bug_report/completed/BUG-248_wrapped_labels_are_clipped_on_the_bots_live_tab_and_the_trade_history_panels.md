# BUG-248 — Word-wrapped labels are shorter than their text on the Bots Live tab and the Trade history panels

- **Reported:** 2026-10-21 (found while fixing BUG-246)
- **Severity:** 🟡 P2 — a sentence is cut off where its label is given less height than its text needs
- **Status:** Fixed (2026-10-21)
- **Board:** Eleven of the twelve labels were never clipped: they sit in panels tabbed behind another (the Bots Ladder and Fills, the Trade Order history and Trade history), which Qt keeps "visible" at their minimum width (82, 180 or 220 px), and `wrapped_text_problems` measured them there; the check now skips what is not drawn and `wrapped_text_in_every_tab` reads each tabbed panel with its tab in front (Bots passes; fixed). The twelfth, the Order history notices on Futures at 1024×700, is cut short at the panel's minimum height: [BUG-251](bug_report/incomplete/BUG-251_the_order_history_notices_are_cut_short_at_the_panels_minimum_height.md).
- **Context:** Bots mode (`src/modules/bots/ui/bots_screen/`, the Live tab's Ladder and Fills docks) and the Trade mode's order and trade history panels (`src/modules/trading/ui/`)
- **Environment:** Qt offscreen platform, the conformance suites' frames at 1024×700, 1366×768 and 1920×1080; not seen on a real display.

## Reproduction
Run `wrapped_text_problems` (`tests/integration/presentation/ui/workbench_layout_checks.py`) over each mode's page at the three sizes: `test_bots_mode_with_a_bot_conformance.py` for Bots, `test_trade_mode_conformance.py` for Trade. Expected: no word-wrapped label is shorter than its text; actual: the labels above.

## Symptom
See the Board line.

## Root cause
Not a layout squeezed by a splitter, as BUG-246 was (read at `master-warrior` ee768d83): the widths of the labels in the Board line are 82, 180 and 220 px at every window size, 1920×1080 included, and `label.visibleRegion().isEmpty()` is true for each of them. They are in docks tabbed behind the front one (Orders on Bots; the other history tab on Trade), which Qt does not draw but keeps visible, parked at the dock's minimum width; `workbench_layout_checks.py` → `wrapped_text_problems` measured their height there. `combo_problems` and (since BUG-245) `column_problems` already skip what is not drawn; this check did not, and no case raised a tab. Read with the tab in front the Bots Ladder and Fills and all but one Trade label are whole; the exception is [BUG-251](../incomplete/BUG-251_the_order_history_notices_are_cut_short_at_the_panels_minimum_height.md).

## Fix
`wrapped_text_problems` skips a label that is not drawn; the new `wrapped_text_in_every_tab` reads the page as shown and then each tabbed panel with its tab raised. The Bots case reads every tab of the bottom docks this way; the Trade case reads the drawn page and waits, by `test_the_tabbed_panels_wait_for_a_bug_that_is_still_open`, for BUG-251 before it reads the tabs.

## Regression test
`test_bots_mode_with_a_bot_conformance.py` (the tabbed panels in front, at the default font and with the application font a point larger) and `test_trade_mode_conformance.py` (the drawn page): the labels are read where they are drawn. Red before for the reason that matters: the check reported 11 labels that nobody could see clipped.

## Verification
Local: both cases, the probes and `tests/unit/architecture` pass. CI: the pull request's `-Full` run.

## Suggested next steps
None for this record; BUG-251 holds the one real clip.
