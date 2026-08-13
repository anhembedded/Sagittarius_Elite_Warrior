# Nhiệm vụ: Dynamic Backtest Engine — Paper Exchange & Virtual Event Loop — Phase 2

> Thuộc Epic [BOT-006 — Backtest Engine](BOT-006_backtest_engine_execution.md), Phase 2 (Dynamic). Phụ thuộc `BOT-020`, `BOT-021`. Nên bắt đầu **sau khi** Phase 1 (`BOT-021`/`BOT-022`) chạy đúng và có unit test đầy đủ.
>
> ## ⛔ DỪNG — chốt quan hệ với `BOT-076` trước khi bắt đầu
>
> Nguồn: 📄 [Rà soát định hướng App](../reports/app_direction_audit.md) §4.
>
> Sau khi [Epic `BOT-073`](BOT-073_realtime_tick_backtest_epic.md) ra đời, repo sắp có
> **3 engine backtest**, trong đó 2 cái có **bất biến ngược nhau**:
>
> | Engine | Bất biến đã cam kết |
> | :--- | :--- |
> | Static (`BOT-021` ✅) | — |
> | **Dynamic (task này)** | **"phải khớp Static tuyệt đối"** — `assert dynamic_result == static_result` |
> | [Realtime (`BOT-076`)](BOT-076_realtime_backtest_engine.md) | **"cố ý khác Static"** |
>
> **Nghi vấn cần trả lời trước khi viết dòng code nào**: giá trị riêng của task này là
> *play/pause/tốc độ để xem replay* — nhưng đó là mối quan tâm **trình bày**, không phải
> engine. Mà `BOT-076` dù sao cũng phải có vòng lặp tick + progress + cancel.
>
> → Nhiều khả năng đúng là **1 engine tick (`BOT-076`) + lớp điều khiển tốc độ ở trên**,
> chứ không phải 2 engine replay song song. Duy trì 3 engine trên cùng một
> `PaperExchange` là bề mặt bảo trì lớn hơn hẳn phần giá trị tăng thêm.
>
> **3 lựa chọn** (user chốt, không tự quyết):
> 1. **Gộp**: bỏ task này, chuyển replay control thành một phần của `BOT-076`.
> 2. **Giữ riêng**: chứng minh được Dynamic có giá trị mà Realtime không thay thế được —
>    ghi rõ giá trị đó ra đây.
> 3. **Đổi vai**: giữ task này nhưng bỏ ràng buộc "khớp Static tuyệt đối", biến nó thành
>    thuần lớp UI replay chạy trên engine bất kỳ.
>
> Quyết định muộn thì **đắt** — viết xong engine rồi mới phát hiện thừa.

## 1. Mục tiêu (Objective)
Mô phỏng lại dữ liệu lịch sử **như đang chạy live** (Virtual Event Loop): chạy chỉ báo + chiến lược + khớp lệnh giả lập theo từng nến phát ra tuần tự, có thể tua nhanh/chậm/tạm dừng — khác Static ở chỗ trải nghiệm giống hệt live trading, không chỉ ra kết quả cuối cùng.

## 2. Mô tả (Description)
Mở rộng vòng lặp replay **đã có sẵn** trong `run_backtest/handler.py` (hiện chỉ emit `MarketTickEvent` có throttle `replay_speed_ms`, **chưa chạy chiến lược/khớp lệnh gì cả**) — nối nó vào `StrategyEngine.on_tick()` (incremental mode, `BOT-020`) + `PaperExchange` (`BOT-021`) để mỗi nến phát ra vừa cập nhật chart vừa có thể sinh lệnh giả lập, đúng hành vi lúc live trading nhưng trên dữ liệu quá khứ.

## 3. Các bước thực hiện (Action Items)
- [ ] Nối `RunBacktestCommandHandler` hiện tại với `StrategyEngine.on_tick()` + `PaperExchange` — mỗi candle: cập nhật chỉ báo → có Signal thì khớp lệnh giả lập → cập nhật equity đang chạy.
- [ ] Thêm `PauseBacktestCommand`/`ResumeBacktestCommand`, `SetReplaySpeedCommand` (đổi `replay_speed_ms` khi đang chạy, không cần dừng hẳn).
- [ ] Events: `BacktestProgressEvent(candle_index, total, current_equity)`, `BacktestTradeSimulatedEvent(trade)`, `BacktestPausedEvent`, `BacktestResumedEvent`, `BacktestCompletedEvent`, `BacktestStoppedEvent` (chuẩn hoá đầy đủ ở `BOT-025`).
- [ ] Đảm bảo vòng lặp chạy trên `ITaskManager` (background task, cancel được qua `CancellationToken`), không chặn UI thread — theo đúng pattern `BinanceWebsocketService`.
- [ ] Unit test: pause/resume/đổi tốc độ hoạt động đúng; events phát đúng thứ tự.
- [ ] **Test parity bắt buộc** — chạy cùng 1 fixture cố định (golden fixture của `BOT-021`, cùng `BacktestProperties`) qua cả 2 đường: Static (`RunStaticBacktestCommandHandler`) và Dynamic (handler của task này ở chế độ chạy hết tốc độ, không throttle). So sánh bằng **`assert dynamic_result == static_result`** trên chính dataclass `BacktestResult` (equality theo field: danh sách `Trade` từng cái, `equity_curve`, `metrics`) — không so sánh gián tiếp qua vài con số tổng hợp. Lệch bất kỳ field nào (kể cả 1 timestamp) = fail, vì nghĩa là vòng lặp động đang tự sắp lại thứ tự fill/submit/mark khác với `PaperExchange.process_candle()`.
- [ ] Vòng lặp động **phải gọi đúng** `PaperExchange.process_candle(candle, signal)` (entry point duy nhất, đã có từ `BOT-021`) cho từng nến — không tự viết lại thứ tự fill→submit→mark ở handler này, đó chính là lý do parity được đảm bảo chứ không phải hy vọng.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Parity dynamic-vs-static (dataclass equality, xem mục Action Items) là điều kiện bắt buộc trước khi coi task này hoàn thành — không merge nếu 2 chế độ cho kết quả khác nhau trên cùng input.
- Cần cơ chế giới hạn/emergency-stop để vòng lặp replay không chạy vô hạn hoặc treo nếu dữ liệu quá lớn.
