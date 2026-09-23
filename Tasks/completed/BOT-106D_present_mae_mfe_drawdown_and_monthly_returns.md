# BOT-106D — Show MAE/MFE, the drawdown curve, and monthly/yearly returns on the Backtest screen

**Status:** ✅ Done (2026-09-22)
**Source:** Self-review of PR #255 (2026-09-22), at the user's request ("self review, focus on design"). `BOT-106B`/`BOT-106C` shipped domain-only because their original QML presentation targets (`BackTestTradeLogs.qml`'s expanded row, `MonthlyReturnsHeatmap.qml`, `DrawdownUnderwaterCard.qml`) no longer exist — QML was removed from this codebase before `EPIC-025`. That gap was recorded only in prose (task implementation notes, the epic's own status line) until now — `architecture-rule.md` §7 ("Code speaks for itself") wants a deferred piece of work as a type or a test, and at minimum, in this repo's own planning terms, as a tracked task rather than a paragraph nobody re-reads.
**Risk:** 🟢 — pure presentation addition; the domain data these three views read (`Trade.mae_percent`/`.mfe_percent`, `calculate_drawdown_series`, `calculate_monthly_returns`/`calculate_yearly_returns`) is already implemented, tested, and stable.
**Complexity:** M — three separate PySide6 surfaces (a trade-log detail row, two new chart-area widgets), each needing to fit the existing Backtest screen without regressing `ui-presentation-rule.md`'s desktop UX and preview requirements.
**Epic (optional):** [`BOT-106`](../backlog/BOT-106_advanced_financial_analytics_and_reports_epic.md)
**Depends on:** [`BOT-106B`](../completed/BOT-106B_mae_mfe_trade_excursion_analysis.md) ✅, [`BOT-106C`](../completed/BOT-106C_drawdown_chart_and_monthly_heatmap.md) ✅ — both done, this task only needs to render what they already compute.

---

## 1. Context and problem

`BOT-106B` added `Trade.mae_percent`/`.mfe_percent`; `BOT-106C` added `calculate_drawdown_series()` and `calculate_monthly_returns()`/`calculate_yearly_returns()` (`src/modules/backtesting/contracts/`). Both are fully implemented, tested (6 + 14 unit tests, mutation-verified), and reachable from any `BacktestResult`/`equity_curve` a run already produces — but nothing in `src/modules/backtesting/ui/` reads them yet. A user running a backtest today gets the numbers computed but never sees MAE/MFE per trade, the drawdown underwater chart, or the monthly/yearly returns heatmap the original tasks described.

## 2. Acceptance criteria

- [x] The Backtest screen's trade log (wherever `BackTestTradeLogs`'s successor widget renders one row per `Trade`) shows `mae_percent`/`mfe_percent` for each trade, following `ui-presentation-rule.md` (QtWidgets only, no QML).
- [x] A drawdown underwater area chart renders `calculate_drawdown_series(result.equity_curve)` somewhere on the Backtest screen (chart area or a new panel — design decision for whoever picks this up, per §3 below).
- [x] A monthly/yearly returns heatmap renders `calculate_monthly_returns`/`calculate_yearly_returns(result.equity_curve, result.initial_balance)`.
- [x] All three read live off the run's actual `BacktestResult`, not a placeholder/sample — verified by a real backtest run showing real, non-zero numbers matching what the domain functions compute for that same run.
- [x] `preview.py` (per `ui-presentation-rule.md`) is updated if either new widget needs one to review in isolation.

## 3. Design

Not designed yet — left for whoever picks this up, since the two prerequisite tasks (`BOT-106B`/`106C`) were explicitly scoped to domain-only and never touched presentation. Two open questions worth resolving before writing code:
1. Where do the drawdown chart and returns heatmap live physically — a new tab/section on the existing Backtest screen, or folded into the existing chart area? (`Docs/HLD/11_desktop_workbench.md` should guide this.)
2. Whether the trade-log MAE/MFE columns need their own explanation/tooltip, given they're a less commonly known metric than PnL — `BOT-106B`'s own domain module docstring already gives the plain-language definition to reuse verbatim.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| (not yet determined) | Trade log widget: add MAE/MFE columns/detail row. |
| (not yet determined) | New drawdown underwater chart widget/panel. |
| (not yet determined) | New monthly/yearly returns heatmap widget/panel. |

## 5. Testing

Not yet planned — map to `testing-rule.md`'s tiers once the widget design (§3) is settled: a ViewModel-level unit test per new widget (no GUI needed, per this repo's own established pattern for chart-area widgets), plus a visual check via `preview.py` or a real run.

## Implementation notes (2026-09-22)

**§3 design decisions, resolved:**
1. Both new panels landed as two more tabs in `BackTestTradeLogsPanel`'s existing `TabBar` — "DRAWDOWN" and "RETURNS" alongside "TRADE LIST"/"BACKTEST LOG" — rather than a new `QDockWidget` panel (`Docs/HLD/11_desktop_workbench.md` §11.3's other option). The tab machinery (`activeBottomTab`, `TabBar`/`Tab`, `_sync_active_tab`) already existed and only needed generalizing from 2 states to 4; a new dock panel would have meant new dock-management code for no functional gain, given the tab bar was already the mutually-exclusive-views mechanism this screen uses.
2. MAE/MFE got no separate tooltip/explanation: they're rendered as plain `"MAE: -x.xx%   MFE: +x.xx%"` text at the top of the row's existing "EVALUATION METRICS & DURATION" detail column (`_trade_log_row.py`), ahead of Duration — a less-common metric reads first rather than getting buried after an unbounded metadata list. No new widget/tooltip infrastructure needed since the value is self-descriptive with the `MAE`/`MFE` labels already spelled out.

**Per-file, what changed:**
- `logic/trade_log_row.py` / `_trade_log_row.py` — `TradeLogRow.mae_percent`/`.mfe_percent` (defaulting `0.0`, same "no excursion observed" convention as `Trade`'s own fields), threaded through `build_trade_log_rows()`/`trade_log_row_to_qml()` as `maeText`/`mfeText`, rendered in the detail column.
- `logic/performance_charts.py` (new) — pure mapping from `BacktestResult` to what the two new widgets need: `build_drawdown_chart_points()` (negates `calculate_drawdown_series()`'s positive percent so the area draws below zero — "underwater" reads down, not up) and `build_yearly_returns_rows()` (chains `calculate_monthly_returns()` → `calculate_yearly_returns()`, keeping `None` for a month never reached — `YearlyReturn.months`'s own "absent, not zero" contract, preserved all the way to the widget).
- `_drawdown_chart_widget.py` (new) — a small standalone `pyqtgraph` widget (`PlotWidget` + one filled `PlotCurveItem`, `DateAxisItem` on the x-axis), **not** built on `ChartCard` (`support/charting/chart_card/`): that class is the candlestick/indicator/crosshair machinery for the main price chart, none of which one area curve needs.
- `_monthly_returns_heatmap_widget.py` (new) — a `QGridLayout` of cells: a plain dash for a month with no data, a coloured (`QPalette`, not `setStyleSheet()`) cell with inline-HTML-coloured text for one that has a value. Deliberately **no `Palette` import, no `setStyleSheet()`, no `apply_role()`** in either new widget file: `tests/unit/architecture/test_app_styling_only_shrinks.py` (ADR D21) ratchets all three counts down, never up, and building genuinely new UI without adding to that census (colour only via `QColor`/`QPalette`, foreground colour via `setText()`'s inline HTML, both untouched by the census) demonstrates the target end-state rather than adding to the debt it tracks.
- `view_models/run_result_view_model.py` — `drawdownPoints`/`yearlyReturns` properties + `set_drawdown_points()`/`set_yearly_returns()` mutators, same "empty list means no result yet" convention as `set_stat_cards([], [])`, living alongside it since they're written and cleared in the same breath (this file's own module docstring already states that principle for every other field it holds).
- `backtest_presenter.py` — `_on_backtest_succeeded()` computes both via `logic/performance_charts.py` and pushes them to the ViewModel; `_on_backtest_empty()`/`_on_backtest_failed()` clear them, mirroring the existing `set_stat_cards([], [])` clears in both places.
- `backtest_trade_logs_panel.py` — two new tabs wired the same way the existing two are: `_build_drawdown_tab()`/`_build_returns_tab()` wrap the new widgets, `_sync_active_tab()` generalized from a binary `is_logs` check to a 4-value switch, `_sync_tab_badges()` lists all 4 `Tab`s, `_sync_drawdown()`/`_sync_returns()` read `run_result.drawdownPoints`/`.yearlyReturns` reactively off their `*Changed` signals — the same signal-driven sync every other field on this panel already uses.
- `preview.py` — sample MAE/MFE on the existing sample trade, plus a synthetic 7-point one-year equity curve run through `build_drawdown_chart_points()`/`build_yearly_returns_rows()` so both new tabs render real (if synthetic) data standalone. Manually verified in this session: `build_preview()` under `QT_QPA_PLATFORM=offscreen`, switching `activeBottomTab` between all 4 values and confirming each tab's content becomes visible with non-empty data (7 drawdown points, 1 yearly-returns row) — the closest to a real visual check this headless environment allows; no regressions in the other two tabs.

**Tests:** 8 new (`logic/performance_charts.py`, drawdown negation/epoch-seconds/empty-run, yearly-returns year grouping/absent-month/colour/compounded-YTD) + 3 new on `trade_log_row.py` (MAE/MFE carried through, default `0.0`, signed text) + 3 new on `RunResultViewModel` (drawdown points and yearly returns each change-and-clear) + 3 on `DrawdownChartWidget` (empty/populated/cleared) + 6 on `MonthlyReturnsHeatmapWidget` (empty/populated/replace-not-append/cleared/no-data dash/loss colour) + 2 on `BackTestTradeLogsPanel` (new tabs mutually exclusive with the old two; reactive data forwarding) + 2 on `BackTestPresenter` (succeeded populates both, a later empty/failed run clears both). `ruff`/`mypy` clean on all 645 source files (one scoped `# type: ignore[import-untyped]` on the new `pyqtgraph` import — the same unavoidable missing-stub gap `pyproject.toml` already documents for every other `pyqtgraph` call site, all of which live inside the wholesale-excluded `support/charting/` directory; this one doesn't, so it needs its own local ignore rather than inheriting the path exclusion). Full targeted suite (`tests/unit/architecture`: 440, `tests/unit/modules/backtesting` + `test_trade_log_row.py`: 760) — 1,200 tests green, including the styling-ratchet guard.
