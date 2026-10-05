# EPIC-033S — The Market mode's charts scroll back and load a chosen range

**Status:** ✅ Done (2026-10-05)
**Source:** the user, 2026-10-05, deciding where the Dev Board's "load more" and date-range Load history go when the Dev Board is deleted (EPIC-033P): "Đưa vào Market mode sau" (put them in the Market mode later)
**Risk:** 🟡 — older candles prepended to a live chart; a gap at the join is the trap
**Complexity:** M — a command, a dialog and a prepend path in the chart
**Epic (optional):** [EPIC-033](../README.md)
**Depends on:** EPIC-033H (merged)

---

## 1. Context and problem
The Market mode's chart loads a fixed window of recent candles. Only the Dev Board loads older candles on demand ("load more") or a chosen date range; EPIC-033P deletes it without keeping either.

## 2. Acceptance criteria
- [x] View → Load older candles (planned as Chart → …; see the notes) prepends the previous window to the active chart, without a gap or a duplicate at the join.
- [x] View → Load range… asks a UTC start and end (a `QDialogButtonBox` dialog) and shows exactly that range.
- [x] Both are disabled while a load runs, and a load is fenced (`async-ui-action-rule.md`): closing the chart drops its result.

## 3. Design
Commands on the Market mode's chart, reusing the store's history query; the range dialog mirrors the Data mode's Sync history… range fields.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/market/` | the two commands, the dialog, the prepend path |
| `.../market/chart_history.py` (new) | `ChartHistory`: the window before the oldest drawn candle, and a range; `HistoryRange`, `RangeCandles` |
| `.../market/history_range_dialog.py` (new) | `HistoryRangeDialog`: View → Load range…'s UTC span |
| `.../market/chart_history_commands.py` (new) | the two commands, routed to the chart in front; presenter-owned |
| `.../market/market_chart.py` | the fenced loads, the prepend, the range drawn without live candles |
| `.../market/market_dependencies.py`, `market_presenter.py`, `market_view.py`, `market_commands.py` | the store port, the per-market `ChartHistory`, the dialog, the commands |

## 5. Testing
Unit: the join has neither gap nor duplicate (boundary values at the window edge); a fenced load dropped on close. Integration: Load range… against a seeded store.

## Implementation notes (written when done)
- **View → Load o&lder candles and Load ran&ge…, also on the Market toolbar, not a Chart menu.** A "Chart" menu title has no free access key (c, h, a, r and t are menu-bar titles' or Backtest panels' keys), the reason `EPIC-033Q` put the market choice in View; these two change what the chart in front shows, so they sit beside it. L and G are no View item's key nor a planned mode key (`test_the_modes_view_items_take_no_access_key_of_the_view_menu`).
- **The commands, not edge scrolling.** The Dev Board loaded older candles when the view panned near the left edge (`HistoryPaginationController`, `EdgeScrollDetector`, a cooldown). The acceptance criteria ask for a command, which is keyboard reachable and needs neither the cooldown nor the recheck loop; the edge detector stays in `ChartCard` for the Dev Board until `EPIC-033P` deletes it.
- **The join (`chart_history.py`).** The store bounds reads by `open_time`, both ends inclusive. An older window reads up to and including the oldest drawn candle's `open_time`, newest first, one row more than the window, and drops the drawn candle by `open_time`: the newest candle of the window is the stored one right before the drawn ones, and none is drawn twice. A gap the store has stays a gap; nothing is invented. A range keeps at most 20,000 candles (a week of 1m is 10,080), its newest when it holds more, and says so in the Output pane.
- **Fencing (`market_chart.py`).** A load records what it was asked against: the chart's generation (moved on by every whole history drawn, a first window or a range), symbol and timeframe. A result that no longer matches is dropped and logged, and the chart stops loading even when the new window never draws. Closing the tab cancels the load's `CancellationToken`, which the worker checks before it reports: a result is never emitted on a deleted chart (the first test run raised `Signal source has been deleted` without it). One load at a time per chart; `loadingChanged` keeps both commands off while it runs and while no chart is open.
- **A range is not live.** While a range is drawn the chart ignores live candles, which would land past a gap the range does not show; it keeps its stream, so the next first window (picking a timeframe) follows it again. Load older candles works on a range too.
- **Verification:** commit tier PASS; 8,683 unit and the trading and presentation integration tests pass; sanity 33. Mutation-checked: the strict `<` at the join, the window's extra row, the cut boundary, the token check, the request fence, the generation bump on a new window, the range ignoring live candles, the range ending on a new window, the commands off while loading, the stale drop re-enabling them. The duplication ratchet caught `_read`, `_submit` and `_request` shared with Bots and Data; they are `_read_stored`, `_start_load`, `_drawn_request`.
- **Review of PR #366: the fence covers a first window asked for but not drawn yet.** The first version moved the generation only when a whole history was drawn and counted only this chart's own loads as loading. With a first window in flight (going live, a new timeframe), Load range… stayed enabled and its range was then replaced by the earlier window, and an older window of 1m could land on a chart switching to 1h. `LiveCandleChart` now calls `_on_first_window_requested` when it asks for a first window and `_on_first_window_settled` when that request settles (the coordinator's `load_finished`, which was discarded, comes back on a Qt signal), so the chart counts as loading until then and the request itself moves the generation on. `LiveCandleChart._on_history` also no longer draws a window of a timeframe the chart has since left (a 1m→1h→1m switch whose 1h window lands last). Both probes of the review are tests now, with the orders that can still happen.
- **Still open:** going back from a range to the live window in one step is `EPIC-033T`; the Load range… dialog proposes the drawn span and has no presets (last day, last week).
