# Nhiệm vụ: Tick-Level Indicator/Strategy Engine Support — *Provisional vs Commit*

> Thuộc [Epic BOT-073](BOT-073_realtime_tick_backtest_epic.md) (chủ sở hữu mới)
> và [Epic BOT-040](BOT-040_backtest_screen_full_feature_epic.md), Phase 0
> (chặn 2/4 Execution Trigger Rule: "Historical bar tick" + "Realtime bar
> tick"). Phụ thuộc `BOT-020` ✅, `BOT-026` ✅.
>
> ✅ **Câu hỏi kiến trúc ở §3 đã được user chốt: chọn hướng (b).** Mục 3 giữ
> nguyên phần phân tích (vẫn đúng và là bối cảnh cần thiết), quyết định + action
> item cụ thể nằm ở **mục 4 mới**.

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

~~**Không tự chọn (a) hay (b) khi bắt đầu code task này — quay lại hỏi user
trước.**~~ → **Đã hỏi và đã chốt, xem mục 4.**

## 4. Quyết định đã chốt: **hướng (b)** — và vì sao nó rẻ hơn vẻ ngoài

User chọn **(b)**: indicator **tính lại mỗi tick**, giá trị RSI/EMA "sống" thay
đổi liên tục trong nến chưa đóng (giống `calc_on_every_tick=true` của TradingView).

### 4.1. Chìa khoá: *provisional* tính được O(1), không cần snapshot/rollback

Nghe "tính lại mỗi tick" dễ tưởng phải lưu ảnh chụp state rồi khôi phục. **Không
cần.** Phần lớn indicator tính giá trị tạm được **O(1)** từ state **đã chốt** + giá
hiện tại, chỉ bằng cách **không gán ngược vào state**:

- [`ema.py`](../../src/domain/indicators/ema.py) hiện là
  `self._ema = (value - self._ema) * self._multiplier + self._ema` — bản provisional
  chính là **đúng biểu thức đó nhưng bỏ phép gán**.
- Cùng nguyên tắc áp cho RSI/MACD/WMA: đọc state đã chốt, trả kết quả, **không
  mutate**.

Nên đây là **thay đổi contract**, không phải thay đổi thuật toán. Đó là lý do
`BOT-073` đánh giá task này "rủi ro cao nhất epic" (đụng domain dùng chung) nhưng
**không** đánh giá là "khối lượng lớn nhất".

### 4.2. Các bước thực hiện

- [ ] Mở rộng contract `IIndicator`: tách rõ **tính tạm** (không mutate, gọi được
      nhiều lần/bar) khỏi **chốt** (mutate, đúng 1 lần/bar khi bar đóng). Giữ
      `update()` hiện tại làm đường "chốt" để **không file nào đang dùng phải sửa**.
- [ ] Áp cho toàn bộ indicator hiện có (`EMA`/`SMA`/`RSI`/`MACD`/`WMA`...). Guard
      test: với cùng chuỗi giá, đường bar-close mới **phải cho kết quả giống hệt**
      bản hiện tại — bất biến số 1 của task này.
- [ ] `Series` ([`series.py`](../../src/domain/scripting/series.py)): thêm khái niệm
      "giá trị tạm của bar hiện tại" tách khỏi lịch sử đã chốt. `push()` giữ nguyên
      ngữ nghĩa ghi vĩnh viễn; tick ghi vào ô tạm và **ghi đè chính nó**, không đẩy
      slot mới.
- [ ] Verify `crossed_above`/`crossed_below` (`BOT-026`) vẫn đúng khi đọc "tạm vs
      chốt" — đây là chỗ dễ sai nhất: 2 tick trong cùng 1 bar **không được** bị so
      như 2 bar khác nhau (nếu không → tín hiệu giả hàng loạt).
- [ ] `StrategyEngine`: thêm đường nhận 1 tick (giá + timestamp của bar đang hình
      thành) tách khỏi `on_tick(candle)` hiện tại (tên `on_tick` hiện đang chỉ "1
      nến đã đóng" — cân nhắc đổi tên cho khỏi hiểu nhầm, nhưng **đừng** đổi hành vi).
- [ ] **Ghi lại lời hứa bất biến** (câu hỏi 3 ở §3): `BOT-020` hiện hứa
      "batch ≡ incremental". Sau task này, Static (bar) và Realtime (tick) **cố ý
      cho kết quả khác nhau**. Phải sửa docstring/tài liệu `BOT-020` để nói rõ, kèm
      lý do — nếu không, người sau sẽ tưởng Realtime đang bug. **Đây là action item
      bắt buộc, không phải ghi chú.**

### 4.3. Bất biến bắt buộc giữ

- Đường **bar-close hiện tại không được đổi hành vi một chút nào**. `IIndicator` đang
  dùng bởi: static backtest, Dev Board live, indicator scripts (`BOT-032`), strategies
  (`BOT-026`). Toàn bộ test hiện có phải xanh **không sửa** — sửa test để cho xanh là
  dấu hiệu đã phá bất biến này.
- `strategy_engine.py`/`i_strategy.py`/`strategy_context.py` từng cam kết "diff = 0
  dòng" ở `BOT-026`. Task này **sẽ phải** đụng `strategy_engine.py` (thêm đường tick)
  → cam kết đó hết hiệu lực **một cách có chủ đích**; ghi rõ khi làm, đừng lặng lẽ vi
  phạm.

## 5. Phụ thuộc

- `BOT-020` ✅ — `IIndicator`/`StrategyEngine`, nơi thay đổi sẽ xảy ra.
- `BOT-026` ✅ — `Series`/`BaseStrategy`, bị ảnh hưởng (đã chọn hướng (b)).
- [`BOT-073`](BOT-073_realtime_tick_backtest_epic.md) — epic chủ sở hữu.
- [`BOT-076`](BOT-076_realtime_backtest_engine.md) — consumer đầu tiên; task này
  **chặn** nó.
- Dữ liệu tick 1s — user tự làm, ngoài phạm vi. Chi phí lưu trữ/runtime:
  [`BOT-075`](BOT-075_tick_data_feasibility_spike.md).
