---
id: "BOT-007"
title: "Nhiệm vụ: Tối ưu hóa UI Theme, Card Components & Layout Config"
status: "completed"
---

# Nhiệm vụ: Tối ưu hóa UI Theme, Card Components & Layout Config

## 1. Mục tiêu (Objective)
- Đưa các thông số cấu hình giao diện (Font family, Font size, Fallback fonts, Bảng màu Binance Yellow, Material Blue) ra file `user_config.json`.
- Chuyển toàn bộ các Card UI (`ControlCard`, `MonitorCard`) kế thừa từ `QFrame` thay vì `QWidget` để hỗ trợ bo góc (border-radius) và viền (border) chuẩn CSS.
- Tối ưu hóa layout `DashboardView` và hoàn thiện ghép nối Presenter theo chuẩn MVP.

## 2. Mô tả (Description)
Tập hợp các cải tiến UI giúp giao diện chuyên nghiệp hơn, tùy biến màu sắc linh hoạt mà không cần sửa code Python, đồng thời chuẩn hóa cấu trúc component.

## 3. Các bước thực hiện (Action Items)
- [x] **Đổi QWidget thành QFrame cho các Card:** `ControlCard`/`MonitorCard` đã kế thừa `BaseCard` (là `QFrame`) từ một đợt refactor trước đó — không còn `QWidget` trực tiếp.
- [x] **Cấu hình UI linh hoạt:** `user_config.json` đã có `ui.font.family`, `ui.font.size`, `ui.font.fallbacks`, `ui.theme.accent_color`, `ui.theme.replace_color`; được đọc qua `ConfigKeys` trong `app_bootstrapper.py::_apply_font()`/`_apply_theme()`.
- [~] **Tái cấu trúc Layout DashboardView:** *Bỏ qua có chủ đích* — xem Ghi chú hoàn thành.
- [x] **Lắp ráp Presenter chuẩn MVP:** `DashboardPresenter` đã được đăng ký qua `PresenterManager`/`RouterManager` trong `main_window.py::_setup_router()`, nhận `container` của engine lazy khi navigate tới màn hình.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đảm bảo fallback font hợp lý nếu hệ thống thiếu `JetBrainsMono Nerd Font`.

## 5. Ghi chú hoàn thành (Completion Notes)
- Khi rà soát lại, 3/4 mục đã được hoàn thành từ một đợt refactor UI trước đó (task doc này bị lỗi thời, chưa cập nhật theo).
- **Mục "Chuyển sang QGridLayout" bị hoãn có chủ đích**: lý do ban đầu là "để dễ chèn sub-card (PnL summary, Order History)", nhưng các sub-card đó chưa tồn tại trong code. Đổi layout ngay bây giờ sẽ là đoán trước hình dạng grid mà không có gì để kiểm chứng — rủi ro đoán sai rồi phải sửa lại khi sub-card thật xuất hiện. Sẽ làm khi PnL/Order History card được đặc tả cụ thể.
- Verify: `scripts/ci-local.ps1` pass (không có thay đổi code, chỉ audit lại trạng thái).
