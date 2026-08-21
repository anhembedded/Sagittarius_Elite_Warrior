# BUG-023 — App đóng giao diện nhưng tiến trình Python và Database Sync không thoát (Zombie / Hanging Process)

**Reported:** 2026-08-20  
**Severity:** 🔴 **P1 (Hanging Process / Unclosed SQLite File Locks)**  
**Status:** ✅ **Fixed 2026-08-21 (root-caused / reproduced / regression-tested / verified)**  

---

## 1. Triệu Chứng (Symptom)

Khi đóng cửa sổ ứng dụng (hoặc gọi lệnh dừng App) trong lúc tiến trình đồng bộ dữ liệu thị trường (Database Sync / Bulk Sync / Historical KLines Fetch / Gap Repair) đang chạy ngầm:
* Log hiển thị toàn bộ chu trình dừng engine bình thường:
  ```text
  2026-08-20 22:14:48,176 - App - INFO - App is stopping gracefully...
  2026-08-20 22:14:48,177 - App - INFO - Scheduler stopped.
  2026-08-20 22:14:48,177 - App - INFO - Stopping Hosted Service 'LiveStreamEngineAdapter'...
  2026-08-20 22:14:48,177 - App.LiveStreamAdapter - INFO - Engine shutting down, ensuring stream is stopped...
  2026-08-20 22:14:48,177 - App.LiveStream - WARNING - Stream is not running.
  2026-08-20 22:14:48,178 - App - INFO - Stopping extension 'HealthExtension'...
  2026-08-20 22:14:48,178 - App - INFO - Disposing extension 'HealthExtension'...
  2026-08-20 22:14:48,178 - App - INFO - Stopping extension 'BinanceBotModule'...
  2026-08-20 22:14:48,197 - App - INFO - Disposing extension 'BinanceBotModule'...
  2026-08-20 22:14:48,197 - App - INFO - Stopping extension 'ThreadManagerExtension'...
  2026-08-20 22:14:48,198 - App - INFO - Disposing extension 'ThreadManagerExtension'...
  2026-08-20 22:14:48,198 - App - INFO - Stopping extension 'LoggerExtension'...
  2026-08-20 22:14:48,198 - App - INFO - Disposing extension 'LoggerExtension'...
  2026-08-20 22:14:48,198 - App - INFO - Stopping extension 'AssetValidatorExtension'...
  2026-08-20 22:14:48,198 - App - INFO - Disposing extension 'AssetValidatorExtension'...
  2026-08-20 22:14:48,198 - App - INFO - Stopping extension 'DependencyValidatorExtension'...
  2026-08-20 22:14:48,199 - App - INFO - Disposing extension 'DependencyValidatorExtension'...
  2026-08-20 22:14:48,199 - App - INFO - Stopping AsyncRuntime event loop...
  2026-08-20 22:14:48,200 - App - INFO - AsyncRuntime event loop stopped.
  2026-08-20 22:14:48,200 - App - INFO - App stopped.
  ```
* **Hậu quả**:
  1. Tiến trình `python.exe` không tự động kết thúc mà tiếp tục chạy ngầm vô hạn (Zombie Process).
  2. Các file cơ sở dữ liệu SQLite shard (`database/*.db`, `*.db-wal`, `*.db-shm`) bị khóa vĩnh viễn (`The process cannot access the file because it is being used by another process`), chặn mọi thao tác build native chart, xóa thư mục hoặc mở phiên app mới.

---

## 2. Nguyên Nhân Gốc Rễ (Root Cause)

1. **`DataManagementPresenter` và `DashboardPresenter` thiếu hook `shutdown()` và không cancel `_cancellation_token`**:
   - Khi `MainWindow.closeEvent()` kích hoạt `PresenterManager.shutdown()`, `DataManagementPresenter` và `DashboardPresenter` không cài đặt phương thức `shutdown()`. Do đó, bất kỳ tác vụ đồng bộ (`_trigger_single_sync`, `_run_bulk_sync`, `_on_repair_gap`, `_on_repair_all_gaps`) đang chạy trong worker thread không hề nhận tín hiệu cancel.
   - Thêm vào đó, `_on_repair_gap` và `_on_repair_all_gaps` hoàn toàn không khởi tạo hoặc truyền `CancellationToken` tới `RepairDataGapCommand`.
2. **`ThreadSafeRateLimiter.acquire()` sleep cứng và không hỗ trợ ngắt**:
   - Khi rate limiter thực hiện `time.sleep()`, nó chặn worker thread mà không kiểm tra cờ hủy `cancellation_requested()`.
3. **`BulkSyncMarketDataCommandHandler` không cancel pending executor futures**:
   - Khi một worker thread bị cancel, các task khác trong ThreadPool vẫn xếp hàng thực thi mà không được cancel sớm.
4. **`RepairDataGapCommandHandler` truyền sai tên tham số tới `IExchangeClient`**:
   - Gọi `exchange_client.get_historical_klines(..., start_time=..., end_time=...)` thay vì `start_str` / `end_str` theo contract của `IExchangeClient`.
5. **`DatabaseManager.dispose_all()` không giải phóng cache session makers**:
   - Không reset `self._sessions` sau khi dispose engine.

---

## 3. Giải Pháp Khắc Phục (Fix)

1. **`DataManagementPresenter` & `DashboardPresenter` Lifecycle Management**:
   - Bổ sung `shutdown()` vào `DataManagementPresenter`: hủy `self._cancellation_token`, đặt `self._shutdown_requested = True`, và chặn mọi submit worker mới khi đang shutdown.
   - Bổ sung `shutdown()` vào `DashboardPresenter`: hủy `self._cancellation_token`, tắt `_autostart_controller`, và chặn tác vụ sau khi đóng.
   - Kết nối `CancellationToken` trong `_on_repair_gap` và `_on_repair_all_gaps`, truyền `cancellation_requested=token.is_cancelled` vào `RepairDataGapCommand`.
2. **Cooperative Cancellation trong Rate Limiter**:
   - Cập nhật `ThreadSafeRateLimiter.acquire(cancellation_requested=...)` phân mảnh thời gian sleep thành các bước 50ms và ngắt ngay lập tức khi nhận cờ hủy.
3. **Bulk Sync Cancellation Propagation**:
   - Trong `BulkSyncMarketDataCommandHandler._run_bulk_sync`, truyền `cancellation_requested` vào `rate_limiter.acquire()` và gọi `future.cancel()` trên tất cả futures đang chờ khi phát hiện cancellation. Xử lý an toàn `concurrent.futures.CancelledError`.
4. **Sửa Interface Contract Call**:
   - Sửa `RepairDataGapCommandHandler` để truyền `start_str=command.start_time, end_str=command.end_time` khớp 100% với `IExchangeClient`.
5. **Database Shard Cleanup**:
   - Cập nhật `DatabaseManager.dispose_all()` để dọn dẹp toàn bộ `self._sessions` song song với `engine.dispose()`.

---

## 4. Regression Tests & Verification Evidence

1. **Unit Regression Tests**:
   - `tests/unit/presentation/ui/screens/test_data_management_presenter.py`:
     - `test_presenter_shutdown_cancels_inflight_sync_token_idempotently`: Kiểm tra gọi `shutdown()` hủy token và idempotent.
     - `test_presenter_shutdown_prevents_subsequent_worker_submissions`: Kiểm tra không cho phép submit worker sau khi shutdown.
     - `test_repair_gap_wires_cancellation_token`: Kiểm tra `_on_repair_gap` tạo và gắn `CancellationToken`.
   - `tests/unit/presentation/ui/screens/test_dashboard_presenter.py`:
     - `test_presenter_shutdown_cancels_cancellation_token_and_shuts_down_autostart`: Kiểm tra presenter shutdown hủy token và controller.
   - `tests/unit/application/services/test_rate_limiter.py`:
     - `test_rate_limiter_acquire_aborts_on_cancellation`: Kiểm tra rate limiter ngắt sleep ngay khi nhận tín hiệu hủy.
2. **Process-Level Integration Regression Test**:
   - `scripts/shutdown_database_sync_probe.py` + `tests/integration/presentation/test_shutdown_database_sync_process.py`:
     - Chạy tiến trình thực tế trên 3 chế độ: `single_sync`, `bulk_sync`, và `repair_gap`. Cả 3 trường hợp thoát sạch < 7.05s với exit code 0.
3. **Full CI Suite Verification**:
   - `./scripts/ci-local.ps1 -Full` chạy toàn bộ Native Build, Chart Benchmark Contract, Ruff Lint, Ruff Format, Mypy static analysis, 1,691 primary tests, 50 sanity tests, 93.65% code coverage, và log scan -> **100% PASSED, 0 WARNINGS/ERRORS**.

