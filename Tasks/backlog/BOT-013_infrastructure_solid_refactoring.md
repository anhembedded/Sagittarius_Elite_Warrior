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
- [ ] Refactor `SQLAlchemyMarketDataRepository`: Tách helper map entity & build UPSERT statement.
- [ ] Refactor `PythonBinanceClient`: Hỗ trợ DI client instance.
- [ ] Refactor `BinanceWebsocketService`: Phân tách hàm `_run_stream()` thành các sub-methods chuyên biệt.

### 🧪 Phase 2: Bổ sung Unit Tests
- [ ] Bổ sung Unit Test `tests/unit/infrastructure/persistence/test_sqlalchemy_repository.py` test chunking & mapping entity.
- [ ] Bổ sung Unit Test `tests/unit/infrastructure/binance/test_python_binance_client.py` test DI client & error handling.
- [ ] Bổ sung Unit Test `tests/unit/infrastructure/binance/test_binance_websocket_service.py` test mock payload parsing.
- [ ] Chạy `pytest` đảm bảo toàn bộ test suite pass 100%.

---

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Không thay đổi hành vi ghi WAL Mode SQLite và cơ chế SQLite UPSERT hiện tại.
