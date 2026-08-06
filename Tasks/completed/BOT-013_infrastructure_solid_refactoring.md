# Nhiệm vụ: Refactor Lớp Infrastructure Chuẩn SOLID & Bổ sung Unit Tests

## 1. Mục tiêu (Objective)
Rà soát và refactor các module trong `src/infrastructure/` (Database Repository, Database Manager, Binance WebSocket & Client) nhằm tuân thủ nguyên lý SOLID (SRP, OCP, DIP), giảm Cyclomatic Complexity và nâng cao testability. Bổ sung Unit Tests tương ứng.

## 2. Các điểm vi phạm SOLID & Giải pháp (Identified Issues & Solutions)

### 🔴 1. Single Responsibility Principle (SRP) & Cyclomatic Complexity trong Repository
- **File vi phạm:** `src/infrastructure/persistence/sqlalchemy_repository.py`
- **Vấn đề:**
  - `save_klines()` gom nhiều trách nhiệm: nhóm MarketData theo symbol, dựng câu lệnh Dialect-specific UPSERT, chia nhỏ chunk 5000 nến, và commit giao dịch.
  - `get_klines()` và `get_database_status()` chứa nhiều dòng chuyển đổi kiểu dữ liệu thủ công giữa SQLAlchemy Model/Row và Domain Entities.
- **Giải pháp:** Tách các private helper methods: `_build_upsert_stmt()`, `_to_market_data_entity()`, `_execute_chunked_upsert()` để hàm chính ngắn gọn và đơn trách nhiệm.

### 🔴 2. Open/Closed Principle (OCP) & Hardcoded Dependency trong Client
- **File vi phạm:** `src/infrastructure/binance/client.py`
- **Vấn đề:** `PythonBinanceClient.__init__` khởi tạo trực tiếp concrete `binance.client.Client` khiến việc Unit Test phải dùng `unittest.mock.patch` sâu vào thư viện bên ngoài.
- **Giải pháp:** Cho phép truyền `client` instance (hoặc factory) qua `__init__` để hỗ trợ Dependency Injection linh hoạt.

### 🔴 3. Single Responsibility Principle (SRP) trong Live Stream Service
- **File vi phạm:** `src/infrastructure/binance/binance_websocket_service.py`
- **Vấn đề:** Phương thức `_run_stream()` chứa luồng xử lý monolithic dài hơn 60 dòng (tạo socket multiplex/single, vòng lặp lắng nghe message, xử lý reconnect delay, parse event data).
- **Giải pháp:** Phân tách thành các hàm con chuyên biệt: `_create_socket()`, `_process_socket_payload()`.

---

## 3. Các bước thực hiện (Action Items)

### 🔨 Phase 1: Refactor Code (Infrastructure Layer)
- [x] Refactor `SQLAlchemyMarketDataRepository`: tách `_group_by_symbol()`, `_build_upsert_stmt()`, `_kline_to_upsert_params()`, `_execute_chunked_upsert()` (cho `save_klines`), `_to_market_data_entity()` (cho `get_klines`), `_parse_db_datetime()` (cho `get_database_status`, loại bỏ ternary lặp lại giữa first_record/last_record).
- [x] Refactor `PythonBinanceClient`: `__init__` nhận thêm `client: Optional[Client] = None` — cho phép inject trực tiếp, mặc định vẫn tự dựng `Client(api_key, api_secret)` như cũ nếu không truyền (không phá vỡ DI container wiring hiện có).
- [x] Refactor `BinanceWebsocketService`: tách `_create_socket()` (chọn kline_socket vs multiplex_socket, sync, dễ test) và `_process_socket_message()` (nhận + giải nén envelope + emit event, async).

### 🧪 Phase 2: Bổ sung Unit Tests
- [x] `tests/unit/infrastructure/persistence/test_sqlalchemy_repository_helpers.py` (mới) — test 5 helper vừa tách, không cần DB thật (nhanh, cô lập). Test chunking/mapping thật (cần DB) đã có sẵn từ trước ở `test_sqlalchemy_repository.py`.
- [x] `tests/unit/infrastructure/binance/test_python_binance_client_unit.py` — thêm test inject client trực tiếp (không cần `patch`), test fallback khi không inject, test lỗi từ client được propagate.
- [x] `tests/unit/infrastructure/binance/test_binance_websocket_service.py` — thêm test `_create_socket` (1 symbol vs nhiều symbol) và `_process_socket_message` (message rỗng, event không phải kline, giải nén envelope multiplex).
- [x] Chạy `pytest` đảm bảo toàn bộ test suite pass 100%.

---

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Không thay đổi hành vi ghi WAL Mode SQLite và cơ chế SQLite UPSERT hiện tại.

## 5. Ghi chú hoàn thành (Completion Notes)

- Tất cả 3 vi phạm đã refactor theo đúng giải pháp đề xuất trong task — không có sai khác/hoãn mục nào ở phase này (khác với BOT-007/BOT-010 trước đó).
- `PythonBinanceClient`: tham số mới `client` đặt cuối cùng, có default `None`, nên **không** cần đổi bất kỳ call site nào (`binance_bot_module.py` DI container vẫn resolve như cũ).
- Verify: `scripts/ci-local.ps1` (ruff lint, ruff format, 149 tests, coverage 88.60%) pass. Toàn bộ test cũ (bao gồm `test_websocket_auto_reconnect` end-to-end qua `_run_stream`) vẫn pass nguyên vẹn sau khi tách hàm — hành vi bên ngoài không đổi.
