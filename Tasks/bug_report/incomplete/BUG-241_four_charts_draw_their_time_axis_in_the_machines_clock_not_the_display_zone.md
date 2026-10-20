# BUG-241 — Four charts draw their time axis in the machine's clock, not in the display zone

- **Reported:** 2026-10-20 (independent review of PR #639, `BUG-240`: https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/639#issuecomment-6294370195)
- **Severity:** 🟡 P2 — under the default display zone, UTC, these charts read the machine's local time (+07 on the owner's machine) while the crosshair and tables beside them read UTC, and they ignore a chosen zone. Display only.
- **Status:** Open
- **Board:** Four Backtest and Bots result charts (grid backtest equity, workbench equity, report comparison, drawdown) build a plain `pg.DateAxisItem`, so their time axis follows the machine's clock, not the app-wide display zone; the same two-conversions fault as `BUG-240`.
- **Context:** Backtest and Bots result charts → `src/modules/bots/ui/`, `src/modules/backtesting/ui/`
- **Environment:** Found by code reading at `15c0113`; not yet reproduced on screen.

## Reproduction
Not yet reproduced on screen. Expected from the code: on a +07 machine under the default zone (UTC), an equity or drawdown chart's axis reads 07:00 for `00:00Z`, while the tables beside it read `00:00`.

## Symptom
Not yet captured.

## Root cause
Not yet established. Suspected: `DateAxisItem(orientation="bottom")` with `utcOffset=None` labels in the machine's local time (pyqtgraph's default): `src/modules/bots/ui/kinds/grid/backtest/equity_chart.py:38`, `src/modules/bots/ui/backtest_workbench/equity_pane.py:37`, `src/modules/backtesting/ui/_report_comparison_chart_widget.py:46`, `src/modules/backtesting/ui/_drawdown_chart_widget.py:49` at `15c0113`.

## Fix
Not yet. Likely `ZonedDateAxisItem` (`src/support/charting/chart_card/zoned_date_axis.py`) fed by the shared display zone (`DisplayTimezonePreference`), as `BUG-240` did for the chart card.

## Regression test
Pending.

## Verification
Not run.

## Suggested next steps
Reproduce on screen on a non-UTC machine; decide whether each chart follows the shared zone (the likely answer) or documents a reason not to.
