# UI Optimizations Task

## 1. Đổi QWidget thành QFrame cho các Card
Hiện tại `ControlCard` và `MonitorCard` đang kế thừa từ `QWidget`. Mặc dù chạy không lỗi, nhưng để làm giao diện kiểu "Thẻ" (Card) có bo góc (border-radius), có viền (border), hoặc đổ bóng (box-shadow) thì `QWidget` cơ bản hỗ trợ rất kém.
Cần đổi class cha của chúng sang `QFrame` (giống như `chart_frame` trong `dashboard_view.py`).

## 2. Tổ chức Layout ở DashboardView
Trong `dashboard_view.py`, hiện đang dùng `QHBoxLayout` làm layout chính, chia `chart_frame` chiếm 3 phần (stretch=3) và cột bên phải chiếm 1 phần (stretch=1). Cách chia tỷ lệ này khá ổn cho màn hình ngang, nhưng cân nhắc dùng `QGridLayout` nếu sau này muốn nhét thêm các Sub-card (như thẻ hiển thị PnL, thẻ lịch sử lệnh) vào bên dưới.

## 3. Lắp ráp Presenter vào MainWindow
Cần khởi tạo `DashboardPresenter` trong `main_window.py` và truyền `app` (sagittarius_engine) vào `MainWindow` để khởi tạo Presenter (hoàn thiện mô hình MVP).
