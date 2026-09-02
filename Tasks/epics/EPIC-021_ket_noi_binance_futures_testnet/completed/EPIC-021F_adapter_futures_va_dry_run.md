# EPIC-021F — Adapter `BinanceFuturesTradingClient` + dry-run qua `/fapi/v1/order/test`

- **Trạng thái:** ✅ Hoàn thành (2026-09-02)
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021D`, `EPIC-021E` · **Chặn:** `EPIC-021G`, `EPIC-021J`

---

## 1. Bối cảnh & vấn đề thật

Đây là task đầu tiên gửi một payload lệnh lên sàn. Rủi ro thật của nó không phải "code sai" mà
là **không phân biệt được sai ở đâu**: payload thiếu field, sai `positionSide`, sai bước nhảy,
sai chữ ký, hay sai quyền của key — tất cả đều hiện ra dưới dạng một mã lỗi số.

Binance Futures có một endpoint sinh ra đúng để giải quyết chuyện này:
`POST /fapi/v1/order/test` (`futures_create_test_order` trong `python-binance`) — sàn **validate
đầy đủ** payload và chữ ký nhưng **không** đưa lệnh vào matching engine. Task này dừng lại ở đó.
Không có lệnh nào khớp trong `EPIC-021F`.

## 2. Thiết kế + lý do

### 2.1 Adapter hiện thực `ITradingClient`, sống ở Infrastructure

```
src/infrastructure/binance/futures_trading_client.py
```

Dựng từ session của `EPIC-021A`'s factory (luôn `testnet=True` trong epic này) và credentials
của `EPIC-021B`. Đây là **instance duy nhất** trong app được phép ký request (ADR §2.1).

### 2.2 Chế độ dry-run là một **tham số của adapter**, không phải một `if` rải rác

```python
class OrderSubmissionMode(Enum):
    VALIDATE_ONLY = "VALIDATE_ONLY"   # POST /fapi/v1/order/test
    LIVE = "LIVE"                     # POST /fapi/v1/order
```

Lý do là enum chứ không phải `bool dry_run`: hai chế độ này gọi **hai endpoint khác nhau**, và
một `bool` trong chữ ký hàm đọc ở call site thành `place_order(order, True)` — không ai đọc ra
được `True` nghĩa là gì. Mặc định của `EPIC-021F` là `VALIDATE_ONLY`; `EPIC-021G` mới mở `LIVE`.

### 2.3 Ánh xạ domain → payload là một mapper riêng, test được không cần mạng

```
src/infrastructure/binance/futures_order_payload_mapper.py
```

`Order` (domain) → `dict` params của `futures_create_order`. Tách khỏi adapter vì nó là logic
thuần, và là chỗ dễ sai nhất: `side` (BUY/SELL) và `positionSide` là **hai** field khác nhau,
`reduceOnly` không được gửi kèm ở Hedge mode, `timeInForce` chỉ hợp lệ với LIMIT, `quantity`
phải đã qua `OrderQuantityRoundingPolicy` (`EPIC-021C`).

Adapter **không tự làm tròn**: nó nhận `Order` đã hợp lệ và từ chối `Order` chưa làm tròn bằng
một lỗi có tên. Làm tròn im lặng trong adapter nghĩa là domain và sàn có hai ý kiến khác nhau về
khối lượng, và không ai biết bên nào đúng.

### 2.4 Lỗi sàn được dịch sang lỗi domain có tên

`BinanceAPIException` mang mã số. Adapter dịch chúng thành một enum
`OrderRejectionReason` (`INSUFFICIENT_MARGIN`, `LOT_SIZE`, `MIN_NOTIONAL`, `PRICE_FILTER`,
`REDUCE_ONLY_REJECTED`, `RATE_LIMIT`, `UNKNOWN`) trước khi đi lên Application. Tầng trên không
được phép biết mã số của Binance — đó là chi tiết Infrastructure.

Mã chưa nhận diện được ánh xạ `UNKNOWN` **kèm nguyên văn** để log còn dùng được, không bị nuốt.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/infrastructure/binance/futures_trading_client.py` | **Mới** — implement `ITradingClient` |
| `src/infrastructure/binance/futures_order_payload_mapper.py` | **Mới** — domain → params |
| `src/domain/trading/order_rejection_reason.py` | **Mới** — enum lý do từ chối |
| `src/domain/trading/order_submission_mode.py` | **Mới** — enum chế độ gửi |
| `src/infrastructure/binance/binance_error_translator.py` | **Mới** — mã lỗi Binance → `OrderRejectionReason` |
| `src/binance_bot_module.py` | Đăng ký `ITradingClient` (chỉ khi `TradingVenue != DISABLED`) |

## 4. Kiểm thử

- **Unit (mapper):** MARKET/LIMIT/STOP_MARKET sinh đúng bộ field; LIMIT thiếu `timeInForce` bị
  chặn; `Order` chưa làm tròn theo `stepSize` bị từ chối bằng lỗi có tên.
- **Unit (translator):** từng mã Binance thật (`-1013`, `-2019`, `-1111`, `-4164`, `-1021`) ánh
  xạ đúng; mã lạ → `UNKNOWN` **và** giữ nguyên văn.
- **Integration:** qua fake server futures (`EPIC-021J`) — `VALIDATE_ONLY` gọi đúng
  `/fapi/v1/order/test`, `LIVE` gọi `/fapi/v1/order`. Khẳng định **đường dẫn**, vì đó chính là
  thứ phân biệt "không khớp lệnh nào" với "vừa khớp một lệnh".
- **Testnet tier (opt-in):** gửi `VALIDATE_ONLY` thật lên Futures Testnet với một khối lượng hợp
  lệ → sàn trả `{}` (chấp nhận). Đây là bằng chứng chữ ký + payload đúng, thu được **mà không
  đặt lệnh nào**.
- **Guard:** không call site nào ngoài `EPIC-021G` được truyền `OrderSubmissionMode.LIVE` cho tới
  khi task đó làm; khoá bằng test `ast`, gỡ trong chính `021G`.

## 5. Mốc chạy được

**Mốc quan trọng nhất của cả epic:** chứng minh chữ ký, quyền của key và payload đều đúng —
**mà không có lệnh nào được tạo.**

```bash
PYTHONPATH=. python Sagittarius_Elite_Warrior/src/main.py order-dry-run \
  --symbol BTCUSDT --side BUY --qty 0.002 --type MARKET
```

```text
POST https://testnet.binancefuture.com/fapi/v1/order/test
payload: symbol=BTCUSDT side=BUY type=MARKET quantity=0.002
         newClientOrderId=SEW-a91f4c72e0b8  (app tự sinh, không để thư viện sinh)

Sàn CHẤP NHẬN payload.  ✔  Không có lệnh nào được tạo.
```

Ca lỗi in ra lý do đã dịch sang domain, kèm nguyên văn của sàn để còn tra được:

```text
Sàn TỪ CHỐI: LOT_SIZE
  nguyên văn: APIError(code=-1013): Quantity less than or equal to zero.
```

Sau task này, `grep -rn "OrderSubmissionMode.LIVE" src/` phải cho **0 call site** — đó là nội dung
guard ở §4, và cũng là cách anh tự kiểm rằng chưa có gì khớp được.

## 6. Ghi chú triển khai

### 6.1 `TradingVenue` chưa từng có config key + resolver thật — task này thêm

Task giả định "Đăng ký `ITradingClient` (chỉ khi `TradingVenue != DISABLED`)" như thể việc đọc
`TradingVenue` từ config đã tồn tại — thực ra chưa: chỉ có `MarketDataVenue` có
`ConfigKeys.EXCHANGE_MARKET_DATA_VENUE` + `resolve_market_data_venue()` (`EPIC-021A`).
`ConfigKeys.EXCHANGE_TRADING_VENUE` + `resolve_trading_venue()` (mặc định `DISABLED`, cùng khuôn
"cảnh báo thay vì crash khi giá trị lạ" của hàm chị em) là hai thứ mới thêm ở đây, cùng dòng
`"exchange.trading_venue": "disabled"` trong `app_config.json` để việc này hiện diện tường minh
chứ không chỉ ẩn trong fallback code.

### 6.2 Bug thật tự phát hiện, không cần commit riêng: sanity `test_every_use_case_resolves_to_a_handler` sẽ đỏ nếu không xử lý

`tests/sanity/test_composition_root.py` scan **mọi** Command/Query dưới `application/use_cases` và
resolve từng cái qua container thật, boot bằng đúng config production (`TradingVenue.DISABLED` mặc
định). `SubmitOrderCommand` cố ý chỉ resolve được khi trading bật — nên tự nhiên **sẽ** làm test đó
đỏ nếu không xử lý. Thêm `"SubmitOrderCommand"` vào `_NOT_DISPATCHED` với lý do viết rõ (đúng yêu
cầu "mọi entry cần lý do" của chính list đó): không phải "never dispatched" (nó CÓ được dispatch
thật qua `order-dry-run`), mà là "boot này tắt trading, giống mọi bản cài thật cho tới khi ai đó
bật". Chạy lại sanity thật (24/24 xanh) để xác nhận trước khi coi task xong — không đoán.

### 6.3 `-1013` không map 1-1 sang một `OrderRejectionReason` — cần đọc message text

Kế hoạch ngầm định mỗi mã lỗi Binance map đúng 1 lý do (giống khuôn `_ERROR_CODE_TO_FAILURE_KIND`
của `EPIC-021D`). Với `-1013` điều đó sai: đây là mã "filter failure" chung của Binance, dùng chung
cho `LOT_SIZE`/`PRICE_FILTER`/`MIN_NOTIONAL` — tên filter chỉ nằm trong text, không có field riêng.
`binance_error_translator.py` vì vậy có thêm một nhánh test-text-theo-thứ-tự-ưu-tiên chỉ cho mã này
(`"notional"` trước `"price"` trước `"quantity"`, để một message MIN_NOTIONAL không bị nhận nhầm
qua từ "price"/"quantity" nếu nó tình cờ xuất hiện). 4 mã còn lại (`-2019`, `-4164`, `-2022`,
`-1003`) map 1-1 qua dict như dự kiến. `-1021` (lệch đồng hồ, đã có tên riêng ở `EPIC-021D`) cố ý
**không** có trong dict — rơi về `UNKNOWN` kèm nguyên văn, vì nó là mã thật nhưng không mô tả vấn đề
nội dung lệnh.

### 6.4 Guard "0 call site" đọc theo `ast`, không theo text thô — nếu không, chính docstring giải thích luật cũng tự vi phạm luật

`grep -rn "OrderSubmissionMode.LIVE" src/` là cách tự kiểm nhanh bằng tay task đề xuất, nhưng nếu
enforce đúng y hệt bằng text thô thì bất kỳ docstring nào *giải thích* luật ("không ai được truyền
`OrderSubmissionMode.LIVE` cho tới `EPIC-021G`") cũng tự vi phạm luật nó đang mô tả — một nghịch lý
tự tham chiếu. Guard test (`test_order_submission_mode_live_is_not_used_yet.py`) vì vậy quét bằng
`ast.Attribute` (biểu thức `OrderSubmissionMode.LIVE` dùng làm giá trị thật — constructor arg, dict
key, so sánh...), bỏ qua chuỗi/docstring — đúng tinh thần "ast", đúng như tên file
`futures_trading_client.py` đã trỏ tới trước khi file guard tồn tại. `order_dry_run_formatter.py`
vẫn tránh nhắc `OrderSubmissionMode` hoàn toàn (không cả import) để giữ output của
`grep` thô sạch nhất có thể — chỉ còn 2 dòng docstring giải thích luật, không phải call site thật.

### 6.5 CLI `order-dry-run` cần y hệt bộ dây EPIC-021E đã tìm ra là thiếu ở §3

Lặp lại đúng phát hiện đã ghi ở `EPIC-021E` §6.1: `main.py`, `cli_commands.json`,
`binance_bot_module.py` đều bị đụng, dù §3 của task này chỉ liệt kê file hạ tầng. Thêm
`--price` bắt buộc (cùng lý do đã ghi ở `EPIC-021E` §6.2 — không có đường lấy giá thị trường
trong scope task này).

### 6.6 `ITradingClient` cần đủ 5 method để khởi tạo được, dù mốc chạy được chỉ cần `place_order`

`ITradingClient` là `ABC` — Python từ chối khởi tạo nếu thiếu bất kỳ abstract method nào, nên
`cancel_order`/`cancel_all_orders`/`get_open_orders`/`get_positions` đều phải có cài đặt thật, dù
mốc chạy được của task này chỉ chạm `place_order`. Đã viết thêm mapper 2 chiều
(`map_futures_order_payload_to_order`, `map_futures_position_payload_to_live_position`) cho việc
đó. `cancel_all_orders`: `futures_cancel_all_open_orders` của Binance chỉ trả một xác nhận, không
trả danh sách lệnh đã huỷ — nên đọc `get_open_orders` **trước** khi huỷ, trả lại danh sách đó như
câu trả lời tốt nhất có thể cho "lệnh nào bị ảnh hưởng".

### 6.7 Kết quả kiểm thử cuối

- Ruff (`src tests scripts tools`): sạch — 3 lỗi baseline có sẵn ở `scripts/shutdown_*_probe.py`
  (không đụng tới, xác nhận bằng `git status` rỗng trên 2 file đó); `ruff format --check` sạch.
- Mypy (`src`+`scripts`, một lệnh, từ thư mục superproject): `Success: no issues found in 213
  source files`.
- Sanity: 24 passed (đã tự tay xác nhận `SubmitOrderCommand` không làm nó đỏ, xem §6.2).
- Unit (`-n 4`): 3084 passed, 1 failed — cùng lỗi trước-đã-biết,
  `test_pan_preview_moves_only_the_data_region_not_the_axes` (chart pan/pixel, không liên quan).
- Guard: `test_order_submission_mode_live_is_not_used_yet.py` xanh; `test_only_the_session_factory_
  constructs_binance_client.py` (`EPIC-021A`) vẫn xanh (không có `Client()` mới ngoài
  `ExchangeSessionFactory`); `grep -rln "class.*ITradingClient" src/` cho đúng 1 implementer
  (`FuturesTradingClient`) + định nghĩa port.
- Chạy thật `main.py order-dry-run` và `main.py order-preview`/`exchange-status` (hồi quy) trong
  sandbox mạng bị chặn — cả ba đều thoát êm với thông báo mạng có tên, không traceback.
