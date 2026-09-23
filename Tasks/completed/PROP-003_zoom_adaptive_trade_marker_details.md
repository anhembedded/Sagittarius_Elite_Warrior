# PROP-003: Chi Tiết Marker Thích Ứng Mức Phóng To (Zoom-Adaptive Trade Marker PnL Details)

- **ID**: `PROP-003`
- **Type**: Proposal / UX Enhancement
- **Module**: `ChartCard / MarkerLayer / MarkerLOD`
- **Status**: `✅ Done (2026-09-23)`
- **Target Version**: `Backtest UX Polish`

---

## 1. Bối cảnh & Vấn đề (Context & Problem)

- Khi biểu đồ ở mức zoom xa (toàn bộ lịch sử hàng nghìn cây nến), việc ẩn text và chỉ vẽ icon tam giác nhỏ gọn là thiết kế tối ưu để tránh rối mắt và bảo toàn FPS.
- Tuy nhiên, khi người dùng zoom sâu vào một đoạn ngắn (chỉ có từ 10 đến 30 cây nến trên màn hình), biểu đồ có rất nhiều không gian trống. Việc người dùng phải rê chuột vào từng tam giác để xem % lãi/lỗ hoặc nhãn lý do thoát lệnh tạo thêm thao tác không cần thiết.

---

## 2. Mục tiêu Đề xuất (Proposal Goals)

1. **Hiển thị linh hoạt theo Mức độ Chi tiết (Level-of-Detail - LOD)**:
   - **Mức Thu nhỏ (Dense / High-level: $> 80$ nến hiển thị)**:
     - Chỉ vẽ icon tam giác tối giản 10px $\times$ 8px.
   - **Mức Trung bình (Medium: 30 - 80 nến hiển thị)**:
     - Vẽ icon tam giác + chấm chỉ báo giá thực thi.
   - **Mức Phóng to Cực đại (Ultra-detailed: $< 30$ nến hiển thị)**:
     - Bên cạnh icon tam giác, tự động vẽ thêm **Mini-badge % PnL** nhỏ gọn (ví dụ: `+2.1%` nền xanh nhạt hoặc `-0.9%` nền đỏ nhạt) và nhãn ngắn (`TP`, `SL`, `Sig`).
2. **Không gây xé hình hay giật lag**:
   - Quá trình chuyển đổi giữa các trạng thái LOD diễn ra tức thì trong chu kỳ `refresh_window()` của `MarkerLayer` / C++ native renderer.

---

## 3. Thiết kế Kỹ thuật (Technical Design)

### 3.1. Phân tầng LOD & Viewport Windowing
- `marker_lod.py`:
  - Mở rộng hàm `select_marker_display()` để xác định `MarkerDensityMode` (DENSE, MEDIUM, DETAILED) dựa trên tỷ lệ `visible_candles_count = max_x_idx - min_x_idx`.
- `marker_layer.py` (`TriangleMarkerItem`):
  - Hỗ trợ vẽ kèm text item phụ khi ở chế độ `DETAILED`.
  - Tái sử dụng pool `TriangleMarkerItem` mà không tạo mới object liên tục khi zoom in/out.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] **AC-1**: Khi zoom vào $< 30$ nến, mini-badge PnL tự động xuất hiện cạnh marker.
- [x] **AC-2**: Khi zoom ra $> 80$ nến, badge PnL tự động ẩn đi và chỉ giữ icon tam giác.
- [ ] **AC-3**: Tỷ lệ FPS trong suốt quá trình zoom duy trì $\ge 60$ FPS. — **deferred**, see §5.
- [x] **AC-4**: Unit tests kiểm tra tính chính xác của thuật toán phân cấp LOD trong `test_marker_lod.py`.

---

## 5. Implementation Notes (2026-09-23)

Built as specified, with three re-scope decisions made against the real
code rather than the proposal's own (partly stale) technical sketch:

- **§3.1 said "mở rộng `select_marker_display()`"** — not done that way.
  `select_marker_display()`'s own LOD axis (pixel-collision aggregation)
  is orthogonal to `MarkerDensityMode` (candle-count-based detail level);
  folding the two together would have coupled two independently-varying
  concerns. Implemented as a **second, separate axis**:
  `marker_lod.classify_marker_density(visible_candle_count(...))`, a pure
  function `MarkerLayer` calls alongside (not inside)
  `select_marker_display()`. AC-1/AC-2's thresholds (30/80 candles) are
  implemented exactly as specified.
- **The badge does not widen `MarkerPoint`.** `MarkerPoint` (a plain
  5-tuple) is a public extensibility contract: custom indicator scripts
  emit it via `emit_markers()`/`draw_markers()`
  (`support/indicators/ui/runner.py`) with no version negotiation — adding
  a 6th required element would silently break every existing script the
  moment it destructures a marker tuple positionally
  (`pitfalls/source.md` #1's general lesson, confirmed for this specific
  seam by `test_dashboard_presenter.py`'s own literal 5-tuple construction
  of a script marker). Nor does it live in `_exit_marker()`'s own `text`
  field — that field is pinned by exact-equality assertions in 4 existing
  test files (`test_chart_canvas_view.py`,
  `test_truthful_backtest_markers_and_logs.py`,
  `test_backtest_truthful_markers_integration.py`) that exist specifically
  to prove a long exit is never mislabeled "Sell"/"Short" — folding a PnL
  suffix into that same string would entangle an unrelated correctness
  guarantee with a display concern. Instead, `MarkerLayer.set_markers()`
  gained an **optional, positionally-aligned `badges` parameter**
  (`Sequence[str | None] | None = None`), threaded through
  `IndicatorManager`/`ChartCard`/`IBacktestChartHost` the same way — every
  existing 2-arg caller (indicator scripts) is unaffected.
- **AC-3 (≥60 FPS) is not verified and is deferred**, undecided rather
  than silently dropped: this repo has no automated FPS-measurement
  harness (`ci-rule.md` names Desktop E2E as opt-in/real-display only,
  never headless), and fabricating a numeric FPS assertion without a real
  measurement mechanism would be exactly the "invented progress" 
  `report-rule.md` §1 forbids. What ships instead: `MarkerLayer` reuses
  its existing `TriangleMarkerItem` pool unchanged (no new per-frame
  allocation), and the added badge is a single child `QGraphicsSimpleTextItem`
  toggled via `setVisible()` — the same reuse-not-recreate pattern the
  pool already used pre-`PROP-003`. A follow-up task should add a Desktop
  E2E perf harness before this AC can be honestly checked off.
- The mockup's short reason codes ("TP, SL, Sig") are implemented as
  `_EXIT_REASON_SHORT_CODES` in `chart_canvas_view.py`, covering all 5
  `ExitReason` members (`TP`, `SL`, `Sig`, `EOB`, `Liq`) — a superset of
  the proposal's own 3-code example.

**Files**: `support/charting/chart_card/marker_lod.py` (`MarkerDensityMode`,
`classify_marker_density`, `visible_candle_count`),
`support/charting/chart_card/marker_layer.py` (`TriangleMarkerItem` badge
child item, `MarkerLayer.set_bar_seconds`/badge storage/density-aware
materialization), `support/charting/chart_card/indicator_manager.py`
(`set_marker_bar_seconds` passthrough, `set_script_markers` badges param),
`support/charting/chart_card/chart_card.py` (`_apply_x_range` refreshes bar
seconds every pan/zoom), `modules/backtesting/ui/ports/i_backtest_chart_host.py`
+ `logic/backtest_chart_host.py` (widened `set_script_markers`),
`modules/backtesting/ui/logic/chart_canvas_view.py`
(`trade_marker_badges_for_trades`, `_exit_badge`), `modules/backtesting/ui/backtest_view.py`
(`_filtered_trades`/`_filtered_trade_flag_badges`, both call sites).

**Tests**: `test_marker_lod.py` (+8 — `visible_candle_count`/
`classify_marker_density` boundary cases, AC-4), new
`test_marker_layer.py` (7 — badge visibility per density mode, hidden
before `set_bar_seconds()` is ever called, hidden for an aggregated
marker, re-evaluated on a threshold crossing with no marker-set change),
`test_chart_canvas_view.py` (+5 — badge alignment/short-code coverage),
`test_backtest_view_layout.py` (+1 — wiring, mutation-verified: removing
the badges argument from `_render_chart()`'s `set_script_markers()` call
was confirmed to turn it red, then restored),
`test_backtest_chart_host.py` (delegation tuple updated for the new
explicit-forwarding convention).

**Verification**: `ruff check`/`ruff format --check` clean on every touched
file; mypy (`--config-file pyproject.toml --namespace-packages
--explicit-package-bases`) introduces zero new errors on any touched file.
`tests/unit/modules/backtesting/` (808), `tests/unit/support/charting/` +
`tests/unit/architecture` (656), `tests/unit/modules/trading/` +
`tests/unit/support/indicators/` (1051): all green.
