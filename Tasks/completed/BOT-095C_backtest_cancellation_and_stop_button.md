# Nhiệm vụ: BOT-095C — Nút Hủy / Dừng Backtest & Thanh Tiến độ Tính toán Realtime (`CancellationToken` & Progress ETA)

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> Phụ thuộc: `BOT-095B` ✅ và [`BOT-095H`](BOT-095H_backtest_action_ownership_and_stale_callback_fencing.md).
> **Trọng tâm**: Tích hợp cơ chế hủy an toàn (`CancellationToken`) cùng thanh tiến độ tính toán nến thời gian thực (% và thời gian ước tính còn lại ETA) vào chuỗi xử lý Static Backtest, kết hợp nút Hủy (Danger Red) trên giao diện người dùng.

> **Hoàn thành 2026-08-17**: `BacktestCancelled` là outcome Application riêng, không phải `BacktestResult` dở dang. Presenter sở hữu `CancellationToken` của Engine và truyền `cancellation_requested: Callable[[], bool]` vào command để Application không phụ thuộc Engine. Cancellation được kiểm tra trên in-sample, out-of-sample và full pass; progress phát theo phase boundary/cadence 16 bars qua Qt signal có `action_id`. Full CI: 891 primary + 24 sanity passed, coverage 94.14%.

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
   cancellation_requested: Callable[[], bool] | None = None
   progress_callback: Callable[[str, int, int, float], None] | None = None
   # phase, processed_bars, total_bars, elapsed_seconds
   ```
   `CancellationToken` vẫn được tạo và sở hữu tại Presenter; command chỉ
   nhận protocol tối thiểu cần thiết để giữ Application độc lập với Engine.
2. Trong vòng lặp nến của `RunStaticBacktestCommandHandler.execute()`:
   - Kiểm tra token theo cadence được benchmark (không mặc định 1,000 nến) trên **mọi** pass: full range, in-sample và out-of-sample.
     - Nếu bị hủy $\rightarrow$ dừng hợp tác, giải phóng tài nguyên và trả về một cancellation outcome tường minh. Không tự thêm `cancelled=True` vào `BacktestResult` nếu domain object chưa có contract đó.
     - Nếu có `progress_callback` $\rightarrow$ Gọi callback để thông báo số nến đã xử lý.

### 2.2. Xử lý Signal & FSM Transition trong `BackTestPresenter`
1. Thêm signal `cancelBacktestRequested` và `backtestProgressUpdated = Signal(int, int, float, str)` vào `BackTestViewModel`.
2. Trong `BackTestPresenter`:
   - Khi bấm "Chạy Backtest":
     - Tạo `self._cancellation_token = CancellationToken()`.
     - Định nghĩa callback cập nhật tiến độ (tính toán ETA: $\text{time\_remaining} = \frac{\text{elapsed}}{\text{progress}} - \text{elapsed}$).
   - Phát qua Qt Signal lên Main Thread để cập nhật UI an toàn (tuân thủ Thread-Affinity), kèm `action_id` của `BOT-095H`; slot bỏ qua progress/callback không còn thuộc action active.
   - Khi nhận signal `cancelBacktestRequested`:
     - Dispatch event `self.fsm.dispatch(BacktestUiEvent.CANCEL_REQUESTED)` $\rightarrow$ FSM chuyển sang `CANCELLING`.
     - Gọi `self._cancellation_token.cancel()`.
     - Log: `"Đang hủy tính toán Backtest..."`.
   - Khi luồng nền kết thúc do hủy:
     - Dispatch event `self.fsm.dispatch(BacktestUiEvent.BACKTEST_CANCELLED)` về **pre-run state** đã lưu (ví dụ `CONFIG_DIRTY` nếu đang giữ kết quả cũ), không luôn ép về `IDLE`.

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
   - Cancel idempotent: success/failure đến sau cancel không được render kết quả hoặc gây illegal transition.
   - FSM chuyển `RUNNING` $\rightarrow$ `CANCELLING` $\rightarrow$ pre-run state phù hợp.
2. **Tiến độ mượt mà**:
   - Progress được throttle/coalesce trên UI thread; ETA chỉ hiển thị sau mẫu đủ ổn định và ghi rõ là ước tính.
3. **Zero Resource Leak**:
   - Không bị rò rỉ SQLite connection handles (`ResourceWarning`).
4. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -Full` đạt Passed (lint, format, primary
     tests và sanity); `-UnitOnly` chỉ dùng để chẩn đoán nhanh.

5. **Race verification**:
   - Test `success-after-cancel`, `failure-after-cancel` và cancel trong out-of-sample pass. Ngưỡng latency phải được benchmark trên fixture có số nến công bố thay vì SLA tuyệt đối.
