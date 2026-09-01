# EPIC-021F — Adapter `BinanceFuturesTradingClient` + dry-run qua `/fapi/v1/order/test`

- **Trạng thái:** 🔴 Chưa bắt đầu
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
