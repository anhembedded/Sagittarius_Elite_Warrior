# Nhiệm vụ: Backtest Screen — Dynamic Replay UI — Phase 2

> Thuộc Epic [BOT-006 — Backtest Engine](BOT-006_backtest_engine_execution.md), Phase 2 (Dynamic). Phụ thuộc `BOT-022`, `BOT-023`.

## 1. Mục tiêu (Objective)
Mở rộng màn hình Backtest (`BOT-022`) với chế độ replay động — xem lại quá khứ như đang xem live, thay vì chỉ nhận kết quả cuối cùng.

## 2. Mô tả (Description)
Thêm control replay (play/pause/stop/tốc độ) và cập nhật trực tiếp `ChartCard` + equity curve + trade log theo từng nến phát ra, tái sử dụng tối đa component đã có (`ChartCard`, `LastPriceLine`, `VolumeItem`...) — không viết lại pipeline nến.

## 3. Các bước thực hiện (Action Items)
- [ ] Replay controls: Play/Pause/Stop + speed selector (1x/5x/20x/Instant), dispatch `PauseBacktestCommand`/`ResumeBacktestCommand`/`SetReplaySpeedCommand` (từ `BOT-023`).
- [ ] `ChartCard` cập nhật candle-by-candle giống hệt cơ chế live tick hiện có (tái sử dụng luồng cập nhật đã có ở live streaming, không tạo pipeline nến thứ 2).
- [ ] Equity curve + stat cards cập nhật tăng dần theo `BacktestProgressEvent` (khác Static mode — không đợi tới cuối mới hiển thị).
- [ ] Trade log panel: append dòng mới theo `BacktestTradeSimulatedEvent`, highlight buy/sell theo màu theme đã có (`BULL_COLOR`/`BEAR_COLOR` từ `chart_card/theme.py`).
- [ ] Unit test cho phần binding event → UI update (mock event bus, assert đúng state UI sau mỗi loại event: progress/trade/paused/resumed/completed).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Tần suất update UI cao khi tốc độ replay lớn (vd Instant) — cần throttle việc **vẽ lại UI** (không phải throttle dữ liệu gốc) để tránh giật lag, giống cách đã tối ưu cho live streaming.
- Đảm bảo dừng/đóng màn hình giữa chừng khi đang replay không để lại background task treo — gọi đúng `CancellationToken`/`dispose()` như các component khác trong `chart_card/`.
