# Nhiệm vụ: Spike — khả thi & chi phí của dữ liệu tick (đo, không đoán)

> Thuộc Epic [`BOT-073`](BOT-073_realtime_tick_backtest_epic.md).
> **Phải xong trước [`BOT-076`](BOT-076_realtime_backtest_engine.md)** — kết quả spike
> này có thể đổi cả thiết kế engine, làm ngược thứ tự thì rủi ro phải viết lại.
>
> **Đây là task điều tra, không phải task code engine.** Sản phẩm bàn giao là một
> báo cáo + vài con số đo thật, không phải tính năng.

## 1. Mục tiêu

Trả lời 4 câu hỏi bằng **số đo thật trên máy thật**, để `BOT-076` bắt đầu với ràng
buộc đã biết thay vì phát hiện giữa chừng:

1. Dữ liệu tick lấy từ đâu, dạng gì?
2. Lưu trữ tốn bao nhiêu — hạ tầng SQLite sharding hiện tại chịu được không?
3. Backtest chạy mất bao lâu — có còn dùng được trong UI không?
4. Cố định 1s hay cho chọn độ phân giải?

## 2. Bối cảnh — cái đã biết chắc

- **`TimeFrame.ONE_SECOND = "1s"` đã tồn tại sẵn** trong
  [`timeframe.py`](../../src/domain/value_objects/timeframe.py) (kèm `to_seconds()`
  xử lý đúng đơn vị `s`). Nên đây **không phải** vấn đề kiểu dữ liệu ở domain — vấn
  đề nằm ở khối lượng và đường ống.
- User đã nói (ghi trong `BOT-042` §2) là **tự làm phần ingestion tick 1s**. Spike
  này **không làm ingestion**, chỉ đánh giá phần hệ thống phải *chứa* và *tiêu thụ*
  nó.
- Ước lượng thô cần kiểm chứng: 1s = **60×** số dòng của 1m → 1 năm/1 symbol ≈
  **31,5 triệu dòng** thay vì ~525K.

## 3. Các bước thực hiện

### 3.1. Nguồn dữ liệu — chốt 1 trong 2

- [x] So sánh **Binance 1s kline** (`interval="1s"`) và **`aggTrades`** (tick thật):
      - Giới hạn API (bao nhiêu bản ghi/request, rate limit, lịch sử lùi được bao xa
        — 1s kline **không** có sẵn lùi vô hạn như 1m).
      - `aggTrades` là tick thật nhưng **không đều nhịp** và lớn hơn nhiều bậc.
      → Xem [báo cáo](../reports/tick_data_feasibility.md) §3.1: weight 2 vs 4/request, số đo docs chính thức.
- [x] Chốt: dùng cái nào, và **ghi rõ giới hạn fidelity kèm theo** — **user xác nhận
      19/08: dùng `1s kline`, không dùng `aggTrades`.** Giới hạn fidelity (gộp OHLCV
      trong giây, không phải từng lệnh riêng lẻ) đã ghi ở báo cáo §3.1.

### 3.2. Lưu trữ — đo thật, không ngoại suy từ lý thuyết

- [x] Sync thật **1 symbol × 7 ngày** ở `1s`, đo dung lượng file `.db` thực tế
      (`database/<SYMBOL>.db`), so với chính nó ở `1m`. → 120,12 MiB vs 2,11 MiB thật,
      xem báo cáo §3.2 (kèm 1 gotcha WAL checkpoint tìm được lúc đo).
- [x] Ngoại suy ra 1 năm từ số đo đó (~6,3 GiB/năm/symbol) — **chưa** ngoại suy nhiều
      symbol cùng lúc, ngoài phạm vi cửa sổ 7 ngày × 1 symbol đã đo.
- [ ] Kiểm tra sharding hiện tại có cần shard thêm theo thời gian không — **chưa đánh
      giá kỹ ở quy mô nhiều symbol × nhiều tháng**; ở quy mô 1 symbol/7 ngày (120 MiB)
      rõ ràng chưa cần, nhưng đó không phải câu hỏi mà mục này thật sự hỏi.
- [x] Đo thời gian `get_klines()` cho 1 khoảng 7 ngày ở `1s` — 6,32s thật (so với
      0,16s ở `1m`), xem báo cáo §3.2.

### 3.3. Runtime — có số so sánh sẵn

- [x] Điểm neo đã biết từ log [`BUG-002`](../bug_report/BUG-002.md): static backtest
      **10.079 nến (7 ngày, 1m) mất ~1,5 giây** (`19:13:19,548` →
      `19:13:21,033`). Cùng 7 ngày đó ở `1s` = **604.800 tick**.
- [x] Đo thật thời gian chạy hết 604.801 điểm dữ liệu — không phải vòng lặp trần, mà
      chạy thẳng `RunStaticBacktestCommandHandler` thật (`ema_crossover`, có indicator
      + out-of-sample) → **10,98s**, 11.285 trades. Xem báo cáo §3.3.
- [ ] Ước lượng thêm chi phí tính lại N indicator mỗi tick riêng biệt (đo 1 indicator ×
      1 tick rồi nhân) — **chưa tách riêng**; số 10,98s ở trên đã bao gồm indicator của
      `ema_crossover` (2 EMA) lẫn trong đó, không phải baseline "không indicator".
- [x] Kết luận: chạy trong UI được không, hay bắt buộc phải có progress + cancel +
      chạy nền — **bắt buộc chạy nền**: query + handler ≈ 17s tổng, hạ tầng
      `CancellationToken` sẵn có từ `BOT-034`/`BOT-095C` dùng lại được, không cần xây
      mới. Xem báo cáo §3.3.

### 3.4. Độ phân giải — cố định hay cho chọn

- [x] Đánh giá đề xuất: cho user chọn **1s / 5s / 15s** thay vì cố định 1s — số đo
      thật (17s cho `1s`) ủng hộ rõ đề xuất này. Xem báo cáo §3.4.
- [ ] Nếu chọn được: nó là field trên `RunRealtimeBacktestCommand` (`BOT-076`) hay
      một `TimeFrame` riêng? — **cố ý để `BOT-076` tự chốt lúc code**, spike này chỉ
      xác nhận "có nên cho chọn", không chốt kiến trúc field.

> ✅ **Kết luận spike (19/08)**: câu 1-3 đã đo thật đầy đủ, câu 4 đã có kết luận sơ bộ
> đủ để `BOT-076` bắt đầu. **Không còn chặn `BOT-076`.** 2 mục còn để trống ở trên
> (sharding đa symbol/nhiều tháng, chi phí indicator tách riêng theo tick) là phần
> tinh chỉnh — không phải điều kiện tiên quyết, người làm `BOT-076` bổ sung khi cần
> chứ không phải quay lại làm task này trước.

## 4. Sản phẩm bàn giao

- [x] Một báo cáo ở [`Tasks/reports/tick_data_feasibility.md`](../reports/tick_data_feasibility.md)
      gồm: bảng số đo thật (dung lượng, thời gian query, thời gian chạy), quyết định
      nguồn dữ liệu, quyết định độ phân giải, và **giới hạn fidelity đã biết**.
- [x] Kết luận: **khả thi**, không phải "không khả thi" — nhưng có điều kiện rõ ràng
      (bắt buộc chạy nền, nên cho chọn độ phân giải) chứ không phải "cứ code là chạy
      mượt". Nói thẳng kèm số thật, đúng tinh thần mục này.

## 5. Rủi ro / Lưu ý

- **Cám dỗ**: bắt đầu code engine luôn vì "thấy cũng dễ". Đừng. Toàn bộ giá trị của
  task này là ràng buộc phát hiện **trước**, không phải sau.
- Không sửa `IIndicator`/`Series` ở đây — đó là [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md).
- Sync 7 ngày dữ liệu 1s có thể mất khá lâu và tốn rate limit — chạy 1 lần, giữ lại
  file `.db` để `BOT-076` dùng lại làm fixture, đừng sync đi sync lại.
- Cẩn thận không commit file `.db` đo được vào repo.

## 6. Phụ thuộc

- Không chặn bởi task nào; chặn `BOT-076`.
- Ingestion tick 1s — user tự làm, ngoài phạm vi (`BOT-042` §2).
