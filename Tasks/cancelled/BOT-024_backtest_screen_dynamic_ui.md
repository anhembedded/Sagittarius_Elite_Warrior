# ❌ ĐÃ HUỶ — BOT-024: Backtest Screen — Replay UI

> **Trạng thái: HUỶ (2026-08-19), do user quyết định. Không làm task này.**
> Nội dung gốc giữ nguyên bên dưới **chỉ để tham khảo lịch sử** — đừng thực hiện nó.

## Vì sao huỷ

Toàn bộ nội dung task này — replay controls Play/Pause/Stop + speed selector,
`PauseBacktestCommand`/`ResumeBacktestCommand`/`SetReplaySpeedCommand` — **là
đúng** [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md) §3.5,
điều khiển tốc độ trên vòng lặp tick của Realtime Backtest. Task này tự ghi
rõ điều đó trong chính đầu file (`đổi phụ thuộc: BOT-023 → BOT-076`, "Mọi
command replay ... nay thuộc BOT-076 §3.5").

Khi đóng `BOT-076` (19/08), user được hỏi thẳng về đúng tính năng này —
*"why need that? play/pause/replay speed i thougth i remove that yet. or
you thing we still need that feature?"* — và chọn **"Drop it, close out
BOT-076"**. §3.5 trong file `BOT-076` đã ghi lại quyết định đó và đánh dấu
huỷ. `BOT-024` là cùng một tính năng dưới một mã task khác, tồn tại độc lập
trong backlog trước khi liên kết `BOT-076` §3.5 này được phát hiện lại lúc
dọn `ROADMAP.md` — giữ nó lại sẽ để backlog treo một việc user đã từ chối
rõ ràng, dưới cái tên khác.

Nếu sau này thật sự cần lại play/pause/replay speed, mở lại **`BOT-076`
§3.5** (đã có sẵn đặc tả kỹ thuật: pause/resume qua command riêng tác động
lên cùng vòng lặp §3.2, throttle không được đổi kết quả) — đừng dựng lại
`BOT-024` như một task UI riêng.

---

# Nhiệm vụ: Backtest Screen — Replay UI (nội dung gốc, không thực hiện)

> Thuộc Epic [BOT-006 — Backtest Engine](../backlog/BOT-006_backtest_engine_execution.md). Phụ thuộc `BOT-022` ✅, [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md).
>
> 📌 **2026-08-18 — đổi phụ thuộc: `BOT-023` → `BOT-076`.**
> `BOT-023` (Dynamic Backtest Engine) **đã bị huỷ**
> ([hồ sơ huỷ](BOT-023_dynamic_backtest_engine.md)); engine replay duy
> nhất giờ là `BOT-076` (Realtime, chạy theo tick). Mọi command replay
> (`PauseBacktestCommand`/`ResumeBacktestCommand`/`SetReplaySpeedCommand`) nay thuộc
> `BOT-076` §3.5, không phải `BOT-023`. Bản thân UI ở task này gần như không đổi —
> chỉ đổi thứ nó điều khiển. Chữ "Dynamic" trong tài liệu cũ = engine đã huỷ, đừng
> hiểu là chế độ đang tồn tại.
>
> `BOT-022` đã mở rộng scope theo [Epic BOT-040](../backlog/BOT-040_backtest_screen_full_feature_epic.md)
> (Top Toolbar/Performance Metrics/Chart Canvas/Trade Logs Table đầy đủ hơn
> bản gốc). Task này kế thừa nguyên UI đó — không viết lại action items ở
> đây, chỉ thêm phần replay động. Các phần bị BOT-040 đánh dấu "chờ
> `BOT-041`/`BOT-042`/`BOT-043`" ở `BOT-022` vẫn chờ tương tự ở đây, không tự
> mở khoá khi làm Dynamic mode.

## 1. Mục tiêu (Objective)
Mở rộng màn hình Backtest (`BOT-022`) với chế độ replay động — xem lại quá khứ như đang xem live, thay vì chỉ nhận kết quả cuối cùng.

## 2. Mô tả (Description)
Thêm control replay (play/pause/stop/tốc độ) và cập nhật trực tiếp `ChartCard` + equity curve + trade log theo từng nến phát ra, tái sử dụng tối đa component đã có (`ChartCard`, `LastPriceLine`, `VolumeItem`...) — không viết lại pipeline nến.

## 3. Các bước thực hiện (Action Items)
- [ ] Replay controls: Play/Pause/Stop + speed selector (1x/5x/20x/Instant), dispatch `PauseBacktestCommand`/`ResumeBacktestCommand`/`SetReplaySpeedCommand` (từ [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md) §3.5).
- [ ] `ChartCard` cập nhật candle-by-candle giống hệt cơ chế live tick hiện có (tái sử dụng luồng cập nhật đã có ở live streaming, không tạo pipeline nến thứ 2).
- [ ] Equity curve + stat cards cập nhật tăng dần theo `BacktestProgressEvent` (khác Static mode — không đợi tới cuối mới hiển thị).
- [ ] Trade log panel: append dòng mới theo `BacktestTradeSimulatedEvent`, highlight buy/sell theo màu theme đã có (`BULL_COLOR`/`BEAR_COLOR` từ `chart_card/theme.py`).
- [ ] Unit test cho phần binding event → UI update (mock event bus, assert đúng state UI sau mỗi loại event: progress/trade/paused/resumed/completed).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Tần suất update UI cao khi tốc độ replay lớn (vd Instant) — cần throttle việc **vẽ lại UI** (không phải throttle dữ liệu gốc) để tránh giật lag, giống cách đã tối ưu cho live streaming.
- Đảm bảo dừng/đóng màn hình giữa chừng khi đang replay không để lại background task treo — gọi đúng `CancellationToken`/`dispose()` như các component khác trong `chart_card/`.
