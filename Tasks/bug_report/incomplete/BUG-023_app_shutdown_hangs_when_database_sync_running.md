# BUG-023 — App đóng giao diện nhưng tiến trình Python và Database Sync không thoát (Zombie / Hanging Process)

**Reported:** 2026-08-20  
**Severity:** 🔴 **P1 (Hanging Process / Unclosed SQLite File Locks)**  
**Status:** 🔴 **Open (Đang mở - Đã ghi nhận log & khoanh vùng cơ chế)**  

---

## 1. Triệu Chứng (Symptom)

Khi đóng cửa sổ ứng dụng (hoặc gọi lệnh dừng App) trong lúc tiến trình đồng bộ dữ liệu thị trường (Database Sync / Bulk Sync / Historical KLines Fetch) đang chạy ngầm:
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

## 2. Phân Tích Cơ Chế Gốc Rễ (Root Cause Hypothesis)

1. **Worker Threads Non-Daemon & Thiếu Cooperative Cancellation**:
   * Khi gọi `IThreadManager.submit(...)` để chạy tải nến hoặc sync dữ liệu, các worker thread chạy trong `ThreadPoolExecutor` không nhận cờ hủy (cancellation token / abort flag) khi `App.stop()` được gọi.
   * `ThreadManagerExtension.dispose()` hoặc Python runtime lúc thoát (`sys.exit()`) phải đợi tất cả các non-daemon threads kết thúc trước khi hủy tiến trình, dẫn đến việc ứng dụng bị treo nếu thread đang kẹt trong vòng lặp mạng `BinanceClient.get_historical_klines` hoặc phân trang lớn.
2. **Database Session & Connection Pool Không Được Dispose Triệt Để**:
   * `DatabaseManager` / `SqliteMarketDataRepository` lưu trữ các SQLAlchemy `Engine` và `SessionMaker` theo từng shard.
   * Khi `BinanceBotModule` bị `dispose()`, repository không gọi `engine.dispose()` trên tất cả các shard đang mở, khiến file handle SQLite WAL vẫn bị giữ mở trong bộ nhớ.

---

## 3. Các Bước Đề Xuất Khắc Phục (Suggested Next Steps)

1. **Bổ Sung Cooperative Cancellation Vào Use Case Sync**:
   * Thêm kiểm tra `cancellation_token` hoặc cờ `app_stopping` trong các vòng lặp phân trang của `SyncMarketDataCommandHandler`, `BulkSyncMarketDataCommandHandler`, và `RepairDataGapCommandHandler`.
2. **Đóng Engine & Shard Connections Khi Teardown**:
   * Bổ sung phương thức `dispose()` vào `DatabaseManager` / `SqliteMarketDataRepository` để đóng toàn bộ kết nối và gọi `Engine.dispose()` cho tất cả các shard DB đang hoạt động.
3. **Cấu Hình Daemon / Graceful Shutdown Cho `ThreadManager`**:
   * Đảm bảo `ThreadManager` phát tín hiệu ngắt (interrupt/cancel) tới các background worker khi ứng dụng nhận tín hiệu thoát.
4. **Viết Regression Test**:
   * Viết test kiểm tra: Khi kích hoạt sync ngầm và ngay lập tức gọi `app.stop()`, tiến trình và `ThreadManager` phải hủy worker thành công trong vòng < 500ms mà không để lại thread treo.
