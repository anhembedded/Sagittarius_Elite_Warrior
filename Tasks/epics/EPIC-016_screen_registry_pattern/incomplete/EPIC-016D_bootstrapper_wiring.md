# EPIC-016D — Cập nhật `app_bootstrapper.py`: đăng ký 4 module + wiring `sidebar_factory`

**Thuộc Epic:** [`EPIC-016`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu — phụ thuộc `016B`, `016C`
**Phụ thuộc:** [`EPIC-016B`](EPIC-016B_registry_va_4_module.md), [`EPIC-016C`](EPIC-016C_main_window_decouple.md).

---

## Việc cần làm

1. Trong `app_bootstrapper.py`, tạo 1 `ScreenRegistry`, gọi
   `register_module()` cho 4 `*ScreenModule` (`DashboardScreenModule`,
   `BacktestScreenModule`, `SettingsScreenModule`, `DatabaseScreenModule`)
   **trước khi** dựng `MainWindow`.
2. Cấp `sidebar_factory` cụ thể (dựng `Sidebar` thật từ
   `components/sidebar/sidebar.py`) cho constructor `MainWindow` mới.
3. Đây là **task duy nhất** trong epic này đụng bootstrap thật — chạy app
   thật (theo skill `run`) để xác nhận: nav hiển thị đúng thứ tự cũ, click
   chuyển màn hình đúng, route mặc định vẫn là Dev Board.

## Tiêu chí xong

- App khởi động, hiển thị Sidebar đúng y hệt thứ tự/label/icon trước khi
  có registry (so sánh ảnh chụp màn hình hoặc đối chiếu bằng mắt).
- Click từng mục nav chuyển đúng màn hình.
- `ci-local.ps1 -Full` xanh, log không có `FAILED|ERROR|Traceback`.
- Sau task này, hướng dẫn "thêm màn hình mới 3 bước" ở mục 8 tài liệu
  thiết kế phải đúng thật — thử thêm 1 module giả (không commit) để xác
  nhận không cần sửa `main_window.py`.
