# Nhiệm vụ: Mô phỏng Monte Carlo & Đánh giá Nguy cơ Phá sản (Risk of Ruin)

**Mã Task:** `BOT-107B`  
**Thuộc Epic:** [`BOT-107`](../backlog/BOT-107_strategy_robustness_and_monte_carlo_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** ✅ **Done (2026-09-24)**  
**Dependencies:** `BOT-021`, [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md)

---

## 1. Mục tiêu

Áp dụng phương pháp mô phỏng Monte Carlo để đánh giá độ ổn định của chiến lược trong tương lai:
1. **Trade Reshuffling (Xáo trộn Thứ tự Lệnh)**:
   - Lấy danh sách $N$ lệnh đã thực hiện trong quá khứ.
   - Chạy $M = 5,000$ đến $10,000$ lần xáo trộn ngẫu nhiên thứ tự các lệnh (sampling with/without replacement).
2. **Tính toán Phân phối Rủi ro**:
   - **Xác suất Phá sản (Risk of Ruin %)**: Tỷ lệ kịch bản mà tài khoản bị sụt giảm quá $50\%$ hoặc $100\%$.
   - **p95 / p99 Worst-Case Drawdown**: Mức sụt giảm vốn tồi tệ nhất ở mức tin cậy 95% và 99%.
   - **Median Expected Return**: Lợi nhuận kỳ vọng trung vị.
3. **Trực quan hóa**:
   - Vẽ chùm đường Equity mô phỏng (Monte Carlo Spaghetti Chart) và biểu đồ phân phối xác suất Max Drawdown.

---

## 2. Implementation Notes (2026-09-24)

**Re-scoped to Trade Reshuffling only** (`architecture-rule.md` §7.2.1
"seam now, variant later"): §1's "sampling with/without replacement"
phrasing named two distinct techniques — reordering the run's own closed
trades (Trade Reshuffling) versus resampling them with repeats (Bootstrap).
Only Trade Reshuffling is built; `run_monte_carlo_simulation()`'s own
docstring documents the deferred bootstrap variant as the seam's next case,
so adding it later is a local change (one new sampling function behind the
same `rng`/`trades` signature), not a redesign.

**Risk of Ruin kept distinct from max-drawdown, on purpose.** Risk of Ruin
(the classic Vince definition: probability equity ever falls to a fraction
of the *starting* balance) answers a different question than the
already-shipped peak-to-trough max-drawdown
(`contracts/backtest_metrics.py`/`drawdown_series_calculator.py`), so the
new `MonteCarloSimulationResult` carries both `risk_of_ruin_50_percent`/
`risk_of_ruin_100_percent` and `p95_max_drawdown_percent`/
`p99_max_drawdown_percent` as separate, non-conflated fields —
`test_monte_carlo_simulation.py::test_risk_of_ruin_and_max_drawdown_answer_different_questions`
proves the two numbers can legitimately differ for the same data.

**Design.** New pure domain module
`contracts/monte_carlo_simulation.py`: `run_monte_carlo_simulation(trades,
initial_balance, iterations, rng, sample_curve_count=200)` reorders the
run's own `Trade.pnl` values via a caller-supplied `random.Random` (never
touches global RNG state, so tests are deterministic) and walks each
shuffled order into a synthetic equity curve — no engine re-run, no
datetime fabrication. The full per-iteration `max_drawdowns_percent`
distribution is kept (cheap — a tuple of floats) for the histogram, while
the much heavier equity curves are capped to a bounded sample
(`sample_curve_count`) independent of `iterations`, so a 10,000-iteration
run doesn't retain 10,000 full curves. `ui/logic/monte_carlo_rules.py`
turns the result into summary lines, drawdown histogram buckets and
spaghetti-chart point series — pure functions, no Qt. Two new small
pyqtgraph widgets (`_monte_carlo_spaghetti_chart_widget.py`,
`_monte_carlo_drawdown_histogram_widget.py`, mirroring the existing
`_drawdown_chart_widget.py`/`_report_comparison_chart_widget.py` shape)
render them; the histogram is this codebase's first genuine statistical
`pg.BarGraphItem` use (the only prior one, `volume_renderer.py`, renders
candle volume, not a distribution).

**Wiring.** New `MonteCarloCoordinator` (mirrors `ChartPreviewCoordinator`
exactly: Presenter-owned, constructor-injected callables, `run()` submits
`_run_worker()` to the thread manager, `except Exception` at the worker
seam) constructs a real `Random()` per click (`# noqa: S311` — sampling,
not cryptography, same rationale precedent as
`tests/integration/golden/dataset.py`). A dedicated
`_next_monte_carlo_run_id`/`_active_monte_carlo_run_id` pair on the
Presenter (not the coordinator, which owns no FSM/id state per
`async-ui-action-rule.md` §2) fences a stale, superseded run's late
completion — mutation-verified. Signal → slot → `ModalsHost` → dialog
follows the exact shape `OutOfSampleComparisonDialog` established:
`BackTestViewModel.openMonteCarloRequested`/`runMonteCarloRequested` →
`BackTestModalsHost._open_monte_carlo()` → `MonteCarloDialog(Overlay)`,
reading `run_result.comparison_snapshot()` for the trade count (no new
"which run is this for" state). `RunResultViewModel.monteCarloResultChanged`
is a signal of its own, deliberately separate from `statCardsChanged`,
because a Monte Carlo run completes on its own schedule (a dialog button
click), not when a backtest finishes.

**No progress bar.** A 5,000–10,000-iteration trade-reshuffle over a
typical backtest's trade count runs in well under a second (pure
in-memory arithmetic, no I/O); `async-ui-action-rule.md`'s progress
requirement is for genuinely long operations, so the dialog's button
simply disables itself for the run's short duration rather than adding
throttled progress plumbing for a case that cannot occur.

**Tests** (all mutation-verified where the logic warrants it):
`test_monte_carlo_simulation.py` (+8 — deterministic reordering via a real
`Random` subclass, the risk-of-ruin-50/100 thresholds, the two-distinct-
risk-numbers proof, the bounded sample-curve cap);
`test_monte_carlo_rules.py` (+9 — summary line content, histogram bucket
boundaries and the clamp mutation, spaghetti series point shape);
`test_monte_carlo_spaghetti_chart_widget.py` (+4),
`test_monte_carlo_drawdown_histogram_widget.py` (+4 — including the
all-zero-drawdown single-bucket edge case); `test_monte_carlo_coordinator.py`
(+2 — a hand-derived synchronous `IThreadManager` fake, the
`emit_completed` mutation); `test_monte_carlo_dialog.py` (+8 — against a
real `BackTestViewModel`, including a real-button-click wiring test);
`test_backtest_presenter.py` (+7 — dispatch, no-run guard, completion,
stale-run-id fencing on both completion and failure paths mutation-verified,
failure-message storage, full dispatch-to-completion path);
`test_backtest_top_panel_layout.py` (+1 — the new button's click wiring).

**Verification**: `ruff check`/`ruff format --check` clean on every touched
file. mypy (gate's real invocation — cwd at the parent directory,
`MYPYPATH` pointing at the sibling `Sagittarius_Engine` checkout): zero
errors in any new or touched Monte Carlo file; the 706 errors present in
the full `src`+`scripts` run are all pre-existing, blamed to commits
before this branch (verified via `git blame`), none in code this task
touched. `tests/unit/architecture` — 440 passed.
`tests/unit/modules/backtesting` — 944 passed, no regressions.
`python3 scripts/check_skill_prompt_references.py` — OK.
