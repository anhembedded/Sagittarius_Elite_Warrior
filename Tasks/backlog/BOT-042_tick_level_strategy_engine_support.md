# Nhiệm vụ: Tick-Level Indicator/Strategy Engine Support

> Thuộc [Epic BOT-040](BOT-040_backtest_screen_full_feature_epic.md), Phase 0
> (chặn 2/4 Execution Trigger Rule: "Historical bar tick" + "Realtime bar
> tick"). Phụ thuộc `BOT-020` ✅.

## 1. Mục tiêu

Cho phép `IIndicator`/`StrategyEngine` xử lý dữ liệu **tick** (user tự làm
ingestion tick 1s — xem mục 2) thay vì chỉ nến đã đóng, để 2 Execution
Trigger Rule "trên mỗi tick" trong spec UI mới có ý nghĩa thật, không phải
checkbox trang trí.

## 2. Bối cảnh — ranh giới rõ với phần user tự làm

User sẽ tự xây "làm tick 1s" — nhiều khả năng là: gọi Binance API lấy dữ
liệu granularity nhỏ hơn nến chuẩn (aggTrade/1s kline), lưu trữ, cấp phát vào
hệ thống hiện có. **Việc đó ngoài phạm vi task này.** Task này chỉ lo phần
**tiêu thụ**: 1 khi có dữ liệu tick, `StrategyEngine`/`IIndicator` hiện tại
có dùng được không? — Câu trả lời hiện tại là **không**, vì:

- `IIndicator.update(value: float) -> T | None` — 1 lần gọi = 1 điểm dữ liệu
  đã "chốt" (SMA/EMA/RSI đều giả định input là chuỗi giá trị rời rạc theo
  thứ tự thời gian, không phân biệt "tick giữa nến" và "nến đã đóng").
- `StrategyEngine._process_one(candle: MarketData)` nhận nguyên 1
  `MarketData` (nến đầy đủ OHLCV) — không có đường dẫn nhận 1 tick giá đơn lẻ
  chưa đóng nến.
- `BaseStrategy`/`Series` (BOT-026) giả định `decide()` được gọi 1 lần/bar
  đã đóng — gọi nhiều lần/bar (mỗi tick) sẽ làm sai lệch lịch sử `Series`
  nếu không có thay đổi (mỗi tick sẽ bị hiểu nhầm là 1 "bar" mới).

## 3. Câu hỏi thiết kế — CHƯA CHỐT, cần quyết định trước khi viết action item

1. **Indicator có tính lại mỗi tick hay chỉ mỗi bar đóng?** — 2 hướng khác
   hẳn nhau:
   - (a) Indicator vẫn chỉ cập nhật khi bar đóng (như hiện tại); tick chỉ
     dùng để đánh giá SL/TP/entry price chính xác hơn trong `PaperExchange`
     (`BOT-041`), không đụng tới indicator/strategy engine. Nếu đây là ý user
     muốn, task này **không cần làm** — mọi thứ nằm gọn trong `BOT-041`.
   - (b) Indicator tính lại mỗi tick (giá trị RSI/EMA "sống" thay đổi liên
     tục trong nến chưa đóng, giống TradingView `calc_on_every_tick=true`) —
     cần `Series`/`IIndicator` phân biệt "cập nhật tạm" (tick, có thể bị ghi
     đè bởi tick tiếp theo cùng bar) với "cập nhật chốt" (bar đóng, ghi vào
     lịch sử vĩnh viễn) — thay đổi kiến trúc thật sự, không nhỏ.
2. Nếu chọn (b): `Series.push()` hiện tại luôn ghi vĩnh viễn — cần thêm khái
   niệm "giá trị tạm của bar hiện tại" tách khỏi lịch sử đã chốt, nếu không
   `crossed_above`/`crossed_below` (BOT-026) sẽ tính sai (so sánh nhầm 2 tick
   cùng 1 bar như thể là 2 bar khác nhau).
3. Batch (static backtest) ≡ incremental (live) có còn đúng khi thêm tick
   không? — bất biến này (`BOT-020`) hiện đảm bảo bằng cách cả 2 mode đi qua
   đúng 1 `_process_one`. Thêm tick cần giữ được bất biến tương đương, hoặc
   chấp nhận batch/tick-incremental là 2 con đường tính toán khác nhau có
   chủ đích (cần nói rõ, không được ngầm định).

**Không tự chọn (a) hay (b) khi bắt đầu code task này — quay lại hỏi user
trước, vì đây là quyết định kiến trúc ảnh hưởng toàn bộ engine, không phải
chi tiết cài đặt.**

## 4. Phụ thuộc

- `BOT-020` ✅ — `IIndicator`/`StrategyEngine`, nơi thay đổi sẽ xảy ra.
- `BOT-026` ✅ — `Series`/`BaseStrategy`, ảnh hưởng nếu chọn hướng (b).
- Dữ liệu tick 1s — user tự làm, ngoài phạm vi.
