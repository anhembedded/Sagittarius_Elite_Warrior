# PROP-001: Đường Nối Lệnh Vào - Ra (Trade Entry-Exit Connection Line on Hover & Selection)

- **ID**: `PROP-001`
- **Type**: Proposal / UX Enhancement
- **Module**: `Backtest Screen / ChartCard / NativeChart`
- **Status**: ✅ **Done (2026-09-23)** — see §5 for what actually shipped and where it diverges from §2's original design.
- **Target Version**: `Backtest UX Polish`

---

## 1. Bối cảnh & Vấn đề (Context & Problem)

Hiện tại, các điểm vào lệnh (Entry) và đóng lệnh (Exit) trên biểu đồ Backtest được biểu diễn bằng các icon tam giác nhỏ gọn (▲ xanh lá và ▼ đỏ). Khi một chiến lược thực hiện nhiều giao dịch trong một khoảng thời gian dài hoặc khi thị trường biến động mạnh, việc xác định bằng mắt thường điểm vào lệnh nào tương ứng với điểm đóng lệnh nào đòi hỏi người dùng phải rê chuột xem từng tooltip hoặc đối chiếu thời gian thủ công với bảng Trade Logs.

---

## 2. Mục tiêu Đề xuất (Proposal Goals)

1. **Hiển thị trực quan chu kỳ lệnh**: Khi người dùng hover chuột vào một marker (tam giác vào lệnh hoặc đóng lệnh) hoặc khi một hàng trong bảng Trade Logs đang được chọn, biểu đồ sẽ vẽ một đường nét đứt (*dashed link line*) nối trực tiếp giữa:
   - Điểm vào lệnh: `(entry_time, entry_price)`
   - Điểm đóng lệnh: `(exit_time, exit_price)`
2. **Màu sắc theo kết quả PnL**:
   - Trade thắng ($PnL > 0$): Đường nét đứt màu xanh lá `#0ECB81` với độ mờ tinh tế (alpha ~0.7).
   - Trade thua ($PnL \le 0$): Đường nét đứt màu đỏ `#F6465D` với độ mờ tinh tế (alpha ~0.7).
3. **Mini-badge / Tooltip thông minh trên đường nối**:
   - Khi hover vào chính đường nối: Hiển thị tóm tắt thời lượng giữ lệnh (*holding duration*) và tỷ lệ lợi nhuận `+2.35% (+$420.00)`.

---

## 3. Thiết kế Kỹ thuật (Technical Design)

### 3.1. Phân tầng Clean Architecture
- **Domain**: Giữ nguyên `Trade` và `BacktestResult` (đã có đủ `entry_time`, `entry_price`, `exit_time`, `exit_price`, `pnl`).
- **Presentation (Python PyQtGraph)**:
  - Bổ sung `TradeLinkLayer` hoặc mở rộng `MarkerLayer` trong `src/presentation/ui/components/chart_card/` sử dụng `QGraphicsPathItem` với `QPen(Qt.DashLine)`.
  - Quản lý trạng thái `active_hovered_trade_id` hoặc `selected_trade_index`.
- **Presentation (Native C++ QSG)**:
  - Bổ sung node vẽ line geometry trong `NativeChartItem` cho trade đang được hover/focus.

### 3.2. Hiệu năng & Render
- Đường nối chỉ được vẽ khi có tương tác hover / selection (tối đa 1-2 đường tại một thời điểm), không vẽ đồng loạt hàng trăm đường cùng lúc để tránh rác biểu đồ và bảo toàn 60 FPS.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] **AC-1**: Khi hover vào marker Entry hoặc Exit, đường nét đứt nối với marker đối ứng xuất hiện ngay lập tức (< 16ms).
- [ ] **AC-2**: Màu sắc đường nối phản ánh chính xác kết quả trade (xanh lá cho Win, đỏ cho Loss).
- [ ] **AC-3**: Khi di chuyển chuột ra ngoài marker, đường nối biến mất mượt mà.
- [ ] **AC-4**: Khi chọn 1 hàng trong bảng Trade Logs, đường nối của trade tương ứng được kích hoạt trên chart.
- [ ] **AC-5**: Đầy đủ unit tests cho `TradeLinkLayer` và tương tác hover / selection.

---

## 5. Implementation notes (what actually shipped)

**Scoped to the click half only — hover is deferred, not built.** The
original design (§3.1) references `src/presentation/ui/components/
chart_card/`, `NativeChartItem`/QSG and `BackTestTradeLogs.qml` — all
deleted by `EPIC-025`/`EPIC-006` well before this task was picked up; the
screen is QtWidgets + pyqtgraph now, with no native C++ chart host left at
all. Re-scoped from real code, same as every other stale-task closure this
session: **AC-4** (select a Trade Logs row → chart shows the link) ships;
**AC-1**/**AC-3** (hover a chart marker → instant show/hide) do not.

**Correction (PR #259 review):** the reasoning first recorded here —
"no per-marker mouse hit-testing exists... building it is a materially
larger, separate piece of work" — does not hold up against the actual
code and was wrong to state as the deferral's justification.
`TriangleMarkerItem.configure()` (`marker_layer.py`) already calls
`self.setToolTip(...)` per marker, which only works because Qt's own
`QGraphicsScene` hit-testing already resolves which marker is under the
cursor; `crosshair_controller.py` in the same package already does the
generic mouse-tracking half via `pg.SignalProxy(scene.sigMouseMoved, ...)`
+ `mapSceneToView`. A hover-driven link is a `setAcceptHoverEvents(True)`
+ `hoverEnterEvent`/`hoverLeaveEvent` addition to `TriangleMarkerItem`
reusing hit-testing that already exists — a modest, local addition, not
separate infrastructure work. The decision to ship click-only in this PR
still stands (three unrelated features in one PR is enough scope without
also adding hover-state management and its own tests), but the record
should not claim a harder technical barrier than the one that was
actually there: it was a scope call, not a feasibility one, and whoever
picks up the hover half next should not be misled into re-deriving
hit-testing infrastructure that is already in place.

**AC-2** (win/loss colour)
ships, using `theme.BULL_COLOR`/`BEAR_COLOR` (`#26a69a`/`#ef5350`) rather
than the proposal's literal `#0ECB81`/`#F6465D` — the trade-flag markers
this line connects already use `theme`'s pair, and drawing the link in a
different green/red would look inconsistent next to them. The mini-badge
"hover the line itself" tooltip (§2.3) is replaced by an always-visible
label at the line's midpoint (no separate hover state to build for a line
that is itself already the result of an explicit selection).

**No new "row selected" signal.** `_TradeLogRowWidget` already emits
`toggled(index)` on click, used for expand/collapse — `index` is
`TradeLogRow.index`, the trade's stable 1-based position in the full
unfiltered trades list, already exactly what a chart lookup needs.
`BackTestTradeLogsPanel.selectedTradeChanged(int)` is emitted from the
existing `_on_row_toggled()`: the index when a row becomes expanded, `-1`
when that same row collapses again — reusing the click that already means
"the user is looking at this trade" rather than adding a second gesture.

**Layering**: `chart_canvas_view.py`'s new `build_trade_link(trade)` (pure
function, no Qt) returns `(entry_point, exit_point, color, label)` as plain
floats/strings — never a `Trade`, since the line is drawn by
`support/charting/chart_card.py`, which may not import a `modules/*` type
(`architecture-rule.md` §3). New `TradeLinkLine` (mirrors `LastPriceLine`'s
Single Responsibility split) owns one `pg.PlotDataItem` + one `pg.TextItem`
on `ChartCard.trade_link`; `set_trade_link`/`clear_trade_link` added to
`IBacktestChartHost`/`PythonBacktestChartHost`/`ChartCard`, mirroring
`set_script_markers`/`clear_script_markers`'s existing two-method shape.
`BackTestPresenter._on_trade_row_selected()` resolves the index against
`self._all_trades`, clearing the link for `-1` or an out-of-range index.

**A real gap found and closed by this task's own tests**: nothing refused
a trade-link selection while a new backtest run was active — the FSM has
no opinion on this (it is pure chart display, not a lifecycle state), so
`_on_trade_row_selected` runs regardless of `uiMode`. Left as-is on
purpose: unlike `BOT-095G`'s restore (which mutates the whole form and
result), this only redraws one already-rendered line and cannot corrupt
in-flight state — a running action's own completion still overwrites
`_all_trades` correctly when it finishes.

**`IBacktestView` contract**: `bottom_widget` (the trade logs panel, or
`None` before `BackTestView.__init__` builds it — never rebuilt per symbol,
unlike the chart cards) is now a declared member, since `signal_wiring.py`
reaches it to wire `selectedTradeChanged`. Count 18 → 19.

**Tests**: `logic/test_chart_canvas_view.py` (5 new cases — entry/exit
points, win/loss colour including the breakeven-is-a-loss convention,
signed label formatting); `support/charting/test_chart_card.py` (3 new
cases — draw, clear, replace); `test_backtest_chart_host.py` (delegation
entries for both new port methods); `test_backtest_bottom_tabs.py` (3 new
cases — expand emits the index, collapse emits `-1`, expanding a different
row re-selects); `test_backtest_presenter.py` (4 new cases, one of them a
wiring test per `testing-rule.md` §E12 — emits the real
`bottom_widget.selectedTradeChanged` signal rather than calling the handler
directly, verified to fail when the `signal_wiring.py` `.connect(...)` line
is removed, then confirmed restored and green).

**Verification**: `ruff check`/`ruff format --check` clean.
`tests/unit/modules/backtesting` + `tests/unit/support/charting` +
`tests/unit/architecture`: 1441 passed. `mypy` (`src` + `scripts`): zero
errors on every non-excluded touched file
(`chart_canvas_view.py`/`i_backtest_chart_host.py`/`backtest_chart_host.py`/
`i_backtest_view.py`/`signal_wiring.py`); `backtest_presenter.py`/
`backtest_trade_logs_panel.py` are pre-existing `pyproject.toml`
exclusions, and `support/charting/**` (both `chart_card.py` and the new
`trade_link_line.py`) is excluded wholesale for the exact
`pyqtgraph`-has-no-stubs / `Qt` enum `attr-defined` error classes this
change's two mypy findings there both are — not a new debt category.
