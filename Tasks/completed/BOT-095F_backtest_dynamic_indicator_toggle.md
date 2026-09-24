# Nhiệm vụ: BOT-095F — Toggle Chỉ báo Tham chiếu Động trên Biểu đồ sau Backtest

**Trạng thái:** ✅ **Done — already implemented, verified 2026-09-24** (see §5)

> Thuộc Epic [`BOT-095`](../backlog/BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> Phụ thuộc: `BOT-095H`.
> **Trọng tâm**: Cho phép người dùng bật / tắt các chỉ báo kỹ thuật tham chiếu (`IndicatorPickerModal` như RSI, MACD, EMA Ribbon) và tự động vẽ / ẩn trực tiếp trên biểu đồ `ChartCanvas` sau khi Backtest đã hoàn thành mà **không bắt người dùng phải chạy lại toàn bộ thuật toán Backtest**.

---

## 1. Vấn đề Hiện tại

1. **Bật tắt chỉ báo tham khảo bị bắt chạy lại toàn bộ Backtest:**
   - Sau khi người dùng chạy xong một chiến lược Backtest (ví dụ `EmaCrossoverStrategy`), trên biểu đồ đã có nến và các đường EMA 12/26 của chiến lược.
   - Người dùng muốn bật thêm chỉ báo tham khảo `rsi_14` hoặc `macd_full` từ menu "Chỉ báo" (`IndicatorPickerModal.qml`) để đối chiếu với các điểm Buy/Sell.
   - Hiện tại, khi bật checkbox RSI trong modal:
     - Tín hiệu `enabledKeysChanged` chỉ ghi log: `_logger.info("Đã cập nhật chỉ báo tham chiếu: rsi_14")`.
     - Đường RSI **hoàn toàn không được vẽ** lên `ChartCanvas`.
     - Người dùng buộc phải bấm "Chạy Backtest" lần nữa thì `IndicatorScriptRunner` mới chạy và vẽ đường RSI.
   - Việc này gây lãng phí CPU và làm gián đoạn trải nghiệm đối chiếu của người dùng.

---

## 2. Thiết kế Kỹ thuật (Technical Design)

### 2.1. Dynamic Script Feeder trong `BackTestPresenter`
Khi nhận signal `enabledKeysChanged` từ `script_model`:
1. **Kiểm tra trạng thái biểu đồ hiện tại:**
   - Nếu `_chart_klines` (tập nến hiện tại đang vẽ trên chart) đã có dữ liệu:
     - Lấy danh sách các script vừa được kích hoạt (`newly_enabled_keys`).
     - Lấy danh sách các script vừa bị tắt (`disabled_keys`).
2. **Đối với các script vừa tắt:**
   - Gọi `self.view.chart_card.indicator_manager.clear_script_indicators(key)` (hoặc ẩn các curve/subplot tương ứng).
3. **Đối với các script vừa bật:**
   - Dựng instance của script qua `IndicatorScriptRegistry.create(key)`.
   - Feed tập nến hiện có `_chart_klines` qua script ở worker hoặc dùng cache output theo `(run_id, script_key, script_version)`; chỉ artifact render hoàn tất mới qua signal về UI thread:
     ```python
     script_runner = IndicatorScriptRunner(self.script_registry, ...)
     script_runner.feed_all(_chart_klines, [key])
     ```
   - Lắng nghe tín hiệu `on_line`, `on_region`, `on_info`, `on_marker` và đẩy thẳng dữ liệu curve lên `IndicatorManager` của `ChartCard`.
4. **Không làm thay đổi kết quả chiến lược:**
   - Việc bật/tắt chỉ báo tham chiếu thuần túy là việc hiển thị trên Chart (Visualization Layer), **không làm thay đổi danh sách giao dịch hay chỉ số PnL**, do đó **không kích hoạt cờ `CONFIG_DIRTY`**.

---

## 3. Danh sách File Cần Chỉnh sửa & Tạo mới

- ✏️ `src/presentation/ui/screens/backtest/backtest_presenter.py`: Cài đặt logic render động các script tham chiếu khi `enabledKeysChanged` phát tín hiệu.
- ✏️ `src/presentation/ui/components/chart_card/indicator_manager.py`: Đảm bảo hỗ trợ add / remove / toggle subplot và overlay script mà không cần reload toàn bộ chart.
- ✏️ `tests/unit/presentation/ui/screens/test_backtest_presenter.py`: Bổ sung test cases:
  - Backtest xong $\rightarrow$ Bật `rsi_14` $\rightarrow$ Subplot RSI xuất hiện trên chart ngay lập tức mà không cần gọi lại `RunStaticBacktestCommand`.
  - Tắt `rsi_14` $\rightarrow$ Subplot RSI bị xóa khỏi chart.

---

## 4. Tiêu chuẩn Nghiệm thu (Acceptance Criteria)

1. **Hiển thị tức thì (Instant Toggle)**:
   - Với cache hit, render nhanh và không block UI; cache miss có trạng thái loading nhỏ. Ngưỡng hiệu năng được benchmark theo số nến/script, không dùng SLA cố định `<50ms`.
2. **Không chạy lại engine backtest**:
   - `RunStaticBacktestCommand` không bị dispatch lại khi chỉ bật/tắt script tham chiếu.
   - FSM giữ nguyên trạng thái `COMPLETED` (hoặc `IDLE`), không bị đánh dấu là `CONFIG_DIRTY`.
3. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -UnitOnly` đạt 100% Passed.

4. **Race verification**:
   - Toggle nhanh on/off hoặc đổi run khi indicator đang tính không được render artifact của run cũ; signal mang `run_id` và bị fence bởi `BOT-095H`.

---

## 5. Implementation Notes (2026-09-24)

The paths in §2/§3 above are stale (`presentation/ui/screens/backtest/`,
`IndicatorPickerModal.qml`) — this codebase dropped QML and moved to the
`modules/`-based layout well before this task was picked up. Re-verified
against the real, current code rather than assumed obsolete, and found
**already fully implemented** under current paths, matching this task's
own proposed design almost exactly:

- The real widget is `IndicatorPickerDialog` (`ChecklistOverlay`, QtWidgets
  — `backtest_modals/indicator_picker_dialog.py`, `EPIC-025` PR 4.3f
  replaced `CheckboxList.qml`). Toggling a row calls
  `IndicatorScriptListModel.setEnabled()`
  (`support/indicators/ui/list_model.py`), which emits `enabledKeysChanged`
  — wired in `signal_wiring.py` to
  `BackTestPresenter._on_indicator_script_selection_changed()`
  (`backtest_presenter.py`), which delegates to
  `IndicatorCoordinator.on_script_selection_changed()`
  (`coordinators/indicator_coordinator.py`).
- That method **is** the "Dynamic Script Feeder" §2.1 asks for: it diffs
  `enabled_keys` against the running `IndicatorScriptRunner`'s active
  scripts, calls `remove_script(key, card)` for newly-disabled keys and
  `add_script(key, raw_klines)` for newly-enabled ones — `raw_klines` is
  the presenter's own retained `current_raw_klines`
  (`presenter_screen_state.py`, populated by `ChartRenderCoordinator
  .on_data_ready()` after a run finishes) — synchronously on the main
  thread, no worker dispatch, no `RunStaticBacktestCommand` re-run, no
  `CONFIG_DIRTY`.
- `IndicatorManager` (`support/charting/chart_card/indicator_manager.py`)
  already exposes the incremental `set_script_regions`/`set_script_info`/
  `set_script_markers` (+ their `clear_*` counterparts) that
  `IndicatorScriptRunner.add_script()`/`remove_script()` drive — no full
  chart reload anywhere in this path.
- §4's race-safety criterion is satisfied by construction rather than by
  `run_id` fencing: the toggle path runs synchronously against
  already-cached klines with no async gap for a stale callback to land in
  — `BOT-095H`'s fencing machinery exists for the genuinely async paths
  (a real backtest run), which this one deliberately isn't.
- Verified with the real test suite, not assumed from reading code alone:
  `tests/unit/modules/backtesting/ui/coordinators/test_indicator_coordinator.py`
  (7 tests, including
  `test_toggling_a_script_off_removes_it_and_on_adds_it` and
  `test_a_script_enabled_during_equity_mode_starts_hidden`) — all passing.

No implementation work was needed. The only real defect this investigation
found was process, not code: the epic's own front-matter status note
(`Tasks/backlog/BOT-095_backtest_signals_fsm_lifecycle_epic.md`) still
listed this task as open — fixed in the same commit as this note.
