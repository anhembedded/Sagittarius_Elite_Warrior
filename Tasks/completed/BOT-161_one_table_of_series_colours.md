# BOT-161 — Every data series colour comes from one table, and the domain names no colour

**Status:** ✅ Done (2026-10-06)
**Source:** the user, 2026-10-06, choosing to keep the last stock-controls ratchet out of `EPIC-033M` ("Task riêng, giữ ratchet": a separate task, keep the ratchet).
**Risk:** 🟡 — a strategy's markers and an indicator's lines change where their colour is decided; a wrong mapping recolours a chart.
**Complexity:** M — about 34 literals in 13 files across `strategy/domain`, `strategy/ui` and `support/indicators`.
**Epic:** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md)
**Depends on:** `EPIC-033M` (merged)

---

## 1. Context and problem
`EPIC-033M` turned every rule of `tests/unit/architecture/test_stock_controls_only.py` into a ban except `color_literal`, which still lists the hex strings of data series in `baseline_stock_controls.json`: indicator lines (`support/indicators/indicator_scripts/*_script.py`), strategy markers and lines (`modules/strategy/domain/strategies/ema_trend_pullback_strategy.py`, `long_term_trend_zone_strategy.py`, `modules/strategy/ui/strategy_overlay/strategy_indicator_lines.py`) and the chart's bull and bear (`support/charting/chart_card/theme.py`). Two of those files are in a module's `domain/`, which should not know what a line looks like.

## 2. Acceptance criteria
- [x] One table names every data series colour by its meaning (an indicator's line, a strategy's entry, a band), and every reader asks the table by name.
- [x] No file under `modules/*/domain` holds a colour; a strategy says which series it draws, the UI decides its colour.
- [x] `color_literal` is zero outside the one table, the table is the guard's single named exemption, and `baseline_stock_controls.json` is deleted: `test_stock_controls_only.py` is a ban outright.
- [x] Every chart shows the same colours as before (a test reads each series' colour through the table).

## 3. Design
**Decision: a sibling table, not `theme.py`.** Series colours live in `support/charting/contracts/series_colours.py`, with their names (`ChartSeries`) in `contracts/chart_series.py`; `chart_card/theme.py` keeps the meanings (take profit, stop loss, levels) and takes bull and bear from the table. Why: (1) an indicator script is Qt-free (`test_module_domain_is_qt_free.py`) and `chart_card/__init__` imports the toolkit, so a script could not read `chart_card.theme` without paying for Qt at load; (2) `test_module_boundaries.py` allows an import of a `contracts/` package from anywhere and of `chart_card` from nowhere in `support/indicators`, so the table is reachable only from there; (3) the precedent still holds: `meaning_colours.py` derives from `theme.py`, which now derives from the one table, so profit and an up-candle cannot drift apart.

The domain names a series, never a colour: `BaseStrategy.chart_line_colors()` is now `chart_line_series() -> dict[str, ChartSeries]`, and `assign_strategy_line_colors` (UI) maps each series to its colour through the table. A `StrEnum` whose members are their own names keeps two series that share a colour today (MACD histogram, neutral line) as two members.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `support/indicators/indicator_scripts/*_script.py` | Read their line colours from the table |
| `modules/strategy/domain/strategies/*.py` | Name series, not colours |
| `tests/unit/architecture/test_stock_controls_only.py` | Becomes a ban; the baseline file goes |

## 5. Testing
Architecture guards; a unit test per moved colour reading the same value through the table; the chart previews.

## Implementation notes (written when done)
- **Table:** 21 `ChartSeries` members in `series_colours.py`, each with the exact hex (case included) it had; `FALLBACK_LINE_SERIES` is the strategy-line palette, same eight colours in the same order. It is the only file the guard does not count colour literals in.
- **Scripts** (`indicator_scripts/*_script.py`, nine files): `color=series_colour(ChartSeries.X)`; the dev and cross scripts' module constants are read from the table.
- **Strategies:** `ema_trend_pullback_strategy` and `long_term_trend_zone_strategy` return `ChartSeries` members from `chart_line_series()`; `strategy_chart_overlay_service` passes them on and the UI helper resolves colours.
- **Guard:** `test_stock_controls_only.py` is a ban; `baseline_stock_controls.json` is deleted; the one exemption is the table's path, pinned by `test_the_one_exemption_is_the_series_table` and `test_a_colour_outside_the_series_table_is_counted`.
- **Tests:** `tests/unit/support/charting/test_series_colours.py` (one case per series, written out as the pre-change hex; bull/bear through `theme.py`; the fallback palette) and `tests/unit/support/indicators/indicator_scripts/test_script_series_colours.py` (each shipped script's `line_colors()`).
- **Verified:** `tests/unit/architecture` 603 passed; `tests/unit/support`, `modules/strategy`, `modules/backtesting`, `modules/bots` and the overlay-lines test 3293 passed; ruff check and format clean; reference check OK; mypy 218 errors on this sandbox before and after the change (none new). The `-Full` run on GitHub is the full gate.
- **Not done:** no preview was run (no display here); colours are proven by value, not by screenshot.
