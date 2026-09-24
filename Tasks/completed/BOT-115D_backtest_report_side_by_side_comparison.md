# Nhiệm vụ: So sánh 2 Báo cáo Cạnh nhau

**Mã Task:** `BOT-115D`  
**Thuộc Epic:** [`BOT-115`](../backlog/BOT-115_backtest_report_persistence_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** ✅ **Done (2026-09-24)**  
**Dependencies:** [`BOT-115C`](BOT-115C_backtest_report_import_and_readonly_state.md) ✅

---

## 1. Vì Sao Task Này Mới Là Đích Đến

3 task trước làm cho báo cáo *lưu được* và *mở lại được*. Nhưng lý do thật sự trader lưu báo cáo là để **đối chiếu**: "đổi EMA 200 sang 150 thì tốt lên hay xấu đi?", "thêm phí 0.075% thì chiến lược còn lãi không?", "bản engine mới có làm đổi kết quả chiến lược cũ không?".

Không có màn so sánh thì user phải mở 2 file lần lượt và tự ghi số ra giấy — đúng cái nỗi đau epic này sinh ra để xoá.

---

## 2. Triển Khai

Modal so sánh 2 cột (tái dùng `OverlayHost` của [`BOT-087`](../completed/BOT-087_overlay_host_engine.md), như mọi popup màn Backtest sau [`BOT-088`](../completed/BOT-088_migrate_backtest_popups_to_overlay_host.md)):

1. **Bảng diff cấu hình** — chỉ liệt kê field **khác nhau**, tái dùng thẳng `BacktestRunConfig.compute_diff_summary()` đã có sẵn (đang dùng cho banner dirty-tracking) thay vì viết logic so sánh thứ hai.
2. **Bảng metrics side-by-side** — mọi chỉ số của `BacktestMetrics` xếp 2 cột + cột chênh lệch, tô xanh/đỏ theo hướng tốt/xấu. Cẩn thận: với `max_drawdown_percent` hay `max_consecutive_losses` thì **nhỏ hơn là tốt hơn** — không được tô màu máy móc theo dấu của hiệu số.
3. **Equity curve chồng lên nhau** — 2 đường trên cùng một trục, chuẩn hoá về cùng mốc 100% nếu `initial_balance` khác nhau (không chuẩn hoá thì so 2 lần chạy khác vốn là vô nghĩa).
4. Nguồn của mỗi cột: một file trên đĩa, hoặc kết quả đang hiển thị trên màn hình.

---

## 3. Kiểm Thử

- 2 report cùng config, khác kết quả → bảng diff config rỗng, có thông báo *"Cấu hình giống hệt nhau"* thay vì bảng trống khó hiểu.
- Chỉ số "nhỏ hơn là tốt hơn" tô màu đúng chiều.
- 2 report khác `initial_balance` → đường vốn chuẩn hoá đúng.
- 2 report khác symbol/timeframe → vẫn so được nhưng có cảnh báo rõ đây là so sánh giữa 2 thị trường khác nhau.

---

## 4. Implementation Notes (2026-09-24)

Built as specified, with two re-scope decisions made against the real
code rather than the task's own (partly stale) technical sketch:

- **§2's "tái dùng `OverlayHost` của `BOT-087`"** — not applicable. `BOT-088`
  (linked by this task's own §2) already migrated every Backtest popup off
  `OverlayHost`/`QQuickWidget` onto `Overlay`-based `QDialog`s
  (`backtest_modals/modals_host.py`'s own docstring: "Replaces both
  `BackTestModals.qml` and Engine's `OverlayHost`/`QQuickWidget`"). Built as
  the 12th `Overlay` subclass in that same package instead, wired through
  `BackTestModalsHost` exactly like the other 11 (`openCompareReportsRequested`
  signal → `_open_report_comparison()`), with a "Compare reports" button on
  the top panel next to "Import report".
- **§2.4's "nguồn của mỗi cột: một file trên đĩa, hoặc kết quả đang hiển thị"**
  — implemented as Column A **always** being the result currently on screen
  (`BackTestViewModel.run_result.comparison_snapshot()`, retained by the
  Presenter right alongside its stat cards) and Column B **always** loaded
  from a file. A second "pick the source" control for Column A was left out:
  Column A already *is* whatever is on screen, which is the point of
  comparing against it — the task's own motivating examples ("đổi EMA 200
  sang 150 thì tốt lên hay xấu đi?") are exactly this "current vs. a saved
  baseline" shape. A file-vs-file comparison (no result on screen at all)
  is not covered; nothing in the task's own §3 test list requires it, and
  it is a small, comparably-scoped follow-up if a real need shows up
  (swap Column A for a second "Load…" button and drop the `comparison_snapshot`
  read).
- **§2.1's diff table** — reuses `BacktestRunConfig.compute_diff_summary()`
  verbatim (a single joined line) rather than a rebuilt per-field row list,
  per the task's own instruction "thay vì viết logic so sánh thứ hai".
  Splitting that string back into rows would mean either parsing it
  (fragile — some of its own segments contain a comma, e.g. `f"{value:,.0f}"`
  for Capital) or duplicating its field list a second time, which is what
  the task explicitly says not to do.
- **§2.2's colour direction** — `max_drawdown_percent` and
  `max_consecutive_losses` (the task's own two named examples) plus
  `max_drawdown_duration_bars` (same shape) are treated as "smaller is
  better"; every other numeric metric defaults to "bigger is better",
  including the already-negative `gross_loss`/`avg_losing_trade`/
  `largest_losing_trade` (a loss closer to zero *is* the bigger number, so
  no special-casing needed there). `total_closed_trades`,
  `avg_bars_per_trade` and the two boolean flags are shown with no tone at
  all — a trade count is not "better" or "worse" in either direction.
- **§2.2's "2 cột + cột chênh lệch"** — implemented as a single Δ (B − A)
  column, coloured by direction, rather than colouring both A and B
  columns independently — one column reads the change at a glance, the
  same convention `compute_diff_summary()`'s banner already reads by (an
  arrow from old to new).

**Files**: `logic/report_comparison_snapshot.py` (`ReportComparisonSnapshot`),
`logic/report_comparison_rules.py` (config diff, market-mismatch warning,
metric-row tone, equity normalization, loaded-file label — all pure),
`_report_comparison_chart_widget.py` (`ReportComparisonChartWidget`, a
second small `pyqtgraph` widget alongside `_drawdown_chart_widget.py`, per
that file's own "own small widget, not `ChartCard`" precedent),
`backtest_modals/report_comparison_dialog.py` (`ReportComparisonDialog`),
`view_models/run_result_view_model.py` (`comparison_snapshot()`/
`set_comparison_snapshot()`, same shape as `extended_metrics_snapshot()`),
`backtest_presenter.py` (`_present_result()` sets the snapshot;
`_on_backtest_empty()`/`_on_backtest_failed()` clear it — both already
cleared `extended_metrics_snapshot` at the same two spots),
`backtest_view_model.py` (`openCompareReportsRequested`/
`requestOpenCompareReports`), `backtest_modals/modals_host.py` (wiring),
`backtest_top_panel.py` ("Compare reports" button).

**Tests**: `logic/test_report_comparison_rules.py` (15 — diff text,
market-mismatch warning, tone direction for higher-is-better/
lower-is-better/neutral fields including the zero-delta case, equity
normalization, non-positive-balance guard, loaded-file label),
`test_report_comparison_chart_widget.py` (4 — empty/populated/cleared
states, both curves independently addressable), `test_report_comparison_dialog.py`
(7 — Column A reads the real view-model snapshot, `statCardsChanged`
refreshes an open dialog, loading a real `.sagi-report.json` file through
the actual "Load report to compare…" button click fills Column B and the
metrics table, a cancelled file picker and a malformed file both degrade
without crashing, Close button closes the dialog), `test_backtest_presenter.py`
(+3 — the comparison snapshot is set on success and cleared on
empty/failed, mutation-verified: removing the `set_comparison_snapshot`
call in `_present_result()` was confirmed to turn all 3 red, then
restored), `test_backtest_top_panel_layout.py` (+1 — button wiring).

**Verification**: `ruff check`/`ruff format --check` clean on every touched
file; mypy (`--config-file pyproject.toml --namespace-packages
--explicit-package-bases`) introduces zero new errors — confirmed by
comparing the exact error count/file set on the touched `backtest_modals`/
`view_models`/`backtest_view_model.py`/`backtest_top_panel.py` files before
and after this change (95 errors in 33 files, identical both times — all
pre-existing PySide6 `@Property` descriptor false positives, same baseline
class documented for `backtest_presenter.py` throughout this epic) and by
grepping the full `src`+`scripts` mypy run for any error naming this
feature's own new identifiers (none). `tests/unit/modules/backtesting/`
(all green, no regressions) + the new test files above.
