# Nhiệm vụ: Chuyển Dashboard thành Dev Board & Đổi Mặc định 1 Biểu đồ ETHUSDT

## 1. Mục tiêu (Objective)
Cấu hình lại màn hình Dashboard hiện tại thành **Dev Board (Developer Dashboard)** dùng cho phát triển/thử nghiệm, đổi danh sách biểu đồ mặc định từ 2 biểu đồ (`BTCUSDT` + `ETHUSDT`) sang duy nhất 1 biểu đồ `ETHUSDT`.

## 2. Mô tả (Description)
Màn hình Dashboard hiện tại đang đóng vai trò màn hình thử nghiệm giao diện (Dev Board) hỗ trợ lập trình viên kiểm thử tính năng vẽ nến real-time và load lịch sử. Cần đổi tên nhãn trên UI/Sidebar để tránh hiểu nhầm đây là Dashboard chính thức của ứng dụng, đồng thời giảm số lượng chart hiển thị mặc định xuống 1 chart `ETHUSDT`.

## 3. Các bước thực hiện (Action Items)

### 🔨 Phase 1: Refactor UI & Presenter
- [x] Cập nhật `_DEFAULT_SYMBOLS` trong `dashboard_presenter.py` thành `("ETHUSDT",)` (chỉ 1 symbol ETHUSDT mặc định).
- [x] Cập nhật tên nhãn Sidebar từ `"Dashboard"` thành `"Dev Board"` trong `_NAV_ROUTES` (`main_window.py`).
- [x] Cập nhật tiêu đề màn hình Header trong `dashboard_view.py` thành `"Developer Board (Live Testbed)"` — thêm `QLabel` header mới (`lbl_header`, objectName `PanelTitle`) vì trước đó view chưa có header, phải bọc layout gốc trong một `QVBoxLayout` ngoài.

### 🧪 Phase 2: Cập nhật Unit & Integration Tests
- [x] Cập nhật `test_dashboard_live_stream.py`: `len(active_charts) == 1` và key `"ETHUSDT"` thay vì `"BTCUSDT"`.
- [x] Thêm `test_dashboard_view.py` (mới) kiểm tra `lbl_header.text()`.
- [x] Thêm assertion nhãn `"Dev Board"` vào `test_sanity_ui_e2e.py::test_sanity_boot_and_dashboard`.
- [x] Chạy `pytest` đảm bảo toàn bộ bộ test suite trôi chảy.

---

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Kiểm tra các test case E2E đang assert `len(active_charts) == 2` để cập nhật đồng bộ sang 1 chart.

## 5. Ghi chú hoàn thành (Completion Notes)
- Rà soát toàn bộ `tests/` cho các assertion phụ thuộc `_DEFAULT_SYMBOLS`/số lượng chart: chỉ `test_dashboard_live_stream.py` thực sự phụ thuộc (các test khác trong `test_dashboard_presenter.py` gọi `_run_load_history`/`_run_sync_and_start` với symbol list truyền thẳng, không qua default).
- `data_management_view.py` đã có sẵn pattern `QLabel(...).setObjectName("PanelTitle")` — tái dùng đúng convention thay vì tạo style mới.
- Verify: `scripts/ci-local.ps1` (ruff lint, ruff format, 100 tests) pass.
