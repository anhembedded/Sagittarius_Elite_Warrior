# ❌ ĐÃ HUỶ — BOT-023: Dynamic Backtest Engine (Paper Exchange & Virtual Event Loop)

> **Trạng thái: HUỶ (2026-08-18), do user quyết định. Không làm task này.**
> Thay thế bởi [`BOT-076` — Realtime Backtest Engine](../in_progress/BOT-076_realtime_backtest_engine.md).
> Nội dung gốc giữ nguyên bên dưới **chỉ để tham khảo lịch sử** — đừng thực hiện nó.

## Vì sao huỷ

Khối "⛔ DỪNG" trong chính task này (nguồn: 📄 [Rà soát định hướng App](../reports/app_direction_audit.md)
§4) đã nêu sẵn 3 lựa chọn và yêu cầu user chốt trước khi viết dòng code nào.
**User chọn phương án 1: Gộp** — bỏ task này, chuyển replay control (play/pause/
tốc độ) thành một phần của `BOT-076`.

Lý do đằng sau, ghi lại để người sau không "khôi phục" nhầm:

- Repo sắp có **3 engine backtest**, trong đó 2 cái mang **bất biến ngược nhau**:

  | Engine | Bất biến đã cam kết |
  | :--- | :--- |
  | Static (`BOT-021` ✅) | — |
  | **Dynamic (task đã huỷ này)** | **"phải khớp Static tuyệt đối"** — `assert dynamic_result == static_result` |
  | [Realtime (`BOT-076`)](../in_progress/BOT-076_realtime_backtest_engine.md) | **"cố ý khác Static"** |

- Giá trị riêng của task này chỉ là *play/pause/tốc độ để xem replay* — đó là mối
  quan tâm **trình bày (presentation)**, không phải engine. Mà `BOT-076` dù sao cũng
  bắt buộc phải có vòng lặp tick + progress + cancel rồi.
- Đúng hình dạng kiến trúc là **1 engine tick (`BOT-076`) + lớp điều khiển tốc độ ở
  trên**, không phải 2 engine replay song song. Nuôi 3 engine trên cùng một
  `PaperExchange` tốn bảo trì hơn hẳn giá trị tăng thêm.
- Quan trọng hơn cả: Dynamic **không** trả lời được yêu cầu gốc của user (chạy chiến
  lược mỗi giây, khớp lệnh tại giá thời điểm đó thay vì lúc đóng nến) vì nó vẫn
  bar-by-bar. Nó chỉ là "xem lại chậm/nhanh" cùng một kết quả Static.

## Hệ quả cần biết

- **Code Dynamic đang tồn tại vẫn còn trong repo, chưa xoá**:
  `src/application/use_cases/backtest/run_backtest/` (`RunBacktestCommand` /
  `RunBacktestCommandHandler` / `BacktestState`), có đăng ký DI trong
  `binance_bot_module.py` và có unit test riêng
  (`tests/unit/application/use_cases/test_run_backtest.py`). Nó chỉ phát
  `MarketTickEvent` có throttle, **không chạy chiến lược, không khớp lệnh**, và
  **không có consumer thật nào** (không màn hình nào dispatch nó).
- Việc **xoá** phần code đó là một quyết định riêng, chưa được chốt — đừng xoá kèm
  như dọn dẹp tiện tay. Khi `BOT-076` bắt đầu, cân nhắc: hoặc tái dùng vòng lặp
  replay đó làm nền, hoặc xoá hẳn và viết mới. Chốt rõ trước, đừng để lửng lơ.

---

<details>
<summary>📜 Nội dung gốc của task (đã huỷ — chỉ để tham khảo)</summary>

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

</details>
