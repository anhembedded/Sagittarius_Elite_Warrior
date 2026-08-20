# BUG-025 — Không có buffer/streaming ở đường dữ liệu Sync (Binance→DB) và Backtest (DB→RAM): RAM phình theo độ dài khoảng, không có trần

**Reported:** 2026-08-20
**Severity:** 🟡 **P2** (chưa crash trong điều kiện thông thường, nhưng scale kém — đặc biệt với khung 1s vừa thêm ở `BOT-112E` và tuỳ chọn "Toàn bộ lịch sử")
**Status:** 🟡 **Mở một phần (2026-08-21) — nhánh Sync đã sửa + regression-tested; nhánh Backtest vẫn mở, cần bàn thiết kế trước khi code (xem §3.2)**

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

### 3.2. Backtest — 🔴 Vẫn mở, cần bàn thiết kế trước khi code

`get_klines()` (DB → RAM) và `RunStaticBacktestCommandHandler` chưa đổi.
Đổi `get_klines()` sang trả về iterator dùng `yield_per()` (hoặc tương đương)
thay vì `query.all()`, và refactor `_simulate()` để tiêu thụ iterator trực
tiếp (chỉ cần giữ lại nến cuối cùng cho `force_close()`, không cần giữ cả
list). Ràng buộc khó hơn nhánh sync: `split_klines_for_out_of_sample()` cần
biết tổng số nến **trước khi chạy** để chia in-sample/out-of-sample — cần
quyết định giữa (a) query 2 lần (COUNT rồi stream), hay (b) buffer toàn bộ
chỉ riêng cho nhánh out-of-sample và giữ nguyên full-load cho nhánh chính.
Chưa tự quyết, cần hỏi trước khi code.

### 3.3. Còn lại

- **Viết regression test đo RAM có giới hạn cho nhánh Backtest** khi làm
  §3.2 — test tạo dataset lớn giả lập (ví dụ 500k+ nến trong DB test), assert
  bằng cách nào đó peak RAM/objects sống không tỷ lệ thuận tuyến tính không
  giới hạn theo cỡ dataset (ví dụ đếm số object `MarketData` sống cùng lúc
  qua `tracemalloc`/`gc` thay vì đo RSS hệ điều hành vốn nhiễu). Nhánh Sync
  đã có test kiểu này ở §3.1 (`test_streaming_and_discarding_chunks_...`) —
  dùng làm mẫu khi viết cho Backtest.
- **Xác nhận lại RAM baseline lúc rảnh (862.1 MB) có thực sự do đợt fetch/backtest
  trước đó để lại hay không** — trước khi coi đây là bằng chứng bổ sung của
  chính bug này, nên đo lại RSS ngay sau khi app khởi động (chưa sync/backtest
  lần nào) để có baseline sạch so sánh. Vẫn chưa làm.

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
quy trình. Nhánh Backtest (§3.2) vẫn giữ nguyên khuyến nghị đo RAM baseline
thật trước khi bắt tay sửa, và nên viết test kiểu (1) ở trên khi làm — xem
mẫu ở `test_streaming_and_discarding_chunks_never_lets_more_than_one_chunk_stay_alive`.
