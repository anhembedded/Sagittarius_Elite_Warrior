# Nhiệm vụ: Watchlist / Market Overview

## 1. Mục tiêu (Objective)
Cho phép theo dõi nhiều symbol cùng lúc dưới dạng bảng (giá hiện tại, % thay đổi, volume) thay vì phải mở từng ChartCard riêng lẻ — tận dụng hạ tầng Live Stream đã hoàn thiện ở BOT-005.

## 2. Mô tả (Description)
Thêm `WatchlistCard`/`WatchlistScreen` hiển thị bảng (QTableView) các symbol đang theo dõi, cập nhật realtime qua `MarketTickEvent` giống cách `ChartCard` đang nhận dữ liệu, nhưng không cần vẽ candlestick — chỉ cần giá đóng cửa gần nhất, % thay đổi so với phiên/nến trước, và volume.

## 3. Các bước thực hiện (Action Items)
- [ ] `WatchlistTableModel` (QAbstractTableModel): cột Symbol / Last Price / % Change / Volume, cập nhật cell qua `dataChanged` khi có tick mới — tránh render lại toàn bảng mỗi tick.
- [ ] `WatchlistPresenter` đăng ký lắng nghe `MarketTickEvent` (giống `dashboard_presenter.py` đang làm), map sang dòng tương ứng trong model theo symbol.
- [ ] Highlight màu xanh/đỏ tạm thời khi giá tăng/giảm (dùng `theme.py`'s `BULL_COLOR`/`BEAR_COLOR` đã có sẵn từ chart_card).
- [ ] Danh sách symbol theo dõi lấy từ `DEFAULT_SYMBOLS` trong config (tái dùng, không tạo cơ chế cấu hình symbol thứ hai) — mở rộng thêm được nếu BOT-017 (Settings Screen) đã có UI quản lý symbol.
- [ ] Click vào 1 dòng trong watchlist để chuyển ChartCard tương ứng lên focus (nếu đang hiển thị) — không bắt buộc phải mở chart mới.
- [ ] Unit test cho `WatchlistTableModel`/`WatchlistPresenter` (mock event bus, assert đúng dòng/cột được cập nhật) theo `.agents/rules/testing.md`.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Nhiều symbol tick liên tục — đảm bảo update UI qua đúng cơ chế thread-safe hiện có (giống cách `dashboard_presenter.py` marshal sang main thread), không update trực tiếp từ WebSocket thread.
- Không tự ý stream thêm symbol ngoài danh sách đã cấu hình — tránh vượt rate-limit của Binance WebSocket.
