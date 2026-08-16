# Nhiệm vụ: BOT-095F — Toggle Chỉ báo Tham chiếu Động trên Biểu đồ sau Backtest

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
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
   - Feed tập nến hiện có `_chart_klines` qua script:
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
   - Khi bật một indicator script trong `IndicatorPickerModal` $\rightarrow$ Đường chỉ báo / Subplot xuất hiện ngay trên chart trong vòng $< 50\text{ms}$.
2. **Không chạy lại engine backtest**:
   - `RunStaticBacktestCommand` không bị dispatch lại khi chỉ bật/tắt script tham chiếu.
   - FSM giữ nguyên trạng thái `COMPLETED` (hoặc `IDLE`), không bị đánh dấu là `CONFIG_DIRTY`.
3. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -UnitOnly` đạt 100% Passed.
