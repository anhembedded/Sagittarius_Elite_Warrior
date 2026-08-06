# Nhiệm vụ: Dynamic Backtest Engine — Paper Exchange & Virtual Event Loop — Phase 2

> Thuộc Epic [BOT-006 — Backtest Engine](BOT-006_backtest_engine_execution.md), Phase 2 (Dynamic). Phụ thuộc `BOT-020`, `BOT-021`. Nên bắt đầu **sau khi** Phase 1 (`BOT-021`/`BOT-022`) chạy đúng và có unit test đầy đủ.

## 1. Mục tiêu (Objective)
Mô phỏng lại dữ liệu lịch sử **như đang chạy live** (Virtual Event Loop): chạy chỉ báo + chiến lược + khớp lệnh giả lập theo từng nến phát ra tuần tự, có thể tua nhanh/chậm/tạm dừng — khác Static ở chỗ trải nghiệm giống hệt live trading, không chỉ ra kết quả cuối cùng.

## 2. Mô tả (Description)
Mở rộng vòng lặp replay **đã có sẵn** trong `run_backtest/handler.py` (hiện chỉ emit `MarketTickEvent` có throttle `replay_speed_ms`, **chưa chạy chiến lược/khớp lệnh gì cả**) — nối nó vào `StrategyEngine.on_tick()` (incremental mode, `BOT-020`) + `PaperExchange` (`BOT-021`) để mỗi nến phát ra vừa cập nhật chart vừa có thể sinh lệnh giả lập, đúng hành vi lúc live trading nhưng trên dữ liệu quá khứ.

## 3. Các bước thực hiện (Action Items)
- [ ] Nối `RunBacktestCommandHandler` hiện tại với `StrategyEngine.on_tick()` + `PaperExchange` — mỗi candle: cập nhật chỉ báo → có Signal thì khớp lệnh giả lập → cập nhật equity đang chạy.
- [ ] Thêm `PauseBacktestCommand`/`ResumeBacktestCommand`, `SetReplaySpeedCommand` (đổi `replay_speed_ms` khi đang chạy, không cần dừng hẳn).
- [ ] Events: `BacktestProgressEvent(candle_index, total, current_equity)`, `BacktestTradeSimulatedEvent(trade)`, `BacktestPausedEvent`, `BacktestResumedEvent`, `BacktestCompletedEvent`, `BacktestStoppedEvent` (chuẩn hoá đầy đủ ở `BOT-025`).
- [ ] Đảm bảo vòng lặp chạy trên `ITaskManager` (background task, cancel được qua `CancellationToken`), không chặn UI thread — theo đúng pattern `BinanceWebsocketService`.
- [ ] Unit test: pause/resume/đổi tốc độ hoạt động đúng; events phát đúng thứ tự; **PaperExchange khớp lệnh nhất quán với Static mode (`BOT-021`)** trên cùng dữ liệu + tham số (bài test đối chiếu quan trọng — dynamic và static phải cho cùng kết quả cuối, nếu lệch nghĩa là 1 trong 2 có bug).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Parity dynamic-vs-static là điều kiện bắt buộc trước khi coi task này hoàn thành — không merge nếu 2 chế độ cho kết quả khác nhau trên cùng input.
- Cần cơ chế giới hạn/emergency-stop để vòng lặp replay không chạy vô hạn hoặc treo nếu dữ liệu quá lớn.
