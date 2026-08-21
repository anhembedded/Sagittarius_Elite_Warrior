# BUG-025 — Không có buffer/streaming ở đường dữ liệu Sync (Binance→DB) và Backtest (DB→RAM): RAM phình theo độ dài khoảng, không có trần

**Reported:** 2026-08-20
**Severity:** 🟡 **P2** (chưa crash trong điều kiện thông thường, nhưng scale kém — đặc biệt với khung 1s vừa thêm ở `BOT-112E` và tuỳ chọn "Toàn bộ lịch sử")
**Status:** ✅ **Fixed 2026-08-21 — cả 2 nhánh Sync và Backtest đã sửa + regression-tested**

---

## 1. Triệu Chứng (Symptom)

Quan sát ban đầu (dán kèm màn hình Process Explorer trong VSCode): tiến trình
`python.exe` chạy app hiển thị **862.1 MB RAM** trong khi CPU 0%, Disk 0 MB/s,
Network ~0.5 Mbps — tức tại thời điểm chụp, app đang **rảnh** (không fetch/sync
gì), nhưng RAM vẫn ở mức cao. Nghi vấn ban đầu: "thuật toán fetch database có
vấn đề, RAM càng tăng, không có buffer, vừa fetch vừa lưu RAM chứ không ghi
đĩa".

Đọc code xác nhận: **đúng là không có buffer/chunk ở cả hai đường dữ liệu
chính** — RAM đo được lúc rảnh nhiều khả năng là dư ảnh của lần fetch/backtest
gần nhất (Python GC đã free logic nhưng CPython/Windows CRT không luôn trả RSS
về OS ngay — không tự nó là bằng chứng leak), nhưng cơ chế "load hết vào RAM
rồi mới xử lý" là **thật**, không phải suy đoán, và **không có trần** theo độ
dài khoảng dữ liệu.

---

## 2. Root Cause — hai đường dữ liệu, cùng một khiếm khuyết kiến trúc

### 2a. Sync (Binance → DB) — `src/infrastructure/binance/client.py`

`_fetch_raw_klines()` (dòng 52-87) dùng generator phân trang thật của Binance
(`get_historical_klines_generator`, ~1000 nến/request — phần network OK), nhưng
gom **toàn bộ** kết quả generator vào một list Python duy nhất trước khi trả
về:

```python
raw_klines = []
for i, k in enumerate(generator):
    raw_klines.append(k)   # dòng 69 — giữ hết trong RAM, không giới hạn
```

`_map_to_market_data()` (dòng 96-118) sau đó dựng **list thứ hai** đầy đủ
object `MarketData` từ `raw_klines` — hai bản biểu diễn toàn bộ dữ liệu cùng
sống trong RAM một lúc.

`SyncMarketDataCommandHandler._sync_single_symbol()`
(`src/application/use_cases/sync/sync_market_data/handler.py`, dòng 70-87) chờ
`get_historical_klines()` trả về **toàn bộ** list đó rồi mới gọi
`self.repo.save_klines(klines)` **đúng một lần duy nhất** ở cuối. Không có ghi
DB theo lô trong lúc fetch.

### 2b. Backtest (DB → RAM) — `src/infrastructure/persistence/sqlalchemy_repository.py`

`get_klines()` (dòng 135-162):

```python
return [self._to_market_data_entity(row) for row in query.all()]
```

`query.all()` materialize **toàn bộ** result set SQLAlchemy thành list ORM
object trước, rồi list comprehension dựng thêm **list `MarketData` thứ hai**
đầy đủ — cùng kiểu double-list như nhánh sync. Không dùng `yield_per()` hay
server-side cursor nào để stream.

`RunStaticBacktestCommandHandler.execute()`
(`src/application/use_cases/backtest/run_static_backtest/handler.py`, dòng
89-95) load **toàn bộ** klines của khoảng backtest vào RAM một phát
(`self._repository.get_klines(...)`), không giới hạn trừ khi caller tự truyền
`limit`. Vòng `_simulate()` (dòng 178-265) tuy chỉ đọc từng `candle` một tại một
thời điểm, nhưng **buộc phải có sẵn cả list** vì cần biết `klines[-1]` cho
`force_close()` và vì `split_klines_for_out_of_sample()` cần tổng số lượng để
chia in-sample/out-of-sample trước khi chạy.

### 2c. Vì sao đáng lo với khung 1s / "Toàn bộ lịch sử"

Spike `BOT-075` từng đo thật: 7 ngày `BTCUSDT` ở khung `1s` = 604,801 dòng,
120.12 MiB `.db`. Khung 1s mới được hỗ trợ chính thức ở `BOT-112E`. Cả hai
đường dữ liệu trên đều tỷ lệ thuận RAM theo **số nến trong khoảng yêu cầu**,
không có cơ chế nào chặn trần — sync một khoảng dài hoặc backtest "Toàn bộ
lịch sử" ở 1s có thể kéo RAM lên hàng trăm MB đến hàng GB tuỳ độ dài.

---

## 3. Các Bước Khắc Phục

### 3.1. Sync — ✅ Đã sửa (2026-08-21)

Thêm `IExchangeClient.stream_historical_klines()` (`src/application/ports/i_exchange_client.py`)
— method **mới**, song song với `get_historical_klines()` cũ chứ không thay
thế nó, vì 29 chỗ khác trong repo gọi `get_historical_klines()` cho các
truy vấn nhỏ/bounded (Dashboard, Dev Board load-more, Backtest fetch panel,
Gap Repair...) không có rủi ro RAM gì — đổi interface đó sẽ là thay đổi không
cần thiết và rủi ro hồi quy cho toàn bộ 29 chỗ đó một cách vô ích.

`PythonBinanceClient.stream_historical_klines()`
(`src/infrastructure/binance/client.py`, method `_stream_raw_klines_as_market_data`)
gom nến theo lô 1000 (`_KLINE_STREAM_CHUNK_SIZE`, khớp đúng page size Binance
trả về), `yield` từng lô ngay khi đủ, không giữ toàn bộ range trong RAM.
`_fetch_raw_klines()`/`get_historical_klines()`/`_map_to_market_data()` cũ
**giữ nguyên không đổi một dòng nào** — chỉ thêm nhánh mới.

`SyncMarketDataCommandHandler._sync_single_symbol()` đổi sang tiêu thụ
`stream_historical_klines()` bằng vòng `for chunk in ...`, gọi
`repo.save_klines(chunk)` **mỗi lô**, kiểm tra `cancellation_requested()`
trước mỗi lần lưu (rộng hơn bản cũ — trước đây chỉ kiểm tra 1 lần duy nhất
sau khi fetch xong toàn bộ).

**Regression test (chạy fail đúng lý do trên code cũ trước khi sửa, xác nhận
bằng `git stash` tạm lùi `handler.py` rồi chạy lại):**
- `tests/unit/application/use_cases/test_sync_market_data_handler.py::test_sync_streams_each_chunk_to_the_db_as_it_arrives_instead_of_buffering_the_whole_range`
  — assert `save_klines` được gọi 2 lần (1 lần/lô), không phải 1 lần với toàn
  bộ dữ liệu.
- `test_cancellation_mid_stream_stops_before_saving_the_in_flight_chunk` —
  lô đã fetch trước thời điểm hủy vẫn được lưu, lô sau thời điểm hủy thì
  không.
- `tests/unit/infrastructure/binance/test_python_binance_client_unit.py::test_stream_historical_klines_yields_bounded_chunks_instead_of_one_giant_list`
  — 2005 nến giả lập → yield đúng 3 lô `[1000, 1000, 5]`, chứng minh kích
  thước lô có trần cố định, không tỷ lệ thuận theo tổng số nến.
- 6 test cũ trong `test_sync_market_data_handler.py` đổi mock target từ
  `get_historical_klines` sang `stream_historical_klines`, hành vi giữ
  nguyên. Toàn bộ 1619 test unit pass sau khi sửa, `ruff` sạch.

**Bằng chứng RAM/log thật (thêm sau khi bị hỏi lại "test check log/RAM chưa" —
đúng, ban đầu chỉ có mock call-count, chưa đủ thuyết phục):**
- `test_streaming_and_discarding_chunks_never_lets_more_than_one_chunk_stay_alive`
  — đếm **object `MarketData` sống thật** qua `gc.get_objects()` (không đo RSS
  hệ điều hành vốn nhiễu — xem mục Ghi chú) trong lúc stream 5000 nến giả lập
  rồi `del` từng chunk ngay sau khi nhận (mô phỏng đúng hành vi handler thật:
  `save_klines(chunk)` rồi bỏ qua). Assert số object sống tại đỉnh điểm
  `<= 1000` (đúng 1 chunk) và về `0` sau khi xong. **Mutation-verified**: tạm
  sửa code giữ tham chiếu mọi chunk đã yield (mô phỏng leak) → test fail đúng
  như dự đoán (`5000 <= 1000`), rồi revert lại — chứng minh test thật sự phân
  biệt được code đúng và code rò rỉ, không phải test luôn pass bất kể gì.
- `test_sync_logs_a_persisted_line_per_chunk_not_just_one_summary_at_the_end`
  — bằng chứng log thật qua `caplog` (không suy diễn từ mock): thêm dòng
  `logger.debug("[%s] Persisted chunk of %d klines (%d total so far)...")`
  vào handler (`App.SyncMarketData`, mỗi lần lưu 1 lô), test assert đúng 2
  dòng log xuất hiện với đúng số liệu từng lô — chứng minh vòng lặp thật sự
  chạy chunk-by-chunk, không chỉ dựa vào việc mock được gọi bao nhiêu lần.

### 3.2. Backtest — ✅ Đã sửa (2026-08-21)

Chọn phương án (a) đã nêu — **COUNT rồi 2 truy vấn `LIMIT`/`OFFSET` streaming**
— sau khi hỏi và được xác nhận trực tiếp, vì đây là cách duy nhất thực sự
giải quyết vấn đề RAM (phương án (b) gần như giữ nguyên hiện trạng).

`IMarketDataRepository` có thêm 2 method mới, song song với `get_klines()` cũ
(giữ nguyên không đổi — cùng nguyên tắc "thêm method mới, không sửa cái cũ"
đã dùng cho nhánh Sync ở §3.1, vì `get_klines()` còn 2 người gọi khác không
liên quan tới rủi ro RAM):
- `count_klines(...)` — `COUNT(*)` có cùng bộ filter với `get_klines()`.
- `stream_klines(...)` — như `get_klines()` nhưng trả về generator (dùng
  `yield_per()`, cùng `_KLINE_STREAM_CHUNK_SIZE=1000` như nhánh Sync), có
  thêm `offset` để lấy đúng đoạn out-of-sample tail mà không đọc lại đoạn
  in-sample đã stream trước đó.

`split_klines_for_out_of_sample()` (thao tác trên `list` đã có sẵn) giữ
nguyên; thêm `split_count_for_out_of_sample(total, ratio)` — cùng công thức
`round(total * ratio)`, chỉ khác là hoạt động trên **số đếm** thay vì trên
list đã materialize, để `RunStaticBacktestCommandHandler` biết offset/limit
cho từng pha (in-sample, out-of-sample, full-range) **trước khi** đọc bất kỳ
dòng nào. Cả 2 hàm dùng chung 1 công thức `round()` (hàm list gọi lại hàm
count) để không có 2 nơi tính split khác nhau.

`RunStaticBacktestCommandHandler.execute()`/`_simulate()` viết lại để tiêu
thụ generator thay vì `list`: `len(klines)` cũ (cho tiến độ % và cho
`klines[-1]`) được thay bằng `phase_bar_count` truyền vào tường minh và một
biến `last_candle` cập nhật trong vòng lặp. Có 1 rủi ro biên đã cân nhắc và
chấp nhận có ghi chú: `count_klines()` và `stream_klines()` là 2 truy vấn
riêng biệt (khác nhánh Sync vốn chỉ 1 lần fetch), nên về lý thuyết nếu có
ghi dữ liệu xen vào giữa 2 truy vấn thì số đếm có thể lệch — `_simulate()`
raise `RuntimeError` tường minh nếu điều đó xảy ra (thay vì crash mù trên
`None.close_price`), không âm thầm cho ra kết quả sai.

### 3.3. Còn lại

- ✅ **Regression test đo RAM có giới hạn cho nhánh Backtest** — xem mục
  "Regression test (Backtest)" bên dưới. Đếm object `MarketData` sống thật
  qua `gc.get_objects()` (không đo RSS hệ điều hành), lấy mẫu định kỳ thay vì
  mỗi dòng (mỗi dòng gọi `gc.collect()` quá chậm, ban đầu làm test chạy hàng
  phút — phát hiện lúc chạy thật, không phải suy đoán).
- **Xác nhận lại RAM baseline lúc rảnh (862.1 MB) có thực sự do đợt fetch/backtest
  trước đó để lại hay không** — vẫn chưa làm, không thuộc phạm vi nhánh code
  đã sửa (đo baseline là việc vận hành/quan sát, không phải bug code).

---

## Ghi chú

Root cause ban đầu chỉ dựa trên **đọc code tĩnh** (bước 1 của `bug-fix-rule.md`),
không có log/profiler thật đo RAM (bước 2 đầy đủ). Khi sửa nhánh Sync (§3.1),
bản đầu chỉ có test call-count-based (mock) — **bị hỏi lại đúng chỗ yếu**:
call-count chứng minh `save_klines()` được gọi đúng số lần, nhưng không
chứng minh được RAM/object thật sự không bị giữ tham chiếu ở đâu đó. Bổ sung
2 lớp bằng chứng thật, không dùng mock:
1. Đếm **object `MarketData` sống thật** qua `gc.get_objects()` (chính xác,
   tất định, không nhiễu như đo RSS hệ điều hành) trong lúc stream rồi `del`
   từng chunk — mô phỏng đúng hành vi handler thật. **Mutation-verified**:
   tạm sửa code để cố tình giữ tham chiếu mọi chunk, xác nhận test fail đúng
   như dự đoán, rồi revert — chứng minh test phân biệt được code đúng/sai,
   không phải test vô nghĩa luôn pass.
2. Log thật qua `caplog` — thêm dòng `logger.debug()` mỗi lần lưu 1 lô vào
   chính handler, test assert log thật xuất hiện đúng số lần/đúng số liệu,
   không suy diễn từ việc mock được gọi bao nhiêu lần.

Cả 2 test đã xác nhận **fail đúng lý do** trên code cũ trước khi fix, đúng
quy trình.

**Regression test (Backtest, §3.2):**
- `tests/unit/domain/backtesting/test_out_of_sample_split.py` — 5 test mới
  cho `split_count_for_out_of_sample()`, kể cả 1 test đối chiếu với hàm list
  cũ trên 50 giá trị tổng khác nhau để đảm bảo 2 công thức không bao giờ
  lệch nhau.
- `tests/integration/infrastructure/persistence/test_sqlalchemy_repository.py`:
  `test_count_klines_*` (3 test), `test_stream_klines_yields_the_same_rows_as_get_klines`,
  `test_stream_klines_offset_and_limit_select_the_out_of_sample_tail`, và
  **bằng chứng RAM thật**
  `test_stream_klines_never_holds_more_than_a_bounded_number_of_rows_live` —
  cùng kỹ thuật đếm object sống qua `gc.get_objects()` như nhánh Sync, lấy
  mẫu định kỳ (mỗi 250 dòng trong 2500 dòng) thay vì mỗi dòng. **Mutation-verified**:
  tạm sửa `stream_klines()` quay về `query.all()` (mô phỏng đúng bug gốc),
  xác nhận test fail đúng như dự đoán (`2500 < 1250` sai), rồi revert lại.
- `tests/unit/application/use_cases/test_run_static_backtest.py`,
  `tests/integration/application/test_backtest_with_broker_simulation.py`,
  `tests/unit/application/use_cases/test_ema_trend_pullback_backtest_integration.py`,
  `tests/unit/application/use_cases/test_run_realtime_backtest.py`: mọi test
  dựng `RunStaticBacktestCommandHandler` với `Mock` repository đổi sang mock
  `count_klines()`/`stream_klines()` thay vì `get_klines()` (5 file, hành vi
  test giữ nguyên — đây là các test đã có từ trước, không phải test mới).
  `tests/integration/presentation/test_backtest_user_flow.py`'s
  `_InMemoryMarketDataRepository` (test double thật implement
  `IMarketDataRepository`) thêm 2 method mới, delegate về `get_klines()` có
  sẵn.

Toàn bộ `tests/unit/` (1636 test) + `tests/sanity/` (50 test) pass sau khi
sửa, `ruff check`/`format` sạch trên mọi file đã sửa.
