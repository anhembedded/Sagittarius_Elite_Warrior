# BOT-106D — Show MAE/MFE, the drawdown curve, and monthly/yearly returns on the Backtest screen

**Status:** 🔵 Backlog
**Source:** Self-review of PR #255 (2026-09-22), at the user's request ("self review, focus on design"). `BOT-106B`/`BOT-106C` shipped domain-only because their original QML presentation targets (`BackTestTradeLogs.qml`'s expanded row, `MonthlyReturnsHeatmap.qml`, `DrawdownUnderwaterCard.qml`) no longer exist — QML was removed from this codebase before `EPIC-025`. That gap was recorded only in prose (task implementation notes, the epic's own status line) until now — `architecture-rule.md` §7 ("Code speaks for itself") wants a deferred piece of work as a type or a test, and at minimum, in this repo's own planning terms, as a tracked task rather than a paragraph nobody re-reads.
**Risk:** 🟢 — pure presentation addition; the domain data these three views read (`Trade.mae_percent`/`.mfe_percent`, `calculate_drawdown_series`, `calculate_monthly_returns`/`calculate_yearly_returns`) is already implemented, tested, and stable.
**Complexity:** M — three separate PySide6 surfaces (a trade-log detail row, two new chart-area widgets), each needing to fit the existing Backtest screen without regressing `ui-presentation-rule.md`'s desktop UX and preview requirements.
**Epic (optional):** [`BOT-106`](../backlog/BOT-106_advanced_financial_analytics_and_reports_epic.md)
**Depends on:** [`BOT-106B`](../completed/BOT-106B_mae_mfe_trade_excursion_analysis.md) ✅, [`BOT-106C`](../completed/BOT-106C_drawdown_chart_and_monthly_heatmap.md) ✅ — both done, this task only needs to render what they already compute.

---

## 1. Context and problem

`BOT-106B` added `Trade.mae_percent`/`.mfe_percent`; `BOT-106C` added `calculate_drawdown_series()` and `calculate_monthly_returns()`/`calculate_yearly_returns()` (`src/modules/backtesting/contracts/`). Both are fully implemented, tested (6 + 14 unit tests, mutation-verified), and reachable from any `BacktestResult`/`equity_curve` a run already produces — but nothing in `src/modules/backtesting/ui/` reads them yet. A user running a backtest today gets the numbers computed but never sees MAE/MFE per trade, the drawdown underwater chart, or the monthly/yearly returns heatmap the original tasks described.

## 2. Acceptance criteria

- [ ] The Backtest screen's trade log (wherever `BackTestTradeLogs`'s successor widget renders one row per `Trade`) shows `mae_percent`/`mfe_percent` for each trade, following `ui-presentation-rule.md` (QtWidgets only, no QML).
- [ ] A drawdown underwater area chart renders `calculate_drawdown_series(result.equity_curve)` somewhere on the Backtest screen (chart area or a new panel — design decision for whoever picks this up, per §3 below).
- [ ] A monthly/yearly returns heatmap renders `calculate_monthly_returns`/`calculate_yearly_returns(result.equity_curve, result.initial_balance)`.
- [ ] All three read live off the run's actual `BacktestResult`, not a placeholder/sample — verified by a real backtest run showing real, non-zero numbers matching what the domain functions compute for that same run.
- [ ] `preview.py` (per `ui-presentation-rule.md`) is updated if either new widget needs one to review in isolation.

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
