# EPIC-021A — Khái niệm môi trường sàn: `MarketDataVenue`/`TradingVenue` + client factory

- **Trạng thái:** 🔴 Chưa bắt đầu
- **Repo:** Elite
- **Chặn:** mọi task còn lại của `EPIC-021`
- **Đóng bug:** [`BUG-079`](../../../bug_report/incomplete/BUG-079_binance_endpoint_config_keys_are_dead.md)

---

## 1. Bối cảnh & vấn đề thật

App không có khái niệm "đang nói chuyện với sàn nào". Client được DI dựng không tham số
([`binance_bot_module.py:231`](../../../../src/binance_bot_module.py)), nên
`PythonBinanceClient.__init__` rơi vào nhánh mặc định và tạo
`Client(api_key="", api_secret="", requests_params={"timeout": 30})` — mainnet, ẩn danh,
không có đường nào đổi được từ ngoài. Websocket giống hệt: `await AsyncClient.create()`
([`binance_websocket_service.py:110`](../../../../src/infrastructure/binance/binance_websocket_service.py)).

Hai key `BINANCE_REST_URL`/`BINANCE_WS_URL` **trông như** đang cấu hình việc đó
([`config_keys.py:11-12`](../../../../src/config/config_keys.py), `app_config.json`) nhưng không
nơi nào trong `src/` đọc chúng — đó là `BUG-079`, và nó nguy hiểm đúng theo kiểu tài liệu sai:
một người sửa `app_config.json` thành testnet sẽ tin là mình đã đổi, trong khi request vẫn bay
lên mainnet.

Tầng sanity đang phải lách bằng monkey-patch `Client.API_URL` trong `try/finally`
([`tests/sanity/conftest.py:147,153`](../../../../tests/sanity/conftest.py)). Chấp nhận được cho
một fixture; là dấu hiệu rõ ràng rằng endpoint đáng lẽ phải là **tham số dựng client**.

## 2. Thiết kế + lý do

### 2.1 Hai enum, không phải một cờ boolean

```
src/domain/value_objects/market_data_venue.py   # MAINNET_PUBLIC | FUTURES_TESTNET
src/domain/value_objects/trading_venue.py       # DISABLED | FUTURES_TESTNET
```

Mỗi enum một file: khác vòng đời, khác người quyết định, và `TradingVenue` mang một luật an toàn
mà `MarketDataVenue` không có (ADR §3 — **không có** member `MAINNET`). Gộp hai enum vào một file
sẽ khiến luật đó trông như một chi tiết cấu hình. `architecture-rule.md` §5.

Vì sao là hai enum chứ không một cờ `testnet: bool`: ADR §2. Vì sao chúng buộc phải dẫn tới hai
**instance client** chứ không hai tham số: ADR §2.1 — `python-binance` chỉ có một cờ `testnet`
cho toàn bộ `Client`, đổi endpoint của mọi nhóm API cùng lúc (`base_client.py:251,274,285`;
`streams.py:128-130`).

### 2.2 Port + factory

```
src/application/ports/i_exchange_session_factory.py   # ABC: create_market_data_client() / create_trading_client()
src/infrastructure/binance/exchange_session_factory.py
src/infrastructure/binance/binance_endpoints.py       # bảng venue -> (rest_url, ws_url, testnet_flag)
```

`abc.ABC`, không `Protocol`: không rơi vào ba lý do ngoại lệ ở `architecture-rule.md` §2.1.

Factory là **chỗ duy nhất** trong toàn repo được phép gọi `Client(...)`/`AsyncClient.create(...)`.
Khoá bằng một test quét `ast` (khuôn có sẵn: `test_backtest_view_contract.py` của `EPIC-013B`) —
không phải bằng một dòng ghi chú.

### 2.3 Cắt config chết, không giữ lại "cho tương thích"

`BINANCE_REST_URL`/`BINANCE_WS_URL` bị **xoá** khỏi `config_keys.py` và `app_config.json`, thay
bằng `EXCHANGE_MARKET_DATA_VENUE` và `EXCHANGE_TRADING_VENUE`. Giữ lại key cũ "phòng khi ai đó
dùng" chính là cách một config chết sống thêm một năm nữa.

### 2.4 Sanity tier chuyển sang đúng cơ chế này

`tests/sanity/conftest.py` bỏ monkey-patch `Client.API_URL`, thay bằng inject một venue trỏ tới
fake server qua chính factory. Fake server **giữ nguyên** — nó vẫn là thứ chứng minh
`PythonBinanceClient` thật chạy đủ mọi dòng (`EPIC-009`'s ADR). Chỉ đường trỏ endpoint là đổi.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/domain/value_objects/market_data_venue.py` | **Mới** — enum + docstring nêu ràng buộc ADR §2 |
| `src/domain/value_objects/trading_venue.py` | **Mới** — enum, docstring ghi rõ vì sao không có `MAINNET` |
| `src/application/ports/i_exchange_session_factory.py` | **Mới** — port |
| `src/infrastructure/binance/binance_endpoints.py` | **Mới** — ánh xạ venue → endpoint + cờ `testnet` |
| `src/infrastructure/binance/exchange_session_factory.py` | **Mới** — implement, nơi duy nhất gọi `Client(...)` |
| `src/infrastructure/binance/client.py` | Ctor nhận session đã dựng thay vì tự tạo `Client` mặc định |
| `src/infrastructure/binance/binance_websocket_service.py` | `AsyncClient.create()` → lấy từ factory (giữ nguyên toàn bộ logic reconnect/cancel) |
| `src/binance_bot_module.py` | Đăng ký factory; `IExchangeClient` dựng qua factory theo venue đã cấu hình |
| `src/config/config_keys.py`, `src/config/app_config.json` | Xoá 2 key chết, thêm 2 key venue |
| `tests/sanity/conftest.py` | Bỏ monkey-patch `Client.API_URL`, trỏ fake server qua factory |

## 4. Kiểm thử

- **Unit:** mỗi venue trả đúng endpoint và đúng cờ `testnet`; `TradingVenue` không có member nào
  ánh xạ tới host mainnet (test này là hiện thân của ADR §3 — nó phải đỏ nếu ai đó thêm member).
- **Unit:** `PythonBinanceClient` dựng từ factory không tự tạo `Client` nào.
- **Sanity:** tier hiện tại vẫn xanh **và** vẫn im lặng (`diagnostic_guard`) sau khi bỏ
  monkey-patch — đây là bằng chứng cơ chế mới thay được cơ chế cũ, không phải chỉ "test vẫn pass".
- **Guard (`ast`):** không file nào ngoài `exchange_session_factory.py` gọi `Client(`/`AsyncClient.create(`.
  Verify hai chiều: pass sạch, và đỏ khi cố tình chèn một lời gọi vào file khác.
- **Regression cho `BUG-079`:** một test khẳng định không còn key nào trong `app_config.json` mà
  `src/` không đọc — chặn cả lớp lỗi, không chỉ hai key này.

## 5. Mốc chạy được

`scripts/epic021a_venue_probe.py` — in ra endpoint thật mà factory dựng cho **từng** venue, rồi
`ping` mỗi cái. Chạy được **không cần key**:

```bash
PYTHONPATH=. python Sagittarius_Elite_Warrior/scripts/epic021a_venue_probe.py
```

```text
MARKET_DATA  MAINNET_PUBLIC   https://api.binance.com/api             testnet=False  ping OK   42ms
MARKET_DATA  FUTURES_TESTNET  https://testnet.binancefuture.com/fapi  testnet=True   ping OK  191ms
TRADING      DISABLED         (không dựng client)
TRADING      FUTURES_TESTNET  https://testnet.binancefuture.com/fapi  testnet=True   ping OK  188ms
```

Đây chính là thứ `BUG-079` khiến không ai kiểm được hôm nay: hai dòng URL **khác nhau** là bằng
chứng cấu hình thật sự điều khiển endpoint. Kèm theo: `python src/main.py --self-check` (tầng
out-of-process của `EPIC-009`) phải vẫn thoát 0.
