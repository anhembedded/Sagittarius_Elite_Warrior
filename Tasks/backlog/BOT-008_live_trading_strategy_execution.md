# Nhiệm vụ: Xây dựng Module Chiến lược Live Trading & Tín hiệu Giao dịch

**Priority:** Deferred on purpose (was P1; the owner decides when live trading starts)
**Board:** Tính toán chỉ báo (RSI, EMA, MACD) từ Live Stream & phát tín hiệu đặt lệnh qua Binance API. Mọi phụ thuộc kỹ thuật đã xong — `BOT-078` (out-of-sample) **đã xong** (14/08) nhưng **chưa tự động mở khoá**: cần quyết định tường minh của user, không suy ra từ việc code xong, vì `PythonBinanceClient` nối thẳng mainnet thật, không có testnet. Xem ghi chú định hướng ở đầu file.
**Complexity:** 🔴 **`L (Thinking)`**
**Depends on:** `BOT-001` ✅, `BOT-005` ✅

## 1. Mục tiêu (Objective)
Cho phép bot tự động tính toán các chỉ báo kỹ thuật (RSI, EMA, MACD) trực tiếp từ luồng dữ liệu thời gian thực (Live Stream) và phát tín hiệu Mua/Bán (OrderSignal) để thực thi đặt lệnh trên Binance Testnet/Paper Trading.

## 2. Mô tả (Description)
Sau khi nến được cập nhật real-time qua WebSocket (`LiveStreamAdapter`), các Indicator Evaluator sẽ tính toán giá trị mới nhất. Khi đạt điều kiện chiến lược, hệ thống sẽ phát sinh `ExecuteOrderCommand` qua CQRS Pipeline.

## 3. Các bước thực hiện (Action Items)
- [ ] Thiết kế `IIndicator` và triển khai các chỉ báo phổ biến: `RSI`, `EMA`, `MACD`.
- [ ] Tạo `StrategyEngine` đăng ký lắng nghe sự kiện `MarketTickEvent` để tính toán chỉ báo theo từng nến đóng/từng tick.
- [ ] Định nghĩa `ExecuteOrderCommand` và `ExecuteOrderCommandHandler` trong Application Layer.
- [ ] Kết nối `BinanceExchangeClient` với Binance Testnet REST API để gửi lệnh Mua/Bán thật hoặc giả lập.
- [ ] Cập nhật trạng thái lệnh (Executed / Filled / Rejected) lên Monitor Card trên giao diện.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Không lưu các hằng số API Key / Secret Key cứng trong code; đọc từ `user_config.json` hoặc Environment Variables.
- Cần có cơ chế ngắt khẩn cấp (Emergency Stop) trên UI để người dùng dừng tất cả các lệnh đang chạy.
