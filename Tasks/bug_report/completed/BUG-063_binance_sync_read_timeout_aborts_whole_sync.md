# BUG-063 — `SyncMarketDataCommand` mất hết dữ liệu vừa tải khi Binance trả lời chậm

| Trường | Giá trị |
| :--- | :--- |
| **Trạng thái** | ✅ **Đóng 2026-08-27 — root cause tìm ra và đo được** (§Root cause) |
| **Mức độ** | 🟡 P2 — không mất dữ liệu vĩnh viễn (tự tiếp tục ở lần sync sau), nhưng mỗi lần dính lỗi là mất trắng phần đã tải trong lần gọi đó và người dùng phải tự bấm sync lại |
| **Phát hiện** | 2026-08-27, user báo qua log thật khi thử backtest `HISTORICAL_TICK` (nến 1 giây) trên `VolumeSpikeFlowStrategy` |

## Symptom

Log thật do user cung cấp, sau khi chuyển UI backtest sang chế độ `HISTORICAL_TICK`
và yêu cầu đồng bộ dữ liệu 1 giây cho ETHUSDT từ 2026-08-21 đến 2026-08-27 (~6 ngày,
~518.400 nến):

```
2026-08-27 15:41:13,722 - App.ExchangeClient - INFO - Streaming historical klines for ETHUSDT at 1s from 20 Aug 2026 08:40:13 to 27 Aug 2026 08:40:14
2026-08-27 15:41:59,268 - App.ExchangeClient - ERROR - Failed to stream historical klines for ETHUSDT: HTTPSConnectionPool(host='api.binance.com', port=443): Read timed out. (read timeout=10)
2026-08-27 15:41:59,269 - App - ERROR - SyncMarketDataCommand failed: HTTPSConnectionPool(host='api.binance.com', port=443): Read timed out. (read timeout=10)
```

kèm traceback đầy đủ xuống tận `requests.exceptions.ReadTimeout` trong
`urllib3/connectionpool.py`, qua `binance/client.py` → `client.py:134` (dòng cũ,
`_stream_raw_klines_as_market_data`) → `sync_market_data/handler.py:77`.

**Quan trọng**: đoạn log *trước* lỗi này cho thấy `VolumeSpikeFlowStrategy` (chiến
lược mới, `BOT` không có số vì task tạo chiến lược không đi qua `Tasks/backlog/`)
chạy đúng, không liên quan — 2 lần backtest (1m, 5m) hoàn tất bình thường với kết
quả thật (lỗ -9.41% và -2.51% out-of-sample). Lỗi chỉ xảy ra ở bước đồng bộ dữ liệu
1 giây, hoàn toàn tách biệt khỏi code chiến lược.

## Root cause

`src/infrastructure/binance/client.py:49` (dòng cũ) — `Client(api_key, api_secret)`
không set `requests_params`, nên dùng timeout đọc mặc định của chính thư viện
`python-binance`: **10 giây** (khớp chính xác `read timeout=10` trong log).

Đồng bộ 1 giây trên 1 khoảng nhiều ngày cần **hàng trăm request REST tuần tự**
(`_KLINE_STREAM_CHUNK_SIZE = 1000` nến/request → 6 ngày = ~519 request). Thư viện
`python-binance` **không có retry nào ở tầng generator** — 1 request chậm hơn 10
giây trong số ~519 request là đủ để `ReadTimeout` bung ra khỏi
`get_historical_klines_generator(...)`, phá toàn bộ vòng lặp `for k in generator`
ở cả `_fetch_raw_klines` và `_stream_raw_klines_as_market_data`.

Hậu quả thực tế trong log: nến đã tải được trong buffer (chưa đủ
`_KLINE_STREAM_CHUNK_SIZE` để yield) bị **mất hoàn toàn**, không lưu vào DB — lãng
phí băng thông và thời gian đã bỏ ra, dù không mất dữ liệu vĩnh viễn (lần sync kế
tiếp tự tiếp tục từ điểm phủ gap cuối cùng trong DB, nhờ cơ chế `BUG-025` lưu từng
chunk ngay khi tải xong).

## Fix

`src/infrastructure/binance/client.py`:

1. **Nâng timeout đọc mặc định lên 30 giây** (`_DEFAULT_REQUEST_TIMEOUT_SECONDS`),
   truyền qua `requests_params={"timeout": ...}` khi tự dựng `Client`. Vẫn có giới
   hạn — một kết nối thật sự chết vẫn báo lỗi trong thời gian chấp nhận được — chỉ
   không còn coi 1 response chậm bình thường là thảm hoạ.
2. **Thêm `_generate_raw_klines_with_retry()`** — helper generator dùng chung cho
   cả `_fetch_raw_klines` và `_stream_raw_klines_as_market_data`, thay thế việc
   gọi thẳng `self.client.get_historical_klines_generator(...)`:
   - Bắt `requests.exceptions.RequestException` (bao gồm `ReadTimeout`,
     `ConnectionError`, `ConnectTimeout`).
   - **Tiếp tục từ nến cuối cùng đã nhận được** (`close_time + 1ms`, đúng quy ước
     đã có ở `BUG-022`), **không** tải lại từ `start_str` gốc — không lãng phí
     request đã trả tiền, không tải trùng dữ liệu đã lưu.
   - Backoff luỹ thừa (`2s, 4s, 8s`), tối đa `_MAX_TRANSIENT_RETRIES = 3` lần lỗi
     **liên tiếp không có tiến triển**. Mỗi nến nhận được reset bộ đếm — kết nối
     chập chờn nhưng vẫn tiến được thì không bao giờ tự bỏ cuộc (người dùng huỷ
     bằng nút Cancel là giới hạn duy nhất); kết nối chết hẳn thì báo lỗi sau tối đa
     4 lần thử, không treo vô hạn.
   - `_cancellable_sleep()` — sleep chia nhỏ theo
     `_CANCELLATION_POLL_INTERVAL_SEC = 0.05`, cùng kiểu với
     `ThreadSafeRateLimiter.acquire()` đã có sẵn — huỷ giữa lúc đang chờ backoff
     có tác dụng ngay, không phải đợi hết cả khoảng chờ.
3. **`requirements.txt`**: thêm `requests` — trước đây chỉ là dependency gián tiếp
   qua `python-binance`, giờ import trực tiếp để bắt đúng loại exception.

## Regression test

`tests/unit/infrastructure/binance/test_python_binance_client_unit.py` — 3 test mới,
xác nhận đỏ trước khi sửa (lỗi `ImportError` do hằng số `_DEFAULT_REQUEST_TIMEOUT_SECONDS`
chưa tồn tại — đúng lý do, không phải lỗi ngẫu nhiên), xanh sau khi sửa:

- `test_stream_historical_klines_resumes_from_the_last_kline_after_a_transient_network_error`
  — mô phỏng đúng kịch bản log: 2 nến tải được rồi `ReadTimeout`, assert cả 5 nến
  (2 cũ + 3 mới) đều có trong kết quả cuối, và lần gọi lại dùng đúng
  `close_time + 1ms` của nến cuối, không phải `start_str` gốc.
- `test_stream_historical_klines_gives_up_after_repeated_transient_errors_with_no_progress`
  — kết nối chết hẳn (không nến nào lọt qua) phải báo lỗi sau đúng
  `_MAX_TRANSIENT_RETRIES + 1` lần gọi, không lặp vô hạn.
- `test_stream_historical_klines_cancellation_during_retry_backoff_stops_immediately`
  — huỷ trong lúc đang chờ backoff phải dừng ngay, không đợi hết delay.

Cũng cập nhật `test_no_injected_client_falls_back_to_constructing_the_real_sdk_client`
để assert đúng `requests_params` mới truyền vào `Client(...)`.

12 test cũ của cùng file (bao gồm 2 test cancellation cũ đếm chính xác số lần gọi
`cancellation_requested()`) vẫn xanh nguyên — logic huỷ được dồn vào đúng 1 chỗ
trong helper mới, không nhân đôi số lần kiểm tra.

**Verify đầy đủ trên máy thật** (venv dựng bằng `uv`, Python 3.12.3, Engine repo
clone riêng để `sagittarius_engine` import được):
- `ruff check` / `ruff format --check` trên `src tests tools`: sạch.
- `mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases
  src scripts` (chạy đúng từ repo root, `src` + `scripts` cùng lệnh): sạch, 155 file.
- Unit + Sanity đầy đủ: **2349 passed** (2325 unit + 24 sanity), 0 dòng
  `FAILED|ERROR|Traceback|ResourceWarning` trong log đầy đủ (`> file 2>&1`, không
  `| tail`). Còn đúng 1 `RuntimeWarning` ở `test_log_panel.py` — đã xác nhận có
  sẵn từ trước khi sửa bug này (không liên quan).
