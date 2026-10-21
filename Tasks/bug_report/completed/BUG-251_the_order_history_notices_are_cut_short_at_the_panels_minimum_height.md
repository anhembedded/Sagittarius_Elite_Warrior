# BUG-251 — The Trade mode's Order history and Trade history notices are cut short at the panel's minimum height

- **Reported:** 2026-10-21 (found while fixing BUG-248, the conformance suite's wrapped-text check read with the tab in front)
- **Severity:** 🟢 P3 — the last line of a three-line notice ("Binance keeps a Futures order that was cancelled or expired without a fill for 3…") is hidden until the person drags the panel taller; nothing is lost
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** The history panel's notice shrank with the rest when the dock gave it less than the panel needs; the notice and scope labels now keep their wrapped height (vertical policy Minimum) and the rows give way, so the sentence is shown whole at 1024×700 with the mode still fitting the window.
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
`HistoryPanel` gives its scope and notices labels a vertical size policy of `Minimum` (`history_panel.py`). `Minimum` keeps the label's hint as its least height and caps nothing, so the layout gives a wrapped label `heightForWidth` at the dock's width, and the rows, which have a stretch and scroll, take the shortfall. (A first version used `Fixed`, which caps the label at its hint measured at another width and cut the notice again in a dock narrowed to 220 px, at every window size; the reviewer found it and the narrow-dock test below pins it.) That is the third option the report weighed ("the notices move out of the shrinking layout"), done by policy rather than by a new container: no height is added to the mode's minimum (`fits_the_window` passes at 1024×700), and the panel's own minimum hint is unchanged. The shared `MinimumHintSlot` needed no change.

## Regression test
`tests/integration/presentation/ui/test_trade_mode_conformance.py` now reads every tabbed panel in all six runs: `_TABS_EXCEPTION` and `test_the_one_run_that_skips_the_tabs_waits_for_a_bug_that_is_still_open` are gone, as the report said they must. Red before (`'lblOrderHistoryNotices' is 42px tall, its text needs 60px`), green after. `tests/unit/modules/trading/ui/desk/test_history_panel.py::test_a_long_notice_is_shown_whole_in_a_dock_as_narrow_as_it_goes` (red with `Fixed`: 75 of 105 px). Frames of the panel at the dock's minimum height, before (notice 50 px of 60) and after (60 of 60): `images/BUG-251-order-history-notice-before.png`, `images/BUG-251-order-history-notice-after.png`.

## Verification
Commit tier, `tests/integration/presentation`, `tests/unit/modules/trading`, `tests/unit/architecture` green locally except `test_workbench_conformance[True-1024x700]` (the Backtest mode needs 711 px of height), which fails identically on `master-warrior` here and is not this change. Wrapped heights depend on the font; Windows not run.

