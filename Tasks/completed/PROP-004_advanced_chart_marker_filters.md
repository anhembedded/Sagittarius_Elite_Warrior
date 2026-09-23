# PROP-004: Bộ Lọc Marker Nâng Cao Trên Biểu Đồ Backtest (Advanced Chart Marker Filter Controls)

- **ID**: `PROP-004`
- **Type**: Proposal / UX Enhancement
- **Module**: `Backtest Screen / BackTestTopPanel / MarkerLayer`
- **Status**: ✅ **Done (2026-09-23)** — see §5 for what actually shipped and where it diverges from §3's original design.
- **Target Version**: `Backtest UX Polish`

---

## 1. Bối cảnh & Vấn đề (Context & Problem)

Hiện tại, người dùng chỉ có một checkbox duy nhất: **"Hiển thị Marker lệnh"** (Bật/Tắt toàn bộ). Khi chạy backtest trên tập dữ liệu dài (ví dụ 1 năm) với chiến lược scalping hoặc lướt sóng tần suất cao (hàng trăm lệnh), việc bật tất cả marker khiến biểu đồ bị che lấp bởi mật độ marker quá dày đặc. Người dùng không có cách nào để:
- Chỉ quan sát các lệnh thua để tìm lỗi logic chiến lược.
- Chỉ quan sát các lệnh có lợi nhuận đột biến ($> 5\%$) để đánh giá điều kiện vào lệnh.

---

## 2. Mục tiêu Đề xuất (Proposal Goals)

1. **Thêm Menu Lọc Nhanh Marker trên Thanh Điều Khiển Chart**:
   - Bên cạnh nút toggle "Marker Lệnh", thêm dropdown / popover bộ lọc:
     - **Lọc theo Kết quả (Outcome)**:
       - *Tất cả lệnh (All)*
       - *Chỉ lệnh Thắng (Wins Only)*
       - *Chỉ lệnh Thua (Losses Only)*
     - **Lọc theo Vị thế (Side)**:
       - *Tất cả (All)*
       - *Chỉ lệnh Long (Long Only)*
       - *Chỉ lệnh Short (Short Only)*
     - **Lọc theo Ngưỡng PnL (Min $|PnL|$ Threshold)**:
       - Slider hoặc input số để chỉ hiện các lệnh có $|PnL| \ge X\%$.
2. **Cập nhật tức thì không cần chạy lại Backtest**:
   - Khi thay đổi bộ lọc trên UI, chỉ cần cập nhật danh sách marker đưa vào `MarkerLayer.set_markers()`, không cần re-run engine backtest.

---

## 3. Thiết kế Kỹ thuật (Technical Design)

### 3.1. Phân tầng Clean Architecture
- **ViewModel (`backtest_view_model.py`)**:
  - Thêm các thuộc tính: `markerFilterOutcome` (ALL/WIN/LOSS), `markerFilterSide` (ALL/LONG/SHORT), `markerFilterMinPnl` (float).
- **Presenter (`backtest_presenter.py`)**:
  - Thêm phương thức `_apply_chart_marker_filters(result: BacktestResult)` để lọc danh sách `result.trades` trước khi gọi `trade_flag_markers()`.
  - Kết nối signal từ ViewModel để trigger update layer tức thì (< 5ms).
- **QML Component (`BackTestTopPanel.qml` / `MarkerFilterPopup.qml`)**:
  - Thiết kế popover gọn gàng theo chuẩn QML theme của ứng dụng.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] **AC-1**: Chọn "Wins Only" chỉ hiển thị các cặp marker của các trade có $PnL > 0$.
- [x] **AC-2**: Chọn "Losses Only" chỉ hiển thị các cặp marker của các trade có $PnL \le 0$.
- [x] **AC-3**: Thay đổi bộ lọc phản hồi tức thì trên biểu đồ, không làm reset view range của người dùng (redraws only the marker layer via `set_script_markers`, never touches the plot's view range).
- [x] **AC-4**: Trạng thái bộ lọc được lưu giữ và khôi phục an toàn — qua `chart_controls`'s own combo/spinbox state directly, not a ViewModel round-trip (see §5 for why).
- [x] **AC-5**: Unit tests kiểm tra đầy đủ các kịch bản lọc marker.

---

## 5. Implementation Notes (2026-09-23)

Re-verified against the current codebase before designing anything — §3's
`backtest_view_model.py`/`backtest_presenter.py`/`BackTestTopPanel.qml`
targets are stale (QML left this screen entirely under `EPIC-025`), but
`trade_flag_markers()` (the actual marker-building function §3 didn't
name) still exists, now in `src/modules/backtesting/ui/logic/
chart_canvas_view.py`.

**Where the filters actually live, and why not the ViewModel**:
`BacktestChartControls` (`src/modules/backtesting/ui/logic/
chart_controls.py`) is the toolbar that already owns the *existing*
single "Buy/Sell Flags" show/hide checkbox, and its own docstring states
the reason it bypasses the ViewModel/Presenter round-trip entirely: "no
config to validate or dispatch... Dumb component, emits signals, decides
nothing." The 3 new filters are the same kind of pure display state, so
they follow the same convention rather than reopening it — `MarkerOutcomeFilter`/
`MarkerSideFilter` combo boxes plus a `QDoubleSpinBox` (min `|PnL|` %),
all built as plain, unstyled `QtWidgets` (no new `setStyleSheet()`/`Palette`
import, respecting the app-styling shrink-only ratchet).

**Design**: `chart_canvas_view.py` gained `MarkerOutcomeFilter`/
`MarkerSideFilter` enums, `filter_trades_for_markers()` (a pure function,
outcome/side/min-PnL as three independently combinable predicates — a
different shape from `trade_log_filter.TradeLogFilter`'s 5 mutually-exclusive
tabs, since this proposal explicitly wants "Short + Win" simultaneously
selectable), and `trade_flag_markers_for_trades()` (the per-trade marker
loop split out of `trade_flag_markers()`, which now just calls it with
`result.trades`). `BackTestView.set_trade_flags_visible()`/`_render_chart()`
both build markers through a new `_filtered_trade_flag_markers()` helper
that reads the 3 filters straight off `self.chart_controls` before
building markers — no new ViewModel property, no new Presenter method.
`refresh_trade_flag_filters()` (new `IBacktestView`/`signal_wiring.py`
member — the contract's declared-member count moved 17 → 18) re-applies
`set_trade_flags_visible()` with the checkbox's own current state whenever
any filter changes, so a filter can never override the separate show/hide
toggle.

**A real bug found by this task's own test suite**: `QComboBox.addItem(text,
userData=<enum member>)` round-trips a `str`-subclassed `Enum` through
`QVariant` as a *plain* `str` (its value), not the enum instance —
`currentData() is MarkerOutcomeFilter.WINS_ONLY` was silently always
`False`, which would have made the outcome/side filters permanent no-ops
in production despite every widget interaction looking correct. Fixed by
re-wrapping the getters' return value (`MarkerOutcomeFilter(combo.currentData())`)
rather than trusting Qt's round-trip. A second, unrelated bug from the same
first test run: connecting `currentIndexChanged(int)`/`valueChanged(float)`
directly to `sig_marker_filter_changed.emit` (a zero-argument `Signal()`)
raised `TypeError` at the first user interaction — fixed via a small
`_emit_marker_filter_changed(*_args)` bridge method.

**Tests**: `tests/unit/modules/backtesting/ui/logic/test_chart_canvas_view.py`
(moved from a stale `tests/unit/presentation/ui/screens/` path while
touching this exact file — `filter_trades_for_markers`/
`trade_flag_markers_for_trades` pure-function coverage, including the
"all three filters combine, not override" case), `tests/unit/modules/
backtesting/ui/logic/test_chart_controls.py` (new — default filter state,
each control emits the signal, disabling trade-flags disables the 3
filters too), and two new cases in `tests/unit/modules/backtesting/ui/
test_backtest_view_layout.py` (`_filtered_trade_flag_markers()` actually
narrows under a real `BackTestView` + real `BacktestResult`, and
`refresh_trade_flag_filters()` re-applies the checkbox's own state rather
than forcing visibility on).

**Verification**: `ruff check`/`ruff format --check` clean; `mypy` (`src`
+ `scripts`, this repo's own `ci-local.ps1` invocation) reports "Success:
no issues found in 660 source files" (`chart_canvas_view.py` is
mypy-checked and stayed clean; `backtest_view.py`/`chart_controls.py` are
pre-existing `pyproject.toml` exclusions, unrelated to this change).
`tests/unit/modules/backtesting` + `tests/unit/architecture`: 1208 passed.
