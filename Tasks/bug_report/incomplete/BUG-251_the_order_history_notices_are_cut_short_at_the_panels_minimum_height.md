# BUG-251 — The Trade mode's Order history and Trade history notices are cut short at the panel's minimum height

- **Reported:** 2026-10-21 (found while fixing BUG-248, the conformance suite's wrapped-text check read with the tab in front)
- **Severity:** 🟢 P3 — the last line of a three-line notice ("Binance keeps a Futures order that was cancelled or expired without a fill for 3…") is hidden until the person drags the panel taller; nothing is lost
- **Status:** Open
- **Board:** On Futures at 1024×700, `lblOrderHistoryNotices` is 42 px tall and its text needs 60 px at 446 px wide: the Order history panel (and, with its own notices, Trade history) starts at the minimum height `MinimumHintSlot` asks for, which counts a wrapped label as its first lines; making the panel ask for the room costs the mode 45 px of height it does not have at 1024×700.
- **Context:** Trade mode → `src/modules/trading/ui/desk/account_tabs/history_panel.py` (`HistoryPanel`) in `src/support/ui_kit/minimum_hint_slot.py` (`MinimumHintSlot`) → `ui/`
- **Environment:** Qt offscreen platform under pytest, PySide6 as locked, Linux container fonts; app at `master-warrior` ee768d83. Wrapped heights depend on the machine's font; Unknown on a real Windows display.

## Reproduction
1. In `test_trade_mode_conformance.py`, drop `_TABS_EXCEPTION`: the Futures run at 1024×700 then reads the tabbed panels too (`wrapped_text_in_every_tab`, `workbench_layout_checks.py`, which raises each before reading its labels).
2. Run the Futures case at 1024×700. Expected: no wrapped label shorter than its text. Actual: `'lblOrderHistoryNotices' is 42px tall, its text needs 60px at 446px wide (tab 'Order history')`. The other five runs (Spot, and Futures at 1366×768 and 1920×1080) pass.
Frequency: every run here.

## Symptom
```
trade~futures_testnet@1024x700/wrapped_text_shown_whole: 'lblOrderHistoryNotices' is 42px tall, its text needs 60px at 446px wide (tab 'Order history')
```
Expected: the notice shown whole, or the panel scrolling (`ui-presentation-rule.md` §3).

## Root cause
Established by reading, not yet by a fix (read at `master-warrior` ee768d83): `MinimumHintSlot` makes a dock start at the panel's minimum size hint (`sizeHint()` returns `minimumSizeHint()`); the panel is a `QVBoxLayout` of scope label, notices label, rows and pager, and a word-wrapped label's minimum height is its first lines, not its height at the panel's width. At 446 px the panel needs 201 px and the dock gives it 156 px, so `QBoxLayout` shrinks every item in proportion and the notices label gets 42 of its 60 px. Tried and not kept: (a) the stacked rows `Ignored` vertically, which also drops the panel's hint and left the dock shorter still; (b) `HistoryPanel.minimumSizeHint` adding the labels' wrapped height, which fixes the label but makes the mode need 745 px of height at 1024×700 (`fits_the_window` fails by 45 px).

## Fix
Pending. It is a trade: the notice shown whole costs the Trade mode height at 1024×700 that it does not have, so either the panel scrolls once at itself, or the notices move out of the shrinking layout, or the mode gives the history docks less of something else. Needs a decision before code.

## Regression test
`test_trade_mode_conformance.py` reads every tabbed panel in five of its six runs; the sixth, Futures at 1024×700, reads the drawn page while this report is open, and `test_the_one_run_that_skips_the_tabs_waits_for_a_bug_that_is_still_open` fails the day the report leaves `incomplete/`, so the exception cannot stay.

## Verification
Not run.

## Suggested next steps
1. Decide the trade above (panel scrolls once, notices outside the layout, or less height elsewhere). 2. Fix at `HistoryPanel`/`MinimumHintSlot`, the shared mechanism. 3. Switch the case to `wrapped_text_in_every_tab` and move this report to `completed/`.
