# Nhiệm vụ: Tối ưu hóa UI Theme, Card Components & Layout Config

## 1. Mục tiêu (Objective)
- Đưa các thông số cấu hình giao diện (Font family, Font size, Fallback fonts, Bảng màu Binance Yellow, Material Blue) ra file `user_config.json`.
- Chuyển toàn bộ các Card UI (`ControlCard`, `MonitorCard`) kế thừa từ `QFrame` thay vì `QWidget` để hỗ trợ bo góc (border-radius) và viền (border) chuẩn CSS.
- Tối ưu hóa layout `DashboardView` và hoàn thiện ghép nối Presenter theo chuẩn MVP.

## 2. Mô tả (Description)
Tập hợp các cải tiến UI giúp giao diện chuyên nghiệp hơn, tùy biến màu sắc linh hoạt mà không cần sửa code Python, đồng thời chuẩn hóa cấu trúc component.

## 3. Các bước thực hiện (Action Items)
- [ ] **Đổi QWidget thành QFrame cho các Card:** Chuyển class cha của `ControlCard` và `MonitorCard` từ `QWidget` sang `QFrame` (hoặc kế thừa `BaseCard`) để hỗ trợ QSS styling tốt hơn.
- [ ] **Cấu hình UI linh hoạt:** Bổ sung section `ui` trong `src/config/user_config.json` chứa: `font_family`, `font_size`, `colors.primary`, `colors.accent`.
- [ ] **Tái cấu trúc Layout DashboardView:** Chuyển từ `QHBoxLayout` cứng sang `QGridLayout` linh hoạt hơn khi cần chèn thêm các Sub-card (PnL summary, Order History) bên dưới.
- [ ] **Lắp ráp Presenter chuẩn MVP:** Khởi tạo `DashboardPresenter` trong `app_bootstrapper.py` / `main_window.py` và truyền `container` của engine vào MainWindow.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đảm bảo fallback font hợp lý nếu hệ thống thiếu `JetBrainsMono Nerd Font`.
