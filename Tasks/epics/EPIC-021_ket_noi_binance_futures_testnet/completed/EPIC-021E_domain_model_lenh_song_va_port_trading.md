# EPIC-021E — Domain model lệnh sống + port `ITradingClient` (không chạm mạng)

- **Trạng thái:** ✅ Hoàn thành (2026-09-02)
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021C` · **Chặn:** `EPIC-021F`

---

## 1. Bối cảnh & vấn đề thật

Repo có `Trade` — nhưng `Trade` là **kết quả của backtest**: một giao dịch đã đóng, có entry và
exit, dùng để tính metrics. Vị thế đang mở chỉ tồn tại dưới dạng `_OpenPosition`, một dataclass
**private** bên trong [`paper_exchange.py`](../../../../src/domain/backtesting/paper_exchange.py).

Không có gì mô tả một **lệnh đang sống**: đã gửi nhưng chưa khớp, khớp một phần, bị sàn từ chối,
bị huỷ. Đó là toàn bộ phần trạng thái mà giao dịch thật thêm vào so với backtest — trong backtest
mọi lệnh khớp ngay lập tức theo định nghĩa.

Task này viết mô hình đó, **không chạm mạng một dòng nào**. Sau nó, code có đủ từ vựng để nói về
lệnh; `EPIC-021F` mới nối dây.

## 2. Thiết kế + lý do

### 2.1 Mỗi khái niệm một file (`architecture-rule.md` §5)

```
src/domain/trading/order.py                # Order (frozen)
src/domain/trading/order_status.py         # NEW | PARTIALLY_FILLED | FILLED | CANCELED | REJECTED | EXPIRED
src/domain/trading/order_type.py           # MARKET | LIMIT | STOP_MARKET | TAKE_PROFIT_MARKET
src/domain/trading/time_in_force.py        # GTC | IOC | FOK
src/domain/trading/live_position.py        # LivePosition (đang mở, có liquidation_price đọc từ sàn)
src/domain/trading/client_order_id.py      # sinh id có tiền tố app + idempotency
```

Thư mục `domain/trading/` riêng, không nhét vào `domain/backtesting/`: khác vòng đời hoàn toàn
(một bên mô phỏng, một bên là trạng thái thật ngoài tiến trình này). Câu phân xử nhanh của
`architecture-rule.md` §5.5 — *"đổi `Trade` có bắt buộc phải sửa `Order` không?"* — trả lời
**không**.

### 2.2 `client_order_id` do **app sinh**, không để `python-binance` tự sinh

`futures_create_order` tự chèn `newClientOrderId = CONTRACT_ORDER_PREFIX + uuid22()` khi caller
không truyền (`client.py:7657-7658` của thư viện). Nhận id do thư viện sinh nghĩa là app không
biết trước id của lệnh mình vừa gửi — và khi mất kết nối giữa chừng, không có cách nào hỏi sàn
*"lệnh của tôi có vào không"*. Vì vậy id do app sinh, có tiền tố nhận diện, và được ghi lại
**trước** khi gửi.

Đây cũng chính là hình dạng idempotency: gửi lại cùng `client_order_id` sau timeout không tạo
lệnh thứ hai.

### 2.3 Bốn event, kế thừa `BaseEvent`

```
src/domain/events/order_submitted_event.py
src/domain/events/order_filled_event.py
src/domain/events/order_rejected_event.py
src/domain/events/position_changed_event.py
```

`BaseEvent` là một trong đúng 2 ký hiệu Engine được phép xuất hiện trong `domain/`
(`architecture-rule.md` §3, Shared Kernel). Lưu ý đánh đổi đã ghi ở `Handover.md` §3: dataclass
kế thừa `BaseEvent` **không** `frozen` được — làm theo đúng khuôn 4 event hiện có, kèm docstring,
đừng "sửa lại cho đúng".

`OrderFilledEvent` là thứ `BOT-009`'s Trade Markers Manager đã chờ từ lâu — giữ đúng tên đó.

### 2.4 `ITradingClient` là port **riêng**, không mở rộng `IExchangeClient`

```
src/application/ports/i_trading_client.py
```

Interface Segregation (`architecture-rule.md` §1, ADR §2.1): hai port nói chuyện với hai kết nối
khác nhau, một cần key một không. Thêm method giao dịch vào `IExchangeClient` sẽ buộc mọi
implementer market-data hiện có (kể cả trong `tests/` và `scripts/`) phải cập nhật theo — đúng
khuôn `BUG-026`. Khi thêm port mới, vẫn phải grep implementer ở **cả ba** `src/`, `scripts/`,
`tests/` (bẫy 11, `ONBOARDING.md` §8).

Method: `place_order`, `cancel_order`, `cancel_all_orders`, `get_open_orders`, `get_positions`.
`abc.ABC` — không rơi vào ba ngoại lệ `Protocol` ở §2.1.

### 2.5 Cái chưa mô hình hoá, và cách nó hiện diện (ADR §6)

- **Funding rate:** không tính vào PnL. Test khoá điều đó + docstring ghi điều kiện gỡ.
- **Liquidation:** `LivePosition.liquidation_price` chỉ **đọc từ sàn**, có type riêng
  (`LiquidationPrice`) để không ai nhầm là app tự tính.
- **Hedge mode:** `LivePosition` giả định One-way; docstring nói rõ, và `EPIC-021D` đã chặn từ
  đầu vào.

## 3. Thay đổi theo từng file

Toàn bộ là file **mới** dưới `src/domain/trading/`, `src/domain/events/`,
`src/application/ports/i_trading_client.py`. Không sửa file nào đang chạy — đó là một phần lý do
task này đứng riêng: nó không thể làm hỏng gì.

## 4. Kiểm thử

- **Unit:** ma trận chuyển trạng thái `OrderStatus` — chuyển hợp lệ đi được, chuyển vô lý
  (`FILLED` → `NEW`) bị chặn. Không viết test cho trạng thái mà chính kiểu dữ liệu đã khiến bất
  khả thi (`testing-rule.md` §2 cấm padding coverage).
- **Unit:** `client_order_id` duy nhất, có tiền tố, độ dài trong giới hạn Binance (36 ký tự).
- **Unit (khoá đánh đổi):** `test_live_pnl_excludes_funding_fees` — khoá hành vi hiện tại kèm lý
  do, đúng khuôn `test_signal_generated_event_is_no_longer_frozen` của `EPIC-008F`.
- **Unit:** mọi event kế thừa `BaseEvent` và vào được catalog của Engine.
- **Guard:** grep implementer của `ITradingClient` ở `src/`+`scripts/`+`tests/`; `mypy` chạy
  `src`+`scripts` chung một lệnh (`ci-rule.md` §1).

## 5. Mốc chạy được

Task này cố ý không chạm mạng, nên mốc của nó là **xem domain quyết định gì** trước khi có adapter:

```bash
PYTHONPATH=. python Sagittarius_Elite_Warrior/src/main.py order-preview \
  --symbol BTCUSDT --side BUY --qty 0.0137 --type MARKET
```

```text
Order đã chuẩn hoá
  client_order_id : SEW-a91f4c72e0b8
  symbol/side     : BTCUSDT / BUY   position_side=BOTH (One-way)
  type/quantity   : MARKET / 0.013  (làm tròn xuống từ 0.0137, step 0.001)
  notional ước tính: 832.00 USDT     ≥ minNotional 100 ✔
Trạng thái: SẴN SÀNG GỬI  (chưa gửi — task này không có đường ra mạng)
```

Và một ca bị từ chối, để thấy lỗi có tên chứ không phải mã số:

```text
Trạng thái: TỪ CHỐI  MIN_NOTIONAL — 64.00 USDT < 100.00 USDT
```

`--json` xuất ra đúng object domain để so bằng mắt với payload mà `EPIC-021F` sẽ dựng. Hai bước
tách nhau chính là để khi payload sai, anh biết ngay sai ở domain hay ở mapper.

## 6. Ghi chú triển khai

### 6.1 §3 tự nhận sai — mốc chạy được buộc phải sửa file đang chạy

§3 viết "Toàn bộ là file mới... Không sửa file nào đang chạy". Sai ngay từ chính §5 của task này:
một `main.py order-preview` thật cần đăng ký lệnh CLI, và pattern đăng ký lệnh CLI đã thiết lập
từ `EPIC-021D` luôn đụng đúng 3 file có sẵn: `src/main.py` (thêm `elif`), `src/config/
cli_commands.json` (thêm entry), và `src/binance_bot_module.py` (bind Query→Handler vào DI
container). Đã sửa cả ba, cộng thêm `src/presentation/cli/cli_parser.py` (thêm hỗ trợ
`"action": "store_true"` cho cờ `--json` — JSON config trước đó chỉ có `type`/`required`/
`default`/`help`/`choices`, chưa hỗ trợ cờ boolean thuần). Đây là lần thứ năm liên tiếp
(`EPIC-021A`→`E`) tài liệu kế hoạch viết trước khi code đánh giá thấp diện sửa đổi thật của mốc
chạy được — mẫu hình đã quá rõ để ghi lại một lần nữa ở đây thay vì lặp lại chi tiết.

### 6.2 `--price` là cờ bắt buộc, không có trong lệnh mẫu của §5

Lệnh mẫu ở §5 không có `--price`, nhưng dòng "notional ước tính: 832.00 USDT" chỉ tính được nếu
có giá tham chiếu — 0.013 × 64000 = 832.00. Task này (và domain nó viết) tường minh "không chạm
mạng một dòng nào", nên không có đường lấy giá thị trường trực tiếp; việc đó thuộc luồng thực thi
thật của `EPIC-021F`. Quyết định: `--price` là cờ **bắt buộc**, người gọi tự cung cấp giá tham
chiếu. Với `OrderType.LIMIT` giá này đồng thời là giá đặt lệnh; với các loại khác chỉ dùng để ước
tính notional.

### 6.3 Phát hiện thật khi chạy CLI thật (không phải chỉ test có mock): `IMarketMetadataProvider` không có hợp đồng "never raises"

Chạy thật `main.py order-preview --symbol BTCUSDT --side BUY --qty 0.0137 --type MARKET --price
64000` trong sandbox này (mọi domain `*.binance.*` bị chặn egress) cho log:

```
App - ERROR - PreviewOrderQuery failed: HTTPSConnectionPool(host='testnet.binance.vision',
port=443): Max retries exceeded with url: /api/v3/ping (Caused by ProxyError(...))
Không lấy được luật giao dịch (exchange rules) cho BTCUSDT — kiểm tra kết nối mạng rồi thử lại.
```

Đúng như thiết kế — không crash — nhưng đáng ghi lại: khác `ITradingAccountReader` (`EPIC-021D`,
hợp đồng "không bao giờ raise"), `IMarketMetadataProvider.get_or_fetch()`/`refresh()`
(`EPIC-021C`) **không** hứa điều đó, và `FuturesMetadataProvider.refresh()` thật sự không có
`try/except` nào quanh việc dựng `Client(...)` (tự ping Spot Testnet lúc khởi tạo, cùng cơ chế
`BUG-045`/`EPIC-021D` §4 đã nêu) hay quanh `futures_exchange_info()`. Không phải lỗi vỡ hợp đồng
— cache trống + không mạng vẫn nên "raise" theo đúng chữ ký hàm hiện tại — nhưng đây là lần đầu có
call site (`execute_order_preview`) gọi thẳng cổng này mà không qua một adapter đã tự nuốt lỗi.
Vì vậy CLI này bọc *toàn bộ* `app.dispatch(PreviewOrderQuery, ...)` trong một `try/except
(BinanceAPIException, BinanceRequestException, RequestException)`, không chỉ bọc lệnh gọi cụ thể
— cùng bài học construction-time-ping đã rút ra ở `EPIC-021D` §4, áp dụng lại ở một port khác.
Không tạo `BUG-xxx` mới: không hợp đồng nào bị vi phạm, và điểm gọi duy nhất (đúng file này) đã xử
lý đúng ngay từ đầu — nhưng ghi lại ở đây để `EPIC-021F` (người tiếp theo gọi cổng này cho luồng
thực thi thật) biết trước, không phải tự tìm lại bằng chạy thật lần nữa.

### 6.4 `PositionSide` (LONG/SHORT, `BOT-050`) được tái dùng cho `LivePosition`, không tạo type mới

Task liệt kê 6 file mới dưới `domain/trading/`, không có file `position_side.py` riêng — và
`domain/value_objects/position_side.py` (LONG/SHORT) đã tồn tại sẵn từ backtest (`BOT-050`).
`LivePosition.side` là **property tính từ dấu của `position_amt`** (số có dấu sàn trả về), không
phải field lưu riêng — tránh đúng lớp lỗi "hai bản sao của cùng một sự thật có thể lệch nhau" mà
`position_side` (param gửi lên sàn, luôn `BOTH` ở One-way) với `side` (hướng vị thế thật) dễ nhầm
nếu tách thành hai field độc lập.

### 6.5 Kết quả kiểm thử cuối

- Ruff (`src tests scripts tools`): sạch — 3 lỗi baseline có sẵn ở `scripts/shutdown_*_probe.py`
  (không đụng tới, xác nhận bằng `git status` rỗng trên 2 file đó).
- Mypy (`src`+`scripts`, một lệnh, đúng cách gọi `ONBOARDING.md` §5 — chạy từ thư mục superproject
  `/home/user`, không phải từ `Sagittarius_Elite_Warrior/`): `Success: no issues found in 205
  source files`.
- Sanity: 24 passed.
- Unit (`-n 4`): 3040 passed, 1 failed — `test_pan_preview_moves_only_the_data_region_not_the_axes`
  (chart pan/pixel test ở `presentation/ui/components/`, không liên quan gì tới `domain/trading/`
  hay CLI mới; xác nhận lại bằng chạy riêng lẻ, cùng thất bại đã ghi nhận ở `EPIC-021D`).
- Guard: `grep -rln "ITradingClient" src scripts tests` → chỉ khớp docstring/comment, chưa có
  implementer thật nào (đúng như kỳ vọng — đó là việc của `EPIC-021F`).
- Chạy thật `main.py order-preview` (xem §6.3) và một ca `--qty notanumber` để xác nhận thoát êm
  thay vì crash khi tham số không phải số.
