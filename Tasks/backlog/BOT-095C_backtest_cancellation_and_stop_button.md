# Nhiệm vụ: BOT-095C — Nút Hủy / Dừng Backtest & Thanh Tiến độ Tính toán Realtime (`CancellationToken` & Progress ETA)

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> Phụ thuộc: [`BOT-095B`](BOT-095B_backtest_fsm_and_stale_data_lifecycle.md).
> **Trọng tâm**: Tích hợp cơ chế hủy an toàn (`CancellationToken`) cùng thanh tiến độ tính toán nến thời gian thực (% và thời gian ước tính còn lại ETA) vào chuỗi xử lý Static Backtest, kết hợp nút Hủy (Danger Red) trên giao diện người dùng.

---

## 1. Vấn đề Hiện tại

- Khi chạy Backtest trên tập dữ liệu lớn (ví dụ 1 năm nến `1m` $\approx 500,000$ nến), quá trình tính toán có thể mất từ vài giây đến hàng chục giây.
- Trong suốt thời gian này, UI chỉ hiển thị spinner quay vô định, không có thông tin về % tiến độ hay thời gian còn lại.
- **Không có nút Hủy / Stop**: Nếu người dùng phát hiện chọn nhầm Chiến lược hoặc nhầm Khung thời gian, họ buộc phải chờ toàn bộ vòng lặp nến chạy xong.

---

## 2. Thiết kế Kỹ thuật (Technical Design)

### 2.1. Tích hợp `CancellationToken` & `ProgressCallback` vào Application Layer
Trong `src/application/use_cases/backtest/run_static_backtest/command.py` và `handler.py`:
1. `RunStaticBacktestCommand` bổ sung:
   ```python
   cancellation_token: CancellationToken | None = None
   progress_callback: Callable[[int, int, float], None] | None = None  # (processed_bars, total_bars, percent)
   ```
2. Trong vòng lặp nến của `RunStaticBacktestCommandHandler.execute()`:
   - Cứ sau mỗi $N$ nến (ví dụ mỗi 1000 nến hoặc 1%):
     - Kiểm tra `cancellation_token.is_cancelled()`. Nếu bị hủy $\rightarrow$ Dừng ngay vòng lặp, giải phóng tài nguyên và trả về `BacktestResult(cancelled=True)`.
     - Nếu có `progress_callback` $\rightarrow$ Gọi callback để thông báo số nến đã xử lý.

### 2.2. Xử lý Signal & FSM Transition trong `BackTestPresenter`
1. Thêm signal `cancelBacktestRequested` và `backtestProgressUpdated = Signal(int, int, float, str)` vào `BackTestViewModel`.
2. Trong `BackTestPresenter`:
   - Khi bấm "Chạy Backtest":
     - Tạo `self._cancellation_token = CancellationToken()`.
     - Định nghĩa callback cập nhật tiến độ (tính toán ETA: $\text{time\_remaining} = \frac{\text{elapsed}}{\text{progress}} - \text{elapsed}$).
     - Phát qua Qt Signal lên Main Thread để cập nhật UI an toàn (tuân thủ Thread-Affinity).
   - Khi nhận signal `cancelBacktestRequested`:
     - Dispatch event `self.fsm.dispatch(BacktestUiEvent.CANCEL_REQUESTED)` $\rightarrow$ FSM chuyển sang `CANCELLING`.
     - Gọi `self._cancellation_token.cancel()`.
     - Log: `"Đang hủy tính toán Backtest..."`.
   - Khi luồng nền kết thúc do hủy:
     - Dispatch event `self.fsm.dispatch(BacktestUiEvent.BACKTEST_CANCELLED)` $\rightarrow$ FSM về `IDLE` (hoặc `CONFIG_DIRTY`).

### 2.3. Cập nhật UI trên `BackTestTopPanel.qml`
1. Khi `viewModel.uiMode !== "RUNNING"`:
   - Nút hiển thị màu vàng Gold / Accent: **"Chạy Backtest"** (icon `zap` hoặc `play`).
   - Click $\rightarrow$ `viewModel.runBacktestRequested.emit()`.
2. Khi `viewModel.uiMode === "RUNNING"`:
   - **Thanh Progress Bar & ETA:** Hiển thị thanh tiến độ mượt mà kèm text:
     > *"Đang tính toán: 45% (225,000 / 500,000 nến) — Ước tính còn lại: ~1.8s"*
   - **Nút Hủy (Stop):** Nút đổi thành màu Đỏ cảnh báo (Danger Red): **"Hủy"** (icon `x` hoặc `square`). Enabled = `true`.
   - Click $\rightarrow$ `viewModel.cancelBacktestRequested.emit()`.
3. Khi `viewModel.uiMode === "CANCELLING"`:
   - Nút bị vô hiệu hóa (`enabled: false`), hiển thị text: **"Đang hủy..."** với spinner nhỏ.

---

## 3. Danh sách File Cần Chỉnh sửa & Tạo mới

- ✏️ `src/application/use_cases/backtest/run_static_backtest/command.py`: Thêm `cancellation_token` và `progress_callback`.
- ✏️ `src/application/use_cases/backtest/run_static_backtest/handler.py`: Kiểm tra `token.is_cancelled()` và phát progress định kỳ.
- ✏️ `src/presentation/ui/screens/backtest/backtest_view_model.py`: Thêm `cancelBacktestRequested`, `backtestProgressPercent`, `backtestProgressText`.
- ✏️ `src/presentation/ui/screens/backtest/backtest_presenter.py`: Xử lý hủy an toàn và tính toán ETA.
- ✏️ `src/presentation/ui/screens/backtest/BackTestTopPanel.qml`: Hiển thị thanh progress bar % + ETA và nút Hủy màu đỏ.
- ✏️ `tests/unit/presentation/ui/screens/test_backtest_presenter.py`: Viết test case kiểm tra hủy tác vụ và cập nhật tiến độ.

---

## 4. Tiêu chuẩn Nghiệm thu (Acceptance Criteria)

1. **Ngắt luồng tức thì**:
   - Khi đang chạy backtest dài, bấm nút "Hủy" $\rightarrow$ Tác vụ nền dừng trong vòng $< 100\text{ms}$.
   - FSM chuyển `RUNNING` $\rightarrow$ `CANCELLING` $\rightarrow$ `IDLE`.
2. **Tiến độ mượt mà**:
   - Thanh progress bar cập nhật liên tục từ 0% đến 100% kèm ETA chính xác, không gây giật lag giao diện.
3. **Zero Resource Leak**:
   - Không bị rò rỉ SQLite connection handles (`ResourceWarning`).
4. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -UnitOnly` đạt 100% Passed.
