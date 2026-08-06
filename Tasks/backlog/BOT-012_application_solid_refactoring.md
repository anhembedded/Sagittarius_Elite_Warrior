# Nhiệm vụ: Refactor Lớp Application Chuẩn SOLID & Loại bỏ Primitive Obsession

## 1. Mục tiêu (Objective)
Rà soát và refactor các file trong `src/application/` vi phạm nguyên lý SOLID (DIP, ISP, Primitive Obsession). Viết bổ sung đầy đủ Unit Tests kiểm thử độc lập cho từng Handler và Port được refactor.

## 2. Các điểm vi phạm SOLID & Giải pháp (Identified Issues & Solutions)

### 🔴 1. Dependency Inversion Principle (DIP) Violation
- **File vi phạm:** `src/application/use_cases/sync/bulk_sync_market_data/handler.py`
- **Vấn đề:** `BulkSyncMarketDataCommandHandler.__init__` inject trực tiếp conrete class `sync_handler: SyncMarketDataCommandHandler` thay vì phụ thuộc vào Abstraction (`ICommandHandler[SyncMarketDataCommand, None]` hoặc `IDispatcher`).
- **Giải pháp:** Đổi kiểu dependency sang `ICommandHandler[SyncMarketDataCommand, None]`.

### 🔴 2. Primitive Obsession & Interface Segregation (ISP / Type Safety)
- **File vi phạm:** `src/application/use_cases/queries/get_database_status/handler.py` & `src/application/ports/i_market_data_repository.py`
- **Vấn đề:** 
  - `GetDatabaseStatusQueryHandler` trả về kiểu dữ liệu thô `Dict[str, Any]` thay vì `DatabaseStatusDTO`.
  - `IMarketDataRepository.get_database_status()` khai báo kiểu trả về `dict`.
- **Giải pháp:**
  - Chuẩn hóa kiểu trả về của `get_database_status` sang `DatabaseStatusDTO`.
  - Đảm bảo tính nhất quán dữ liệu giữa `GetDatabaseStatusQueryHandler` và `ScanAllDatabasesQueryHandler`.

---

## 3. Các bước thực hiện (Action Items)

### 🔨 Phase 1: Refactor Code (Application Layer)
- [ ] Refactor `BulkSyncMarketDataCommandHandler` sử dụng interface `ICommandHandler` cho `sync_handler`.
- [ ] Chuẩn hóa kiểu trả về của `GetDatabaseStatusQueryHandler` từ `dict` sang `DatabaseStatusDTO`.
- [ ] Cập nhật phương thức `get_database_status` trong `IMarketDataRepository` trả về `DatabaseStatusDTO`.

### 🧪 Phase 2: Bổ sung Unit Tests
- [ ] Viết Unit Test `tests/unit/application/use_cases/test_bulk_sync_market_data.py` kiểm thử `BulkSyncMarketDataCommandHandler` với mock `sync_handler`.
- [ ] Viết/Cập nhật Unit Test `tests/unit/application/use_cases/test_get_database_status.py` kiểm tra kiểu dữ liệu DTO trả về.
- [ ] Chạy `pytest` đảm bảo toàn bộ 92+ test cases trôi chảy 100%.

---

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đảm bảo không làm gãy giao diện `DataManagementPresenter` khi đổi kiểu dữ liệu trả về từ `dict` sang `DatabaseStatusDTO`.
