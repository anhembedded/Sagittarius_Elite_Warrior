# BUG-025 — Không có buffer/streaming ở đường dữ liệu Sync (Binance→DB) và Backtest (DB→RAM): RAM phình theo độ dài khoảng, không có trần

**Reported:** 2026-08-20
**Severity:** 🟡 **P2** (chưa crash trong điều kiện thông thường, nhưng scale kém — đặc biệt với khung 1s vừa thêm ở `BOT-112E` và tuỳ chọn "Toàn bộ lịch sử")
**Status:** 🔴 **Open (Đã root-cause bằng đọc code, chưa sửa)**

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

## 3. Các Bước Đề Xuất Khắc Phục (Suggested Next Steps)

1. **Sync — ghi theo lô (chunked write) thay vì gom hết rồi ghi 1 lần:**
   Đổi `_fetch_raw_klines()`/`get_historical_klines()` thành generator/iterator
   trả về theo lô (ví dụ mỗi 1000 nến — đúng theo trang Binance đã trả), và
   `SyncMarketDataCommandHandler` gọi `repo.save_klines(chunk)` mỗi lô rồi xả,
   thay vì gom hết vào một `klines: list` rồi ghi 1 lần ở cuối.
2. **Backtest — đọc DB theo streaming/server-side cursor:**
   Đổi `get_klines()` sang trả về iterator dùng `yield_per()` (hoặc tương
   đương) thay vì `query.all()`, và refactor `_simulate()` để tiêu thụ iterator
   trực tiếp (chỉ cần giữ lại nến cuối cùng cho `force_close()`, không cần giữ
   cả list). Ràng buộc khó hơn: `split_klines_for_out_of_sample()` hiện cần
   biết tổng số nến trước khi chạy — cần quyết định giữa (a) query 2 lần
   (COUNT rồi stream), hay (b) buffer toàn bộ chỉ cho nhánh out-of-sample và
   giữ nguyên full-load, việc này cần bàn thiết kế trước khi code chứ không tự
   quyết.
3. **Viết regression test đo RAM có giới hạn:**
   Test tạo dataset lớn giả lập (ví dụ 500k+ nến trong DB test), chạy qua cả
   hai đường, và assert bằng cách nào đó peak RAM/objects sống không tỷ lệ
   thuận tuyến tính không giới hạn theo cỡ dataset (ví dụ đếm số object
   `MarketData` sống cùng lúc qua `tracemalloc` hoặc `gc` thay vì đo RSS hệ
   điều hành vốn nhiễu).
4. **Xác nhận lại RAM baseline lúc rảnh (862.1 MB) có thực sự do đợt fetch/backtest
   trước đó để lại hay không** — trước khi coi đây là bằng chứng bổ sung của
   chính bug này, nên đo lại RSS ngay sau khi app khởi động (chưa sync/backtest
   lần nào) để có baseline sạch so sánh.

---

## Ghi chú

Không root-cause bằng cách chạy thật + đo log/profiler — root-cause hiện tại
chỉ dựa trên **đọc code tĩnh** (đúng bước 1 của `bug-fix-rule.md`, nhưng thiếu
bước 2: bằng chứng log/profiler thật cho việc reproduce). Trước khi sửa, nên
đo RAM thật bằng `tracemalloc`/profiler trên một sync hoặc backtest khoảng dài
thật để có con số cụ thể, tránh sửa dựa trên suy luận thuần tuý.
