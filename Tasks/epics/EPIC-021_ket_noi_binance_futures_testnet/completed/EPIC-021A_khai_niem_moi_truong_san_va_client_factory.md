# EPIC-021A — Khái niệm môi trường sàn: `MarketDataVenue`/`TradingVenue` + client factory

- **Trạng thái:** ✅ Xong
- **Repo:** Elite
- **Chặn:** mọi task còn lại của `EPIC-021`
- **Đóng bug:** [`BUG-081`](../../../bug_report/completed/BUG-081_binance_endpoint_config_keys_are_dead.md)

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
nơi nào trong `src/` đọc chúng — đó là `BUG-081`, và nó nguy hiểm đúng theo kiểu tài liệu sai:
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
src/application/ports/i_exchange_session_factory.py   # ABC: create_market_data_client() -> IExchangeClient
src/infrastructure/binance/exchange_session_factory.py
src/infrastructure/binance/binance_endpoints.py       # venue -> testnet flag + URL hiển thị (đọc lại từ chính Client, không hard-code)
```

> **Sửa phạm vi, phát hiện lúc code thật (2026-09-01):** bản thiết kế gốc còn có
> `create_trading_client()` trên port này, trả thẳng `binance.client.Client`. Đó là vi phạm layering
> — `application/ports/` không được biết kiểu dữ liệu của SDK hạ tầng (`architecture-rule.md` §3,
> cùng tinh thần Shared Kernel). `ITradingClient` (kiểu trả về đúng đắn) chưa tồn tại tới `EPIC-021E`.
> Factory của `021A` **chỉ có `create_market_data_client()`**; việc dựng session cho giao dịch dời
> sang `021E`/`021F`, khi có kiểu Application-safe để trả về. Mốc chạy được ở §5 sửa theo — bớt dòng
> `TRADING`, chỉ còn `MARKET_DATA`.

`abc.ABC`, không `Protocol`: không rơi vào ba lý do ngoại lệ ở `architecture-rule.md` §2.1.

Factory là **chỗ duy nhất** trong toàn repo được phép gọi `Client(...)`/`AsyncClient.create(...)`.
Khoá bằng một test quét `ast` (khuôn có sẵn: `test_backtest_view_contract.py` của `EPIC-013B`) —
không phải bằng một dòng ghi chú.

### 2.2b Klines futures dùng lại đúng pipeline của `python-binance`, không viết lại

Đọc thẳng mã nguồn `python-binance` (không đoán): `get_historical_klines_generator()` **đã có sẵn**
tham số `klines_type: HistoricalKlinesType` (`SPOT` mặc định, `FUTURES` khi cần), và cả hai cùng chạy
qua **một** `_historical_klines_generator()` → `_klines()` → rẽ `self.get_klines()` hoặc
`self.futures_klines()` theo `klines_type`. Cùng một vòng lặp phân trang, cùng một chỗ parse hàng —
đây là bằng chứng từ chính thư viện rằng khối lượng dòng OHLCV tương thích giữa hai họ, không phải
suy đoán của agent.

Hệ quả thiết kế: `PythonBinanceClient` **không cần** một class con/kline-source riêng cho futures.
Chỉ cần constructor nhận thêm `market_data_venue: MarketDataVenue`, ánh xạ sang
`HistoricalKlinesType` bằng một `dict` hằng số (không if/else rải rác), rồi truyền `klines_type=`
vào đúng 2 lời gọi generator đã có. Toàn bộ retry/backoff/cancellation (`BUG-063`) và
`_map_to_market_data()` giữ **nguyên si** — không sửa một dòng.

**Không mở rộng theo `get_exchange_info()`/`get_available_symbols()`.** Hai method đó (spot) và
`futures_exchange_info()` là **hai method độc lập, không dùng chung helper nào** trong
`python-binance` — payload thật sự khác hình dạng (filter futures có `quantityPrecision`,
`pricePrecision`, không giống bộ filter spot). Đó chính xác là lý do `EPIC-021C` tồn tại như một
task riêng (`FuturesSymbolMetadata`, `futures_metadata_parser.py`). `get_available_symbols()` ở
`021A` **giữ nguyên, chỉ đọc spot** — venue chỉ đổi nguồn **klines**, không đổi nguồn symbol catalog.
Việc đó chưa xong tới khi `021C` làm.

**Đã re-verify được từ chính source đã cài (2026-09-01), không phải "tin theo trí nhớ"** — nhưng
**chưa** đối chiếu được với tài liệu Binance sống: mọi domain `*.binance.*` bị chặn egress ở tầng
chính sách của phiên remote này (xác nhận trên cả 6 host, kể cả trang docs). Bằng chứng ở đây tới
từ đọc mã nguồn `python-binance` đã cài trong venv — đủ để tin cho vòng đầu, nhưng nên đối chiếu lại
với dữ liệu klines futures thật một lần trên máy có mạng, trước khi coi đây là đã đóng vĩnh viễn.

### 2.2c Live stream (`AsyncClient`) không đi qua cùng factory — lý do là kỹ thuật, không phải lười

`AsyncClient.create(...)` **là `async`**, phải chạy trong coroutine của chính
`BinanceWebsocketService._run_stream()`. Một factory method đồng bộ không gọi được nó; bọc thành
`async def` trong `IExchangeSessionFactory` cũng không giúp gì — nơi gọi vẫn phải `await` đúng bên
trong coroutine đó, tức là gần như cùng một dòng code đang có sẵn.

**Quyết định:** `BinanceWebsocketService` nhận thẳng `market_data_venue: MarketDataVenue` qua
constructor, và dòng `await AsyncClient.create()` sẵn có nhận thêm `testnet=resolve_testnet_flag(venue)`
— sửa đúng bug ("luôn mainnet") mà không ép một khớp nối không tự nhiên. Guard `ast` ở §2.3 vì vậy
**chỉ khoá `Client(`** (đồng bộ), không khoá `AsyncClient.create(` — hai cơ chế khác nhau, khoá
chung sẽ ép sai một trong hai.

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
- **Regression cho `BUG-081`:** một test khẳng định không còn key nào trong `app_config.json` mà
  `src/` không đọc — chặn cả lớp lỗi, không chỉ hai key này.

## 5. Mốc chạy được

`scripts/epic021a_venue_probe.py` — dựng client thật qua `ExchangeSessionFactory` (không tự gọi
`Client(...)` — script cũng bị AST guard ở §2.2 khoá), in ra endpoint đã resolve cho **từng**
venue, rồi thử `ping` mỗi cái. Chạy được **không cần key**:

```bash
PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
    Sagittarius_Elite_Warrior/scripts/epic021a_venue_probe.py
```

Chạy thật (2026-09-01, phiên dev remote này):

```text
MARKET_DATA  MAINNET_PUBLIC   klines: https://api.binance.com/api            (SPOT   ) testnet=False  [ping skipped: ProxyError]
                              symbols: https://api.binance.com/api            (SPOT — 021C mới đổi)
MARKET_DATA  FUTURES_TESTNET  klines: https://testnet.binancefuture.com/fapi (FUTURES) testnet=True  [ping skipped: ProxyError]
                              symbols: https://testnet.binance.vision/api     (SPOT — 021C mới đổi)
```

Chỉ **2** venue, không có dòng `TRADING` — factory của `021A` chỉ dựng market-data client (xem sửa
phạm vi ở §2.2). Cột `klines`/`symbols` tách rõ vì cùng một venue nhưng hai lời gọi đi hai host khác
nhau (§2.2b) — gộp một cột "URL" duy nhất sẽ là chính kiểu tài liệu nói dối mà `BUG-081` đang sửa.

**Không `ping` được trong phiên phát triển remote này** — egress bị chặn ở tầng chính sách tới mọi
domain `*.binance.*` (xác nhận cả `api.binance.com` lẫn `testnet.binancefuture.com`, lỗi
`ProxyError`), không phải lỗi tạm thời. Script vẫn dựng client thật qua factory, bắt riêng lỗi
ping và in đúng URL đã resolve (`Client.API_URL`/`API_TESTNET_URL`/`FUTURES_URL`/
`FUTURES_TESTNET_URL`, format hệt như `Client.__init__` tự làm — đọc từ thư viện đã cài, không
hard-code trong script). Hai dòng `klines` khác nhau đúng host mainnet vs. testnet — đó đã là đủ
bằng chứng cấu hình thật sự điều khiển endpoint. Trên máy có mạng thật, dòng `[ping skipped: ...]`
biến mất và ping thật chạy — không bắt buộc để đóng task.

Cổng CI đầy đủ chạy sau khi thêm script này (`ruff check`/`ruff format` scope `src tests tools
scripts`, `mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases` trên
`src`+`scripts` một lệnh, `pytest` full suite + sanity) — sạch, không hồi quy mới; xem "Ghi chú
triển khai" bên dưới cho số liệu đầy đủ.

## 6. Ghi chú triển khai (2026-09-01)

Thiết kế ở §2 giữ nguyên; những điều dưới đây là thứ chỉ lộ ra lúc code thật, không phải kế
hoạch ban đầu.

**Sửa phạm vi so với bản thiết kế gốc:**

- Bỏ `create_trading_client()` khỏi `IExchangeSessionFactory` — xem note tại chỗ ở §2.2 (rò rỉ
  kiểu SDK hạ tầng vào `application/ports/`, `architecture-rule.md` §3). Dời sang `021E`/`021F`.
- `binance_websocket_service.py`'s `AsyncClient.create()` **không** đi qua factory — lý do kỹ
  thuật ở §2.2c (async construction phải nằm trong đúng coroutine gọi nó).

**Bug thật tìm thấy khi code, ngoài `BUG-081` đã biết trước:**

- DI đăng ký `IExchangeClient` bằng **instance đã dựng sẵn** (gọi `create_market_data_client()`
  ngay lúc đăng ký) làm mọi test boot app đều ping mạng thật → 45 test lỗi `ProxyError`. Sửa
  bằng lambda lười (`container.singleton(IExchangeClient, lambda _c:
  session_factory.create_market_data_client())`) — đúng idiom sẵn có của `StdLibContainer`,
  không phải cơ chế mới. Nếu merge mà không bắt bằng test suite đầy đủ, đây sẽ là một bản
  `BUG-045` mới, ẩn kỹ hơn (ping xảy ra ở path lười, không phải boot).
- Kline futures dùng lại nguyên `get_historical_klines_generator(klines_type=...)` sẵn có trong
  `python-binance` thay vì viết lại — xác nhận bằng cách đọc source đã cài
  (`_historical_klines_generator` → `_klines()` dùng chung 1 pipeline cho cả `SPOT`/`FUTURES`).
  Chi tiết + giới hạn (chưa đối chiếu được với API sống do egress bị chặn) ở §2.2b.
- `pytest`'s `python_functions` mặc định là glob `test*` (không cần dấu `_`) — hàm
  `testnet_flag_for` bị pytest thu thập nhầm thành test (`fixture 'venue' not found`). Đổi tên
  thành `resolve_testnet_flag`, khớp quy ước `resolve_market_data_venue` cùng module.
- Guard `ast` bản đầu chỉ kiểm import `from binance.client import Client`, báo sai
  `client.py` (chỉ import để dùng làm type annotation `client: Client`, không construct). Sửa:
  guard yêu cầu **cả** import lẫn `ast.Call(func=Name(id="Client"))` thật; verify bằng test
  mutation tự-xác nhận guard bắt được vi phạm thật và bỏ qua đúng trường hợp chỉ có annotation.
- `tests/sanity/binance_fake_server.py` đổi kiểu trả về từ `str` sang dataclass `FakeServerUrls`
  (thêm route futures) — quên cập nhật `conftest.py`'s `booted_app` theo, gây
  `AttributeError: 'FakeServerUrls' object has no attribute 'format'` ở 3 use case. Chỉ bắt được
  ở lần chạy **toàn bộ** sanity suite cuối cùng, sau khi tưởng đã xong — lý do §4 yêu cầu chạy
  lại full suite một lần nữa trước khi báo cáo, không tin vào lần chạy từng phần.

**Cố ý để lại, ghi rõ chứ không im lặng bỏ qua:**

- Chưa boot sanity tier cho venue `FUTURES_TESTNET` — thêm một boot thứ hai sẽ lặp lại đúng lỗi
  thiết kế mà `EPIC-009` đã sửa (tier vốn giới hạn đúng 1 boot/phiên). `021J` sẽ có tier riêng
  (`tests/testnet/`, opt-in).
- Chưa đối chiếu shape kline futures với API Binance sống — egress bị chặn toàn bộ domain
  `*.binance.*` trong phiên dev remote này (xác nhận cả 6 host, kể cả trang docs). Bằng chứng
  hiện có chỉ từ đọc source thư viện đã cài, không phải gọi mạng thật (§2.2b).
- `EPIC-021C` (metadata futures), `021E`/`021F` (trading client) chưa động tới — đúng thứ tự
  §4 của README epic.

**Bằng chứng verify cuối cùng** (đúng 4 cổng `ci-rule.md` yêu cầu, chạy sau khi thêm
`scripts/epic021a_venue_probe.py`):

```
ruff check src tests tools scripts    → 3 lỗi, cả 3 pre-existing (scripts/shutdown_*probe.py,
                                          chưa từng đụng tới)
ruff format --check src tests tools scripts → 846 files already formatted
mypy (config đúng ci-local.ps1: --config-file pyproject.toml --namespace-packages
      --explicit-package-bases, src+scripts một lệnh) → Success: no issues found in 170 source files
pytest tests/sanity                    → 24 passed
pytest tests/unit + tests/integration  → 1 failed, 2966 passed, 4 skipped, coverage 95% —
                                          thất bại duy nhất pre-existing, không liên quan
                                          (test_pan_preview_moves_only_the_data_region_not_the_axes)
```
