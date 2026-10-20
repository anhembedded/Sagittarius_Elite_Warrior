# BUG-243 — Three result charts draw their time axis in the machine's clock, not in the display zone

- **Reported:** 2026-10-20 (independent review of PR #639, `BUG-240`: https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/639#issuecomment-6294370195, which counted four charts; at `3cf7960` three remain, see Root cause)
- **Severity:** 🟡 P2 — under the default display zone, UTC, these charts read the machine's local time (+07 on the owner's machine) while the crosshair and tables beside them read UTC, and they ignore a chosen zone. Display only.
- **Status:** ✅ Fixed (2026-10-20)
- **Board:** The Backtest drawdown and report-comparison charts and the Bot Backtest workbench's equity curve built a plain `pg.DateAxisItem`, which labels in the machine's clock, so their time axis ignored the app-wide display zone. Cause: the same two-conversions fault as `BUG-240`. Fixed: all three use `ZonedDateAxisItem` and follow the zone; an architecture guard bans a plain `DateAxisItem` in `src/`.
- **Context:** Backtest and Bots result charts → `src/modules/backtesting/ui/`, `src/modules/bots/ui/backtest_workbench/`
- **Environment:** Linux, pyqtgraph 0.14.0, app at `3cf7960`; labels read through the painter (`generateDrawSpecs`). Windows not run.

## Reproduction
Display zone `Asia/Ho_Chi_Minh` (or `America/New_York`) set on the Backtest screen (or the shared zone for the Bots workbench), a runner whose clock is UTC: the drawdown, comparison and equity axes over `2026-01-10 02:00Z..08:00Z` draw `03:00 .. 07:00` where Vietnam reads `09:00 .. 15:00`. Frequency: every chart, under every zone but the machine's own.

## Symptom
At `3cf7960`, the axes draw the runner's clock: `{'03:00', '04:00', ..., '07:00'}` (east) and `{'11:00', '12:00', ..., '15:00'}` (west) while the zone says otherwise. The crosshair and tables beside them read in the zone.

## Root cause
At `3cf7960`, `_drawdown_chart_widget.py` → `DrawdownChartWidget.__init__`, `_report_comparison_chart_widget.py` → `ReportComparisonChartWidget.__init__` and `bots/ui/backtest_workbench/equity_pane.py` → `EquityPane.__init__` built `PlotWidget(axisItems={"bottom": DateAxisItem(orientation="bottom")})`. With `utcOffset=None` pyqtgraph labels in the machine's local time, and nothing told them the display zone. The review counted a fourth, the grid backtest's `equity_chart.py`; it no longer exists at `3cf7960`. The design fault is the one `BUG-240` fixed for the chart card: a time axis built from the toolkit's base class instead of the converter the rest of the screen uses. The gate was green because no test read an axis's labels, and CI runs in UTC.

## Fix
`ZonedDateAxisItem` (`BUG-240`) replaces the plain axis in all three widgets; each has `set_display_timezone(zone)`. Wiring: the drawdown panel (`result_panels.py` → `drawdown_panel`, built by `build_panels`) and the comparison dialog follow the Backtest screen's `time_range.displayTimezone` and its `displayTimezoneChanged`; the equity pane follows the shared `DisplayTimezonePreference` through `BacktestWorkbenchView.use_display_timezone` until destroyed. A guard, `tests/unit/architecture/test_time_axes_come_from_zoned_date_axis.py`, fails on any `DateAxisItem(` in `src/` outside `zoned_date_axis.py`, so a fourth cannot appear unnoticed (the family recurred: the chart card, then these).

## Regression test
`tests/unit/modules/backtesting/ui/test_result_charts_follow_the_display_zone.py` (drawdown and comparison, east and west zones, and a dialog opened after the choice) and `tests/unit/modules/bots/ui/backtest_workbench/test_workbench_display_timezone.py::test_the_equity_curve_axis_reads_in_the_shared_display_zone`. They read the labels each axis draws (`tests/chart_axis_labels.py`), on the production `build_panels`, dialog and workbench. Seven red before the fix (`'10:00', '12:00'` not in `{'03:00', ..., '07:00'}`, and `no attribute 'display_zone'`), green after. The guard is red on the three files before the fix and green after.

## Verification
- Regression tests and guard: red before, green after.
- Positive proof the new axes ran: the drawn labels follow the zone (east: `10:00, 12:00` present; west: `06:00, 08:00`).
- Commit tier and suites: see the pull request.
