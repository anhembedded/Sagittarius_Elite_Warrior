# EPIC-033T — A Market chart showing a range goes back to its live window in one step

**Status:** ✅ Done (2026-10-05)
**Source:** the independent review of PR #366 (EPIC-033S), 2026-10-05: "the only way back from a range to the live window is to pick a timeframe *other than* the active one … a usability gap"
**Risk:** 🟢 — one command that asks for the first window again; the fence EPIC-033S built already drops what it replaces
**Complexity:** S — a command, a `LiveCandleChart` restart at the same timeframe, a test
**Epic (optional):** [EPIC-033](../README.md)
**SPEC (optional):** [SPEC-002](../../../../Docs/SPEC/SPEC-002_watch_the_live_market.md)
**Depends on:** EPIC-033S (merged)

---

## 1. Context and problem
After View → Load range… (`EPIC-033S`) the chart draws the range and takes no live candle (`market_chart.py`, `apply_candle`). It follows the stream again only when a new first window is drawn, and `LiveCandleChart._on_timeframe_changed` ignores the active timeframe. So the way back is to pick another timeframe and then the one wanted: two restarts, two syncs. Closing and reopening the tab also works, but it is not a command.

## 2. Acceptance criteria
- [x] View → Back to live (or re-choosing the active timeframe) draws the newest first window of the chart in front and follows the stream again, in one request.
- [x] Off while the chart in front shows no range, and while it loads; a range or older window asked before it is dropped (the EPIC-033S fence).

## 3. Design
A command next to Load range… that asks the chart for a first window at its own timeframe (a public `LiveCandleChart` entry over `_restart`), so a desk or bot chart can use it too. Its access key must pass `test_the_modes_view_items_take_no_access_key_of_the_view_menu`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/charting/live_chart/live_candle_chart.py` | a public "show the newest window again" entry |
| `src/modules/trading/ui/market/` | the command, its enabled state, the chart's call |

## 5. Testing
Unit: from a drawn range, one trigger draws the newest window and a live candle is drawn again; the command is off with no range and while loading (mutation-verified).

## Implementation notes (written when done)
- **The entry:** `LiveCandleChart.show_newest_window()` (`src/support/charting/live_chart/live_candle_chart.py`), a public restart at the shown symbol and timeframe, live if the chart is. A desk or bot chart can call it too. Re-choosing the active timeframe still does nothing; the command is the way back.
- **The command:** View → Back to l&ive (`BACK_TO_LIVE`, `market_commands.py`), also on the mode's toolbar, beside Load range…. Its access key is `i`: `a` is a mode's key and `e` is taken, and `test_the_modes_view_items_take_no_access_key_of_the_view_menu` checks this.
- **Enabled state:** `ChartHistoryCommands` gained `backToLiveEnabledChanged`. Back to live is on only while the chart in front shows a range and is not loading.
  - `MarketChart` gained `showingRangeChanged`. It is needed because a range's own load reports "not loading" before the range is drawn, so `loadingChanged` alone would leave the command a step behind.
  - The EPIC-033S fence is unchanged: the restart moves the generation on, so a load asked before it is dropped.
- **Tests:** `tests/unit/modules/trading/ui/market/test_market_chart_back_to_live.py` has 5 tests:
  - from a range, one trigger draws minutes 0–59 and a live candle (minute 60) is drawn again;
  - the chart's stream is restarted exactly once;
  - the command is off with no range, while its window loads and after it draws, and with no chart open.
- **Mutations:** each of these turns tests red:
  - the command does nothing (3 red);
  - the enabled state ignores the range (2 red);
  - the enabled state ignores loading (1 red);
  - no `showingRangeChanged` (3 red).
