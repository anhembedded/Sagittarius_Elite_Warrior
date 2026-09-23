# PROP-002: Tương Tác Hai Chiều Bảng Trade Logs & Biểu Đồ (Bi-directional Table-to-Chart Navigation & Highlighting)

- **ID**: `PROP-002`
- **Type**: Proposal / UX Enhancement
- **Module**: `Backtest Screen / Trade Logs / ChartCard`
- **Status**: ✅ **Done, half only (2026-09-23)** — see §5 for what shipped and what is deliberately deferred.
- **Target Version**: `Backtest UX Polish`

---

## 1. Bối cảnh & Vấn đề (Context & Problem)

Hiện tại, bảng **Trade Logs** (danh sách lịch sử lệnh) và **Chart Canvas** (biểu đồ nến & markers) hoạt động tương đối độc lập về mặt tương tác người dùng:
- Khi người dùng muốn xem lại một lệnh bị lỗ nặng hoặc lãi lớn trên bảng Trade Logs, họ phải tự cuộn trục thời gian trên biểu đồ để tìm thời điểm diễn ra lệnh đó.
- Khi người dùng nhìn thấy một cụm marker trên biểu đồ và muốn tra cứu chi tiết thông số lý do vào/ra lệnh, họ phải lật qua các trang phân trang của bảng Trade Logs để tìm dòng tương ứng.

---

## 2. Mục tiêu Đề xuất (Proposal Goals)

1. **Điều hướng từ Bảng sang Biểu đồ (Table $\rightarrow$ Chart)**:
   - Khi người dùng click chọn 1 hàng trong bảng `Trade Logs`, biểu đồ tự động thực hiện cuộn mượt mà (*smooth pan/zoom*) để đưa cây nến Entry & Exit của lệnh đó vào trung tâm màn hình.
   - Làm nổi bật (*pulse animation* hoặc *ring highlight*) cặp marker tương ứng trên chart trong 2 giây.
2. **Điều hướng từ Biểu đồ sang Bảng (Chart $\rightarrow$ Table)**:
   - Khi người dùng click vào một tam giác marker trên biểu đồ:
     - Bảng `Trade Logs` tự động chuyển đến đúng trang phân trang (*page number*) chứa lệnh đó.
     - Tự động cuộn và bôi sáng hàng tương ứng trong bảng.

---

## 3. Thiết kế Kỹ thuật (Technical Design)

### 3.1. Phân tầng Clean Architecture & Signals
- **ViewModel (`backtest_view_model.py`)**:
  - Khai báo thuộc tính `@Property(int)` `focusedTradeIndex` và signal `focusedTradeChanged`.
  - Khai báo `@Slot(int)` `focusTrade(int index)` được gọi từ QML table delegate hoặc chart interaction.
- **Presenter (`backtest_presenter.py`)**:
  - Nhận sự kiện `focusTrade`:
    - Tính toán phạm vi timestamp `(min_ts, max_ts)` của trade.
    - Gọi `chart_card.set_view_range(min_ts - padding, max_ts + padding)`.
    - Tính toán số trang phân trang: `target_page = (index // PAGE_SIZE) + 1` và cập nhật `tradeLogCurrentPage`.
- **QML Views**:
  - `BackTestTradeLogs.qml`: Bind highlight delegate với `viewModel.focusedTradeIndex`.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] **AC-1**: Click vào hàng trong `Trade Logs` điều hướng biểu đồ đến đúng thời gian của lệnh với biên đệm an toàn. **Shipped** — see §5.
- [ ] **AC-2**: Click vào marker trên biểu đồ tự động chuyển bảng `Trade Logs` đến đúng trang và chọn đúng hàng. **Deferred** — see §5.
- [x] **AC-3**: Tương tác mượt mà, không bị giật lag, không reload lại dữ liệu hay kích hoạt lại FSM. Panning reuses `ChartCard`'s existing `setXRange`/`setLimits` machinery; no data reload, no FSM dispatch.
- [x] **AC-4**: Kiểm thử đầy đủ với Unit test (pure function, port delegation, `ChartCard`, Presenter). Sanity untouched — this is pure chart display wiring, not a new boot-time surface.

---

## 5. Implementation notes (what actually shipped)

**Scoped to the Table→Chart half only — Chart→Table is deferred, not built.**
Re-verified from real code before implementing (same discipline as every other
stale-task pickup this session): the original design's §3.1 (`@Property`/
`@Slot` "called from QML table delegate", `BackTestTradeLogs.qml` binding) is
entirely stale — this repository has zero `.qml` files
(`ui-presentation-rule.md` §1, enforced by `test_no_new_qml.py`), and
`PROP-001` (merged the same day, earlier) already solved Table→Chart
selection with plain Qt signals between two QtWidgets classes:
`BackTestTradeLogsPanel.selectedTradeChanged` → `signal_wiring.py` →
`BackTestPresenter._on_trade_row_selected(index)`.

**AC-1 ships** by extending that already-wired handler rather than adding a
parallel `focusTrade` slot: `_on_trade_row_selected` now also calls the new
`chart_card.set_view_range(min_ts, max_ts)` (added to `IBacktestChartHost`/
`PythonBacktestChartHost`/`ChartCard`, mirroring `set_trade_link`'s existing
two-method-pair shape) with a window computed by the new pure function
`build_trade_view_range(trade)` in `chart_canvas_view.py` — padding is 50% of
the trade's own duration on each side, floored at 60 seconds so a
same-candle scalp (near-zero duration) still gets a readable window instead
of a sliver. `ChartCard._apply_view_bounds()`'s existing `setLimits()` clamps
the result to the loaded history exactly as it clamps any other pan/zoom, so
no new bounds-checking was needed.

**The proposal's "pulse animation / ring highlight" (§2 goal 1, second
bullet) is intentionally not built.** `PROP-001` already gives the selected
trade a persistent, always-visible dashed link line with a PnL label — that
already *is* the highlight, and it does not disappear after 2 seconds the
way the proposal's pulse would. Building a second, temporary animation on
top of an already-persistent highlight would be new machinery (this
codebase has no existing marker/line pulse-animation precedent anywhere) for
a marginal, arguably redundant visual effect — against
`architecture-rule.md` §7.2.1's "reuse proven patterns" bias. If a future
task wants item-level attention-drawing (e.g. for AC-2's chart-side
highlight, which has no persistent-line equivalent to lean on), it should
design that fresh rather than retrofitting this one.

**AC-2 (Chart→Table) is genuinely new work, not something already built and
overlooked** — verified directly against the current code, not assumed:
- `TriangleMarkerItem` (`support/charting/chart_card/marker_layer.py`) has
  no click handling today — only `setToolTip()` on hover, which works
  because `QGraphicsScene` already does per-item hit-testing for tooltips;
  reusing that same per-item dispatch for a click (`mousePressEvent`
  override) is the right mechanism, but does not exist yet.
- `MarkerPoint` (`marker_lod.py`) is a plain `(x, y, text, color, direction)`
  tuple with no trade identity, and `MarkerLayer` pools/reuses
  `TriangleMarkerItem`s across trades as the viewport pans — resolving "which
  `Trade` was clicked" needs a new mechanism (either an opaque identity
  carried through the marker tuple, or matching the clicked point's
  `(timestamp, price, direction)` back against `_all_trades`), and
  `support/charting` may not import `modules/backtesting`'s `Trade` type
  directly (`architecture-rule.md` §3).
- `BackTestTradeLogsPanel` has real pagination (`trade_log_pagination.py`,
  `PAGE_SIZE = 20`) but no "jump to the page containing index N and
  highlight that row" method — only forward/back page navigation and the
  existing expand-acts-as-select toggle.

None of that is a small addition on top of AC-1's mechanism — it is a
comparably-sized, separate unit of work (a new marker click path, a new
`IBacktestChartHost` port method, a trade-matching function, and a new
`BackTestTradeLogsPanel` method), and this PR already bundles PROP-002
alongside `BOT-019` (an unrelated screen). Rather than rush AC-2 in
alongside that, it is left as the concrete remaining scope of this task —
whoever picks it up next has the exact gap list above, verified against the
code as it stands after this change, not guessed at.

**Tests**: `logic/test_chart_canvas_view.py` (2 new cases —
duration-proportional padding, floor for a near-instant trade);
`support/charting/test_chart_card.py` (1 new case — `set_view_range` pans
`main_plot`); `test_backtest_chart_host.py` (delegation entry for the new
port method); `test_backtest_presenter.py` (1 new case — selecting a row
pans the chart to cover the trade's real entry/exit timestamps, using
klines that actually span those timestamps so `ChartCard`'s
history-derived `setLimits()` does not clamp the assertion away).

**Verification**: `ruff check`/`ruff format --check` clean on every touched
file. `tests/unit/modules/backtesting/ui/logic/test_chart_canvas_view.py` +
`tests/unit/support/charting/test_chart_card.py` +
`tests/unit/modules/backtesting/ui/test_backtest_chart_host.py` +
`tests/unit/modules/backtesting/ui/test_backtest_presenter.py` +
`tests/unit/architecture`: 742 passed.
