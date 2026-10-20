# BUG-240 — A chart's time axis is mirrored for zones east of UTC and uses one offset for every tick

- **Reported:** 2026-10-20 (found while fixing `BUG-239`; the independent reviewer of PR #636 asked for it to be filed: https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/636#issuecomment-6293080831). The sign half was found while writing this fix's regression test.
- **Severity:** 🟡 P2 for the sign (below), 🟢 P3 for the daylight-saving half. Display only: no order or stored data is affected. The crosshair label and the tables were right, so the axis disagreed with them.
- **Status:** ✅ Fixed (2026-10-20)
- **Board:** Charts' time axes were wrong for every zone but UTC: the offset was passed to pyqtgraph in the opposite sign (Vietnam read UTC-7, `01:00Z` drawn as 18:00 of the day before) and was one number computed at now for all ticks (an hour off across a daylight-saving change). Cause: `pg.DateAxisItem` takes seconds west of UTC, once. Fixed: `ZonedDateAxisItem` writes each tick through `to_display_time`, the converter of the crosshair and the tables.
- **Context:** Any chart (Backtest, Bots) → `src/support/charting/chart_card/` → `plot_layout.py`, `zoned_date_axis.py`
- **Environment:** Linux, pyqtgraph 0.14.0, app at `43bd439`. Drawn labels read with `axis.generateDrawSpecs`. Windows not run.

## Reproduction
1. Display zone `Asia/Ho_Chi_Minh` (UTC+7), chart range `2026-01-01 00:00Z` .. `08:00Z`. Expected hour ticks `08:00` .. `14:00`.
2. Display zone `America/New_York`, range `2026-03-08 03:00Z` .. `15:00Z` (daylight saving starts 07:00Z). Expected `00:00`, `01:00`, `03:00`, `04:00` ...: no `02:00` that day.
Frequency: every chart with a zone other than UTC.

## Symptom
At `43bd439`, Vietnam: `['Thu 01', '18:00', '19:00', '20:00', '21:00', '22:00', '23:00']` (UTC-7, the day before). New York, the March range: `['08:00', '09:00', '10:00', ...]` (UTC+5 for a UTC-5 zone). The Bots and Backtest crosshair labels, converted per instant by the service, read correctly beside it.

## Root cause
At `43bd439`, `plot_layout.py` → `ChartPlotLayout.__init__`, `set_display_timezone`, `add_subplot` passed `get_utc_offset_seconds(now, zone)` (seconds *east* of UTC) as `pg.DateAxisItem(utcOffset=…)`. pyqtgraph's `utcOffset` is seconds *west*: `calculateUtcOffset` returns `-offsetFromUtc()` and `tickStrings` draws `timestamp - utcOffset`. So (1) the sign was inverted for every zone (the `BOT-205` tests pinned `utcOffset == 7 * 3600`, the wiring and not what the axis draws, and the UTC runner hides it), and (2) one offset, taken at now, served every tick, which is the daylight-saving half the review found. The design error: the axis was given a number to convert with, instead of the converter. Same family as `BUG-239`, and `BUG-234`'s: a time and its label from two different conversions.

## Fix
`zoned_date_axis.py` → `ZonedDateAxisItem(pg.DateAxisItem)`: `tickStrings` writes each tick through `format_display_timestamp`, so a label is the tick's own instant converted by `to_display_time`. pyqtgraph's offset places day, month and year ticks on the zone's local midnights, so `tickValues` sets it from the middle of the view, in pyqtgraph's sign. Hour ticks are aligned by pyqtgraph to the machine's own clock (`offsetToLocalHour`), so in a zone whose offset is not a whole hour from the machine's the hour ticks fall on :30 (UTC machine, `Asia/Kolkata`: `06:30, 07:30`); the labels stay true. `ChartPlotLayout` builds the axis for the main plot and every subplot and `set_display_timezone` changes its zone. Limits: ticks beyond a daylight-saving change inside one view are placed with the offset of the view's middle, labelled truthfully (`00:00 01:00 03:00` across the change); the hour alignment above. `to_display_time` now also answers for an instant its zone cannot reach (year 1 west of UTC): UTC, logged once, instead of raising from a paint (review of PR #639). Four other charts build a plain `DateAxisItem`: `BUG-241`.

## Regression test
`tests/unit/support/charting/test_chart_time_axis_follows_daylight_saving.py`: `test_every_tick_reads_in_the_offset_of_its_own_instant` (New York and "System" as New York, across the March change: `01:00` and `03:00` drawn, no `02:00`) and `test_an_east_zone_reads_ahead_of_utc_not_behind_it` (Vietnam: `08:00` drawn, not `18:00`), `test_day_ticks_sit_on_the_local_midnight_of_the_zone` (placement sign, east and west; red when the sign is put back), `test_a_view_at_the_edge_of_the_calendar_draws_instead_of_raising` and `test_a_moment_the_zone_cannot_reach_falls_back_to_utc_and_says_so` (red without the converter's guard). They read the labels the axis draws through the production `ChartPlotLayout`, and are red at `43bd439`'s `plot_layout.py` for the right reason (`'01:00' not in ['08:00', '09:00', …]`, `'08:00' not in ['Thu 01', '18:00', …]`). The three `BOT-205` tests that pinned `utcOffset` now pin `display_zone`; the drawn-label tests are the stronger coverage of that path.

## Verification
- Regression file: 3 red before, green after.
- `tests/unit/support`, `tests/unit/modules/bots/ui`, `tests/unit/modules/backtesting`, `tests/unit/architecture`: green; commit tier PASS.
- Positive proof the new axis ran: `ZonedDateAxisItem` draws `Asia/Ho_Chi_Minh` `['08:00' … '14:00']` and `America/New_York` `['Sat 07', '00:00', '01:00', '03:00', '04:00' …]`.
- `-Full` and the review: see the pull request.
