# Nhiệm vụ: Static Backtest Execution Engine — Phase 1

> Thuộc Epic [BOT-006 — Backtest Engine](BOT-006_backtest_engine_execution.md), Phase 1 (Static). Phụ thuộc `BOT-020`.

## 1. Mục tiêu (Objective)
Chạy chiến lược trên toàn bộ dữ liệu lịch sử trong **1 lượt tính toán nhanh** (không throttle/sleep, không mô phỏng thời gian thực), trả về kết quả đầy đủ (danh sách trade, equity curve, metrics) gần như tức thời.

## 2. Mô tả (Description)
Vòng lặp replay hiện có trong `run_backtest/handler.py` (emit `MarketTickEvent` có throttle `replay_speed_ms`) vốn được thiết kế cho mô phỏng **dynamic** (Phase 2) — **không phù hợp** cho static mode vì cố ý chạy chậm để giả lập thời gian thực. Static mode cần một đường dẫn riêng: đọc toàn bộ klines từ `IMarketDataRepository`, chạy qua `StrategyEngine.run_batch()` (từ `BOT-020`), mô phỏng khớp lệnh qua `PaperExchange` đơn giản.

## 3. Các bước thực hiện (Action Items)
- [ ] `PaperExchange` (đơn giản): nhận `Signal`, mở/đóng vị thế giả lập, tính PnL theo giá đóng nến kế tiếp, trừ phí cố định (%) — chưa cần mô hình slippage phức tạp ở phase này.
- [ ] `RunStaticBacktestCommand`/`RunStaticBacktestCommandHandler` mới — **tách biệt** khỏi `RunBacktestCommand` hiện tại (command hiện tại thuộc Dynamic mode, Phase 2, giữ nguyên không đổi).
- [ ] `BacktestResult` value object: danh sách trade (giá/thời điểm vào-ra, pnl), equity curve (`list[(time, equity)]`), metrics tổng hợp (win rate, tổng lợi nhuận %, max drawdown, profit factor, số lệnh).
- [ ] Events: `BacktestCompletedEvent(result)`, `BacktestFailedEvent(reason)` — phát qua `IEventBus` khi hoàn tất/lỗi (chi tiết chuẩn hoá ở `BOT-025`).
- [ ] Unit test: `PaperExchange` khớp lệnh đúng với kịch bản đã biết trước; `BacktestResult` tính đúng metrics với dữ liệu giả lập có kết quả kỳ vọng rõ ràng.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Static mode không có `sleep`, nhưng vẫn phải chạy trên background task (`ITaskManager`) để không treo UI thread — dữ liệu lớn (nhiều nghìn nến) vẫn tốn CPU đáng kể.
- Không tái sử dụng nhầm `RunBacktestCommandHandler` hiện tại cho static mode — 2 use case có mục đích khác nhau (nhanh/tức thời vs. mô phỏng thời gian thực), gộp chung sẽ làm rối logic throttle.
