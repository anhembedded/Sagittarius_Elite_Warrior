# Nhiệm vụ: Phân tách Dữ liệu In-Sample vs Out-of-Sample (OOS Blind Testing)

**Mã Task:** `BOT-107A`  
**Thuộc Epic:** [`BOT-107`](../backlog/BOT-107_strategy_robustness_and_monte_carlo_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** ✅ **Done (2026-09-24)**  
**Dependencies:** `BOT-021`, [`BOT-095B`](BOT-095B_backtest_fsm_dirty_tracking.md)

---

## 1. Mục tiêu

1. **Cấu hình Phân vùng**:
   - Cho phép người dùng chọn tỷ lệ chia In-Sample / Out-of-Sample (VD: `70% / 30%` hoặc chọn mốc ngày phân tách `split_date`).
2. **Thực thi Độc lập**:
   - Chạy Pass 1 trên tập In-Sample (sinh ra `in_sample_metrics`).
   - Chạy Pass 2 trên tập Out-of-Sample với cùng bộ tham số mà không có sự thiên lệch (sinh ra `out_of_sample_metrics`).
3. **Hiển thị Đối sánh (Side-by-Side Comparison)**:
   - Trên Chart: Vẽ một đường đứt nét phân cách dọc giữa 2 vùng.
   - Trên Bảng Chỉ số: Hiển thị 2 cột số liệu song song: **In-Sample** vs **Out-of-Sample** (cảnh báo đỏ nếu hiệu suất OOS sụt giảm quá 40% so với In-Sample $\rightarrow$ dấu hiệu overfit rõ rệt).

---

## 2. Implementation Notes (2026-09-24)

**Re-verified before implementing** (this repo's own "stale backlog task"
pattern): a dedicated investigation found §2 ("Thực thi Độc lập") already
fully shipped by `BOT-080` — `out_of_sample_split.py`
(`split_klines_for_out_of_sample()`) and `out_of_sample_validation.py`
(`OutOfSampleValidation`, computed by `run_static_backtest/handler.py` and
carried on `BacktestResult.out_of_sample`) already run both passes and
compute both metric sets. §1 and §3 were genuinely unbuilt, but neither
survived re-scoping unchanged:

- **§1 (configurable split ratio) — re-scoped to won't-do.**
  `out_of_sample_split.py`'s own `DEFAULT_IN_SAMPLE_RATIO = 0.7` carries a
  binding `BOT-080` decision: "deliberately NOT meant to become
  user-configurable — letting someone dial the split until the numbers look
  good would defeat the point of this check." Building a picker here would
  reopen a decision this task has no fresh authorization to reverse, so §1
  is closed as won't-do rather than implemented.
- **§3's "40% relative degradation" warning — re-scoped to reuse the
  shipped rule instead of duplicating it.** `BOT-080` already shipped a
  different, live warning — `OutOfSampleValidation.has_high_divergence`, a
  30-point **absolute** drop in `net_profit_percent`
  (`OUT_OF_SAMPLE_DIVERGENCE_WARNING_POINTS = 30.0`). Adding a second,
  differently-formulated 40%-relative threshold beside it would make the
  screen contradict itself on the same question ("is this overfit?");
  replacing the shipped rule is a product decision outside this task's
  scope. The new UI reuses `has_high_divergence` as the one canonical
  overfit signal.
- **The genuinely real, bounded remaining work** was §3's two *display*
  gaps: no chart divider line existed in any form, and the metrics table
  was two stray extended-stat-card rows in a flat grid rather than a real
  side-by-side comparison. Both are now built.

**Design — chart divider.** New `OutOfSampleDividerLine`
(`support/charting/chart_card/out_of_sample_divider_line.py`), mirroring
`TradeLinkLine`'s exact shape (one `pg.InfiniteLine`, `show_at()`/`hide()`,
no knowledge of `BacktestResult`). Wired through `ChartCard`
(`set_out_of_sample_divider()`/`clear_out_of_sample_divider()`) →
`IBacktestChartHost` port → `PythonBacktestChartHost` → the same pattern
`set_trade_link`/`clear_trade_link` already established end to end.
`BackTestPresenter._present_result()` computes the divider's X position as
the in-sample half's own last equity-curve point (exactly where the
out-of-sample half begins) and draws or clears it on every result; the
empty-data and failed paths explicitly clear it so a stale divider from an
earlier run never survives.

**Design — metrics table.** New `out_of_sample_comparison_rules.py`
reuses `BOT-115D`'s `report_comparison_rules.build_metric_comparison_rows()`
directly (it is already generic over any two `BacktestMetrics`) rather than
re-deriving the `_LOWER_IS_BETTER`/`_NEUTRAL_FIELDS` tone logic a second
time. New `OutOfSampleComparisonDialog` mirrors `ReportComparisonDialog`'s
shape but simplified — no file loading, no second chart (the split is
already drawn on the main chart) — sourced entirely from the existing
`BackTestViewModel.run_result.comparison_snapshot()` retained snapshot
(`result.out_of_sample`), refreshed on the same `statCardsChanged` signal
`ReportComparisonDialog` already uses. Wired via a new
`openOutOfSampleComparisonRequested` signal / `requestOpenOutOfSampleComparison`
slot on `BackTestViewModel`, a lazy-construction entry in
`BackTestModalsHost`, and a new "In-Sample vs Out-of-Sample" button in the
top panel — all mirroring `BOT-115D`'s own "Compare reports" wiring
end to end.

**Tests** (all mutation-verified where the logic warrants it):
`test_out_of_sample_comparison_rules.py` (+8 — split description, the
overfit warning's exact `>` boundary, metric-row delegation, divider
timestamp derivation and its empty-equity-curve fallback);
`test_out_of_sample_comparison_dialog.py` (+7 — no-run and
no-validation-yet messages, a validated run's split/table, the warning's
visibility both ways, `statCardsChanged` refresh, the Close button);
`test_chart_card.py` (+3 — divider draws/clears/moves against the real
plot); `test_backtest_chart_host.py` (extended delegation test);
`test_backtest_presenter.py` (+4 — divider drawn at the correct timestamp,
a stale divider cleared by a subsequent unsplit run, cleared on empty data,
cleared on failure; the "drawn" test verified by mutation: removing the
`_apply_out_of_sample_divider()` call made it fail for the right reason,
then restored); `test_backtest_top_panel_layout.py` (+1 — the new button's
click wiring).

**Verification**: `ruff check`/`ruff format --check` clean on every touched
file. mypy (gate's real invocation — cwd at the parent directory,
`MYPYPATH` set to a sibling `Sagittarius_Engine` checkout + that parent):
zero errors across 676 source files under `Sagittarius_Elite_Warrior/`,
same as before this change (`support/charting/**`, including the new
divider file, is pre-existing wholesale-excluded debt, unrelated to this
task). `tests/unit/architecture` — 440 passed.
`tests/unit/modules/backtesting` — 901 passed, no regressions.
`tests/unit/support/charting` — 224 passed, no regressions.
