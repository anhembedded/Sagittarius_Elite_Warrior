# Nhiệm vụ: Indicator & Strategy Engine (Core) — Phase 0

> Thuộc Epic [BOT-006 — Backtest Engine](BOT-006_backtest_engine_execution.md), Phase 0 (Nền tảng dùng chung).

## 1. Mục tiêu (Objective)
Xây dựng lõi tính chỉ báo kỹ thuật + đánh giá chiến lược, dùng chung cho cả **Backtest** (Phase 1/2 của epic này) và **Live Trading** (`BOT-008`) — tránh xây 2 bộ Indicator/Strategy khác nhau cho 2 tính năng vốn cần cùng 1 logic.

## 2. Mô tả (Description)
Lõi tính toán thuần (pure logic), không phụ thuộc UI, I/O hay Binance API, chạy được ở 2 chế độ:
- **Batch**: nhận toàn bộ mảng nến, trả về danh sách tín hiệu — dùng cho Static Backtest (`BOT-021`).
- **Incremental**: nhận từng nến/tick một, tự cập nhật state nội bộ, trả về tín hiệu (nếu có) — dùng cho Dynamic Backtest (`BOT-023`) và Live Trading (`BOT-008`).

## 3. Các bước thực hiện (Action Items)
- [ ] `IIndicator` protocol + cài đặt `RSI`, `EMA`, `MACD` (pure function/class, có thể unit test độc lập với dữ liệu đã biết trước kết quả).
- [ ] `IStrategy` protocol: `evaluate(context) -> Signal` (Signal gồm action Buy/Sell/Hold, lý do, giá, thời điểm).
- [ ] `StrategyEngine` hỗ trợ 2 chế độ chạy:
  - [ ] `run_batch(klines: list[MarketData]) -> list[Signal]`.
  - [ ] `on_tick(candle: MarketData) -> Signal | None` (giữ state giữa các lần gọi).
- [ ] `SignalGeneratedEvent(symbol, action, reason, price, time)` phát qua `IEventBus` mỗi khi có tín hiệu mới (cả 2 chế độ).
- [ ] Unit test: từng indicator so khớp giá trị với công thức chuẩn (dùng bộ dữ liệu tham chiếu cố định); `StrategyEngine` cho kết quả **giống nhau** giữa batch và incremental trên cùng 1 bộ dữ liệu (đây là bài test đối chiếu quan trọng — nếu 2 chế độ lệch nhau nghĩa là có bug).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đây là nền tảng dùng chung — khi triển khai `BOT-008`, action item "Thiết kế `IIndicator`..." của task đó nên **tái sử dụng module này** thay vì làm lại từ đầu. Nên làm `BOT-020` trước hoặc song song với bước đầu của `BOT-008`.
- Không gọi bất kỳ I/O nào (DB, network) trong `StrategyEngine`/indicator — giữ pure để test nhanh và dễ đối chiếu batch/incremental.
