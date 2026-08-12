---
id: "BOT-012"
title: "Nhiệm vụ: Refactor Lớp Application Chuẩn SOLID & Loại bỏ Primitive Obsession"
status: "completed"
---

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
- [x] Refactor `BulkSyncMarketDataCommandHandler` sử dụng `IDispatcher` (thay vì `sync_handler: SyncMarketDataCommandHandler`) — xem Ghi chú hoàn thành cho lý do chọn `IDispatcher` thay vì `ICommandHandler[...]`.
- [x] Chuẩn hóa kiểu trả về của `GetDatabaseStatusQueryHandler` từ `dict` sang `DatabaseStatusDTO`.
- [x] Cập nhật phương thức `get_database_status` trong `IMarketDataRepository` trả về kiểu có type (không còn `dict` thô) — xem Ghi chú hoàn thành.

### 🧪 Phase 2: Bổ sung Unit Tests
- [x] Viết Unit Test `tests/unit/application/use_cases/test_bulk_sync_market_data.py` kiểm thử `BulkSyncMarketDataCommandHandler` với mock `dispatcher`.
- [x] Viết/Cập nhật Unit Test `tests/unit/application/use_cases/test_get_database_status.py` kiểm tra kiểu dữ liệu DTO trả về.
- [x] Cập nhật `tests/unit/application/use_cases/test_scan_all_databases.py` để mock repo trả về `DatabaseStatusSnapshot` thay vì dict.
- [x] Thêm 2 Integration Test mới trong `test_sqlalchemy_repository.py` (`get_database_status` — empty DB & gap detection) — phương thức này trước đó chưa hề được test trực tiếp.
- [x] Thêm Unit Test mới `test_on_check_status_emits_dto_fields` cho `DataManagementPresenter` — trước đó `_on_check_status` cũng chưa có test riêng.
- [x] Chạy `pytest` đảm bảo toàn bộ 106 test cases trôi chảy 100%.

---

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đảm bảo không làm gãy giao diện `DataManagementPresenter` khi đổi kiểu dữ liệu trả về từ `dict` sang `DatabaseStatusDTO`.

## 5. Ghi chú hoàn thành (Completion Notes)

**Vi phạm #1 (DIP):** Dùng `IDispatcher` thay vì `ICommandHandler[SyncMarketDataCommand, None]` như đề xuất ban đầu (task đã nêu đây là 1 trong 2 lựa chọn hợp lệ). Lý do: `ICommandHandler` là một `Protocol` generic — dùng dạng đã tham số hóa (`ICommandHandler[SyncMarketDataCommand, None]`) làm khóa binding cho DI container tự resolve theo type-hint là mong manh (generic alias, không phải kiểu cụ thể có thể tự construct). `IDispatcher` đã được framework bind sẵn toàn cục và đã là pattern chuẩn cả `DashboardPresenter` lẫn `DataManagementPresenter` đang dùng — dùng đúng convention có sẵn thay vì tạo cách mới.

**Vi phạm #2 (Primitive Obsession):** Port `IMarketDataRepository.get_database_status()` trả về **`DatabaseStatusSnapshot`** (dataclass mới, field kiểu gốc: `datetime`/`int`) — **không phải** `DatabaseStatusDTO` (dataclass hiển thị, field kiểu `str` đã format sẵn "OK"/"N gaps found!") như câu chữ gốc của task đề xuất. Lý do: nếu để tầng Infrastructure (`SQLAlchemyMarketDataRepository`) tự sinh chuỗi hiển thị, sẽ trộn lẫn trách nhiệm format/hiển thị vào tầng hạ tầng — vi phạm Clean Architecture theo hướng khác. Thay vào đó, `DatabaseStatusDTO.from_snapshot()` (factory classmethod) là nguồn xử lý format DUY NHẤT, dùng chung bởi cả `GetDatabaseStatusQueryHandler` và `ScanAllDatabasesQueryHandler` — đúng tinh thần "đảm bảo tính nhất quán dữ liệu" mà không cần 2 nơi tự viết logic "OK"/"N gaps found!" riêng biệt (trước đây `ScanAllDatabasesQueryHandler` và `DataManagementPresenter._on_check_status` đều tự làm việc này, trùng lặp).

Verify: `scripts/ci-local.ps1` (ruff lint, ruff format, 106 tests) pass.
