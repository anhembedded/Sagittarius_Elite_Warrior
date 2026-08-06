# Nhiệm vụ: Xây dựng Cỗ máy Backtest (Backtesting Engine)

## 1. Mục tiêu (Objective)
Tận dụng cơ sở dữ liệu khổng lồ (SQL Sharding) đã thu thập để chạy mô phỏng các thuật toán/chiến lược giao dịch trong quá khứ, xuất báo cáo tỷ lệ lợi nhuận (Win/Loss Ratio, PnL).

## 2. Mô tả (Description)
Hệ thống hiện tại đã thiết lập sơ bộ luồng Backtest thông qua `RunBacktestCommand` và `BacktestState`.
Nhiệm vụ này sẽ đưa toàn bộ luồng hoạt động vào thực tế: tải dữ liệu từ DB, nhồi nến vào Strategy qua một vòng lặp sự kiện ảo (virtual event loop), khớp lệnh mô phỏng và lưu vết giao dịch.

## 3. Các bước thực hiện (Action Items)
- [ ] Thiết kế `IStrategy` (Abstract Strategy Class) gồm các hàm như `on_tick()`, `on_candle()`, `buy()`, `sell()`.
- [ ] Khởi tạo một Exchange ảo (Paper Trading) để giữ số dư giả lập (Fake Balance) và khớp lệnh giả lập khi Backtest.
- [ ] Tại `RunBacktestCommandHandler`, truy vấn dữ liệu toàn bộ lịch sử từ Database, sau đó chạy vòng lặp mô phỏng.
- [ ] Kết nối tiến trình Backtest với UI (Dashboard hoặc Backtest Screen) để theo dõi phần trăm hoàn thành (Progress Bar).
- [ ] Kết xuất báo cáo lợi nhuận cuối cùng ra giao diện (Thắng/Thua, Sharpe Ratio, Drawdown).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Vòng lặp Backtest xử lý hàng triệu nến có thể "đóng băng" ứng dụng. Phải chia luồng (Threading/Async) và báo cáo tiến trình về UI qua Signals.
- Hỗ trợ mô phỏng cả trượt giá (Slippage) và phí giao dịch (Commission) để mô phỏng thực tế nhất.
