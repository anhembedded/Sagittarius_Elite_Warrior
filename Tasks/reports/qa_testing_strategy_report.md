# 🛡️ Báo cáo Đánh giá & Chuẩn hóa Quy trình Quản lý Chất lượng (QA & Testing Strategy Audit Report)

> [!NOTE]
> **Báo cáo phân tích chuyên sâu thuộc Task BOT-015.**  
> Tài liệu này tổng hợp đánh giá hiện trạng bộ test suite, xác định các khe hở chất lượng (Quality Gaps), và đề xuất mô hình kim tự tháp kiểm thử chuẩn hóa cho dự án **Binance Bot**.

---

## 1. 📊 Tổng quan Hiện trạng Test Suite (Executive Summary)

Dự án hiện bao gồm **2 bộ test suite chính** chạy qua script `ci-local.ps1`:

| Phân vùng Codebase | Số lượng Test Cases | Trạng thái Chạy | Tỷ lệ Pass |
| :--- | :---: | :---: | :---: |
| **Sagittarius Engine** (`sagittarius_engine/`) | 385 | ✅ Passed | 100% (6 Skipped) |
| **Binance Bot App** (`Binace_Bot/`) | 92 | ✅ Passed | 100% |
| **Tổng cộng toàn bộ hệ thống** | **477** | **✅ PASSED** | **100%** |

### 📈 Phân bố Kim tự tháp Kiểm thử Hiện tại:
- **Unit Tests (`tests/unit/`)**: ~68% (CQRS Handlers, Presenters, Entities, Value Objects).
- **Integration Tests (`tests/integration/`)**: ~22% (SQLite Sharding Repository, Binance Client, Live Stream).
- **UI & Entry Point Tests (`tests/integration/presentation/ui/`)**: ~10% (PySide6 Navigation, Charting, E2E Boot).

---

## 2. 🔍 Đánh giá các Khe hở Chất lượng & Rủi ro (Quality Gaps & Risk Audit)

### 🔴 1. Thiếu Tầng Kiểm thử Tĩnh Entry Point (Static Import / Sanity Gap)
- **Vấn đề phát hiện:** Lỗi `ImportError: cannot import name 'main' from 'app_bootstrapper'` khi người dùng thực thi trực tiếp `python main_window.py` dưới dạng `__main__`.
- **Nguyên nhân:** Bộ test UI cũ (`test_sanity_ui_e2e.py`) chỉ import `MainWindow` như một thư viện Python thông thường trong môi trường pytest, nên không kích hoạt được nhánh execution `if __name__ == "__main__":`.
- **Rủi ro:** Các lỗi Circular Import tĩnh chỉ xảy ra khi chạy ứng dụng trực tiếp nhưng qua mặt được pytest.

### 🔴 2. Quản lý Vòng đời Qt Objects trong UI Tests (Qt Memory Leak & Isolation Risk)
- **Vấn đề phát hiện:** Một số UI test case tạo ra các QWidget/QFrame (`DashboardView`, `ControlCard`) nhưng không gọi `deleteLater()` hoặc không được dọn dẹp triệt để qua `qtbot.addWidget()`.
- **Rủi ro:** Các C++ Qt Object nằm lại trong bộ nhớ có thể can thiệp vào các signal/slot của các test case tiếp theo, gây ra lỗi ẩn hoặc làm sai lệch kết quả test ngẫu nhiên khi chạy trên môi trường CI headless.

### 🔴 3. Giả lập Luồng Bất đồng bộ (Threading Mocking Consistency)
- **Vấn đề phát hiện:** `DashboardPresenter` sử dụng `IThreadManager` để đẩy các tác vụ nặng (như `_run_load_history`, `_run_sync_and_start`) sang worker thread. Khi test, ta dùng mock `submit_sync` để chạy đồng bộ.
- **Rủi ro:** Nếu UI Signal được nối theo chế độ `Qt.QueuedConnection` qua các thread thực tế, việc mock đồng bộ `submit_sync` có thể bỏ qua một số lỗi tiềm ẩn về giật/khóa giao diện (UI Freeze/Deadlock).

### 🔴 4. Thiếu Ngưỡng Chặn Tự động Tỷ lệ Bao phủ Mã nguồn (Coverage Enforcement Threshold)
- **Vấn đề phát hiện:** Script `ci-local.ps1` đã cấu hình chạy `pytest` kèm plugin coverage, nhưng chưa thiết lập ngưỡng chặn tự động `--cov-fail-under=80`.
- **Rủi ro:** Lập trình viên có thể vô tình thêm các module mới mà quên bổ sung test case mà CI không cảnh báo.

---

## 3. 🎯 Đề xuất Mô hình Kim tự tháp Kiểm thử Chuẩn hóa (Target Test Pyramid)

Để nâng cao độ tin cậy của toàn bộ ứng dụng, đề xuất cấu trúc lại bộ test suite thành **4 tầng kiểm thử chuẩn hóa**:

```text
       / \
      /   \     Layer 4: UI E2E & Visual Component Tests (PySide6 / qtbot)
     /     \    ----------------------------------------------------------
    /       \   Layer 3: Infrastructure Integration Tests (SQLite / Binance)
   /         \  ----------------------------------------------------------
  /           \ Layer 2: Isolated Unit Tests (CQRS Handlers / Presenters)
 /-------------\----------------------------------------------------------
/               \ Layer 1: Sanity & Static Entry Point Tests (AST Check / Boot)
```

### 📋 Chi tiết trách nhiệm từng tầng:

#### 🟢 **Layer 1: Sanity & Static Entry Point Tests (`tests/sanity/`)**
- **Nhiệm vụ:** Kiểm tra tĩnh mã nguồn và đảm bảo ứng dụng có thể khởi động (Smoke Test) trong < 1 giây.
- **Các test case cần có:**
  - `test_circular_imports.py`: Phân tích AST đảm bảo không có top-level import gây vòng lặp ở `main.py`, `app_bootstrapper.py`, `main_window.py`.
  - `test_di_container_binding_sanity.py`: Khởi tạo `AppBootstrapper` và verify 100% Core Interfaces (`IDispatcher`, `IEventBus`, `IThreadManager`, `IConfig`, `ITaskManager`) đều được bind thành công.

#### 🔵 **Layer 2: Isolated Unit Tests (`tests/unit/`)**
- **Nhiệm vụ:** Kiểm thử logic nghiệp vụ cô lập hoàn toàn.
- **Quy tắc:** 100% I/O (Database, Network, File System, Threads) phải được mock bằng PyTest Fixtures / Mocks.
- **Đối tượng:** CQRS Handlers (`scan_all_databases`, `bulk_sync`), Domain Entities, Value Objects (`Timeframe`), Presenters (`DashboardPresenter`, `DataManagementPresenter`).

#### 🟡 **Layer 3: Infrastructure Integration Tests (`tests/integration/`)**
- **Nhiệm vụ:** Kiểm thử tương tác thực tế giữa các module hạ tầng.
- **Đối tượng:**
  - `test_sqlalchemy_repository.py`: Kiểm thử SQLite Sharding DB thực tế trên đĩa tạm (`tmp_path`) với WAL mode.
  - `test_binance_websocket_service.py`: Kiểm thử vòng đời bật/tắt luồng WebSocket stream với `ITaskManager` thực tế của Engine.

#### 🔴 **Layer 4: UI E2E & Component Tests (`tests/integration/presentation/ui/`)**
- **Nhiệm vụ:** Kiểm thử phản hồi của giao diện người dùng PySide6.
- **Quy tắc:** Bắt buộc đăng ký mọi Widget qua `qtbot.addWidget()`. Kiểm thử luồng FSM (`IDLE` -> `LOCKED` -> `ERROR`) và tín hiệu kết nối giữa Card và Presenter.

---

## 🛠️ 4. Kế hoạch Hành động Kỹ thuật (Actionable Implementation Plan)

### 📌 **Bước 1: Tái cấu trúc Thư mục Tests**
- Tạo mới thư mục `Binace_Bot/tests/sanity/`.
- Di chuyển `test_circular_imports.py` vào `tests/sanity/`.
- Bổ sung `tests/sanity/test_bootstrapper_di_sanity.py`.

### 📌 **Bước 2: Chuẩn hóa Quy tắc Viết Test (Testing Guidelines)**
- Tạo file quy tắc `.agents/rules/testing.md` với các tiêu chuẩn:
  1. *No Silent Swallowing:* Không dùng `try...except Pass` trong test case.
  2. *Strict Qt Cleanup:* Tất cả Widget khởi tạo trong test phải gọi `qtbot.addWidget(widget)`.
  3. *Explicit Assertions:* Mọi test case async/signal phải có `assert_called_with` hoặc `waitUntil`.

### 📌 **Bước 3: Nâng cấp CI/CD Local Script (`ci-local.ps1`)**
- Cập nhật script hỗ trợ các cờ lọc theo tầng:
  - `.\ci-local.ps1 -SanityOnly` (Chạy nhanh Sanity test trong 1 giây).
  - `.\ci-local.ps1 -UnitOnly` (Chạy bộ Unit test).
  - `.\ci-local.ps1 -Full` (Chạy toàn bộ kèm cờ `--cov-fail-under=80`).
