# 📋 BOT-006: Xây dựng Cỗ máy Backtest Chiến lược (Backtesting Engine Core)

> [!IMPORTANT]
> **Độ ưu tiên:** 🔴 P9 (Thấp nhất trong Backlog)  
> **Trạng thái:** Backlog  
> **Lớp liên quan:** Application Layer, Domain Layer, Infrastructure Layer  

---

## 1. 🎯 Mục tiêu (Objective)

Tận dụng cơ sở dữ liệu nến lịch sử khổng lồ (SQL Sharding theo Symbol/Timeframe) đã thu thập để chạy mô phỏng các thuật toán và chiến lược giao dịch trong quá khứ. Cho phép kết xuất báo cáo tỷ lệ thắng/thua (Win/Loss Ratio), PnL, Drawdown và Sharpe Ratio.

---

## 2. 📝 Mô tả Chi tiết (Description)

Hệ thống hiện tại đã có bộ khung CQRS sơ bộ thông qua `RunBacktestCommand` và `BacktestState`.  
Nhiệm vụ này đưa cỗ máy Backtest vào thực tế hoạt động:
1. Truy vấn mảng lớn dữ liệu nến từ SQLite Sharding Database.
2. Đưa nến vào vòng lặp sự kiện ảo (**Virtual Event Loop**).
3. Đánh giá tín hiệu từ chiến lược (`IStrategy`).
4. Khớp lệnh mô phỏng qua Sàn giao dịch ảo (**Paper Trading Exchange**).
5. Theo dõi tiến trình và đẩy phần trăm hoàn thành (Progress Event) về UI qua EventBus.

---

## 3. 🛠️ Các bước Thực hiện (Action Items)

### Phase 1: Core Domain & Application Protocols
- [ ] **Thiết kế Interface `IStrategy`:** Khai báo các hàm callback chuẩn `on_tick()`, `on_candle()`, `buy()`, `sell()`.
- [ ] **Xây dựng `PaperExchange` (Virtual Exchange):** Quản lý số dư giả lập (Fake Balance), khớp lệnh thị trường/giới hạn (Market/Limit Orders), hỗ trợ mô phỏng trượt giá (Slippage) và phí giao dịch (Commission).

### Phase 2: Command Handler Implementation
- [ ] **Truy vấn Dữ liệu Nến hiệu năng cao:** Đọc nến theo chunk từ SQLite Repository nhằm tránh tràn bộ nhớ (OOM).
- [ ] **Virtual Event Loop:** Chạy vòng lặp phát tín hiệu sự kiện mô phỏng theo thứ tự thời gian tăng dần.
- [ ] **Phát sự kiện Tiến trình:** Emit `BacktestProgressEvent` báo phần trăm hoàn thành về UI.

### Phase 3: Reports & Unit Tests
- [ ] **Kết xuất Báo cáo PnL:** Tính toán các chỉ số Win/Loss Rate, Max Drawdown, Profit Factor.
- [ ] **Bổ sung Unit Tests:** Viết bộ test `tests/unit/application/use_cases/test_run_backtest.py` kiểm thử độc lập luồng backtest với dữ liệu mock.

---

## 4. ⚠️ Rủi ro & Lưu ý (Constraints & Risks)

> [!WARNING]
> - Vòng lặp Backtest khi xử lý hàng triệu nến có thể gây **đóng băng UI thread**. Bắt buộc phải chạy trong worker thread thông qua `IThreadManager` hoặc `ITaskManager`.
> - Cần đảm bảo giải phóng bộ nhớ (garbage collection) giữa các lần chạy backtest liên tiếp.
