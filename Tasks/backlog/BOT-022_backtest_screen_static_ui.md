# Nhiệm vụ: Backtest Screen — Static UI — Phase 1

> Thuộc Epic [BOT-006 — Backtest Engine](BOT-006_backtest_engine_execution.md), Phase 1 (Static). Phụ thuộc `BOT-021`.

## 1. Mục tiêu (Objective)
Có màn hình Backtest **thực thụ** đầu tiên: cấu hình chiến lược, chạy static backtest, xem kết quả trực quan — thay vì chỉ có handler chạy nền không có UI như hiện tại.

## 2. Mô tả (Description)
Thêm `BacktestView`/`BacktestPresenter` vào `src/presentation/ui/screens/backtest/` (thư mục đang **trống**), theo đúng pattern Presenter/View đã có ở `dashboard/` và `data_management/`. Đăng ký entry mới vào Sidebar.

## 3. Các bước thực hiện (Action Items)
- [ ] Config panel: chọn symbol, interval, khoảng thời gian (hoặc số nến), chọn chiến lược + tham số (vd RSI period/threshold), vốn ban đầu, % phí.
- [ ] Nút "Run Backtest" dispatch `RunStaticBacktestCommand` qua `IDispatcher` trên background thread (theo đúng pattern `_on_load_history` của `dashboard_presenter.py` — không dispatch trên main thread).
- [ ] Results panel: stat cards (Win rate, Total PnL %, Max Drawdown, số lệnh), biểu đồ equity curve (pyqtgraph line chart đơn giản), bảng danh sách trade (`QTableView`).
- [ ] Overlay điểm Buy/Sell lên `ChartCard` hiện có (tái sử dụng component, thêm 1 layer marker nhẹ — không sửa core candlestick logic).
- [ ] Trạng thái Loading/Empty/Error hiển thị rõ ràng, không im lặng nuốt lỗi — theo `.agents/rules/testing.md`.
- [ ] Icon Sidebar dùng bộ Lucide đã tích hợp ở `BOT-016` (vd icon dạng biểu đồ/flask).
- [ ] Unit test cho `BacktestPresenter` (mock dispatcher/event bus, assert đúng state UI cho từng trường hợp: thành công, không có dữ liệu, lỗi).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đảm bảo cập nhật UI kết quả marshal đúng về main thread (giống pattern hiện có ở `dashboard_presenter.py`), vì backtest chạy nền.
- Đây là màn hình "thực thụ" đầu tiên — ưu tiên đúng/đủ hơn đẹp; polish thêm (replay động, live update) thuộc Phase 2 (`BOT-024`).
