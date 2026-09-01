# EPIC-021C — Metadata Futures vào production + policy làm tròn khối lượng/giá

- **Trạng thái:** ✅ Xong
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021A` · **Chặn:** `EPIC-021E`

---

## 1. Bối cảnh & vấn đề thật

Sàn từ chối lệnh sai bước nhảy bằng `-1013` (`LOT_SIZE`, `PRICE_FILTER`, `MIN_NOTIONAL`). Một bot
không làm tròn theo `stepSize` sẽ **không đặt được lệnh nào**, và triệu chứng của nó (một mã lỗi
số) không nói gì cho người đọc lần đầu.

Repo đã có gần đủ hạ tầng cho việc này từ `BOT-095E1` — entity `SymbolMarketMetadata`, port
`ISymbolMarketMetadataCache`, cache in-memory thread-safe, và parser
`parse_binance_symbol_metadata` ([`market_metadata_parser.py:57`](../../../../src/infrastructure/binance/market_metadata_parser.py)).
**Production không gọi parser đó một lần nào** — chỉ `tests/unit/infrastructure/binance/test_market_metadata_parser.py`
gọi. Đây không phải "thiếu tính năng", mà là một mảnh hạ tầng đã dựng xong rồi bị bỏ quên; task
này nối nó vào, không viết lại.

Thêm một điểm khác biệt thật: parser hiện đọc payload **spot** `exchangeInfo`. Futures
(`/fapi/v1/exchangeInfo`) có thêm `quantityPrecision`, `pricePrecision`, và bảng đòn bẩy — thiếu
chúng thì khối lượng vẫn có thể sai ở chữ số thập phân cuối.

## 2. Thiết kế + lý do

### 2.1 Tách metadata futures khỏi metadata spot — cùng tầng, khác nội dung

```
src/domain/entities/futures_symbol_metadata.py       # step_size, tick_size, min_notional,
                                                     # quantity_precision, price_precision, max_leverage
src/infrastructure/binance/futures_metadata_parser.py
```

Không nhồi thêm field futures vào `SymbolMarketMetadata`: nó đang phục vụ mô hình broker của
backtest, và thêm field chỉ-futures vào đó sẽ buộc mọi call site backtest phải hiểu một khái
niệm chúng không dùng. Hai file cùng nằm `infrastructure/binance/` vì **cùng abstraction level**
(cùng là parser payload sàn) — `architecture-rule.md` §5 cấm trộn *khác* level, không cấm hai
thứ ngang hàng ở cạnh nhau.

### 2.2 Làm tròn là **domain policy thuần**, không phải helper trong adapter

```
src/domain/policies/order_quantity_rounding_policy.py
```

Cùng chỗ, cùng hình dạng với `OrderMatchingPolicy`/`FeeCalculatorPolicy`/`MarginRiskPolicy` đã
có. Lý do bắt buộc là domain: đây là logic **quyết định lệnh nào hợp lệ**, có bờ vực rõ ràng
(đúng ở `minNotional`, sai ở dưới nó một xu), và phải test được không cần mạng. Nhét nó vào
adapter là đúng thứ khiến `PaperExchange` và live tính khác nhau.

Ba phép, tách bạch:

1. `round_quantity_down(qty, step_size)` — **luôn làm tròn xuống**. Làm tròn lên có thể vượt
   margin khả dụng và bị từ chối; làm tròn xuống chỉ khiến lệnh nhỏ hơn dự định.
2. `round_price_to_tick(price, tick_size, side)` — làm tròn theo hướng **có lợi cho việc khớp**
   (BUY xuống, SELL lên) hoặc bảo toàn, chốt tường minh trong docstring.
3. `is_notional_sufficient(qty, price, min_notional)` — trả về quyết định có tên, không phải
   `bool` trần đi lang thang.

Dùng số thập phân đúng cách: `stepSize = "0.001"` phải được xử lý bằng `Decimal`, không phải
`float`. Bẫy 2 ở `ONBOARDING.md` §8 (so sánh float) đã có tiền lệ thật trong repo này.

### 2.3 Nạp lúc nào

Metadata nạp **một lần khi chọn symbol để giao dịch**, cache theo symbol, và làm mới khi
`EPIC-021D` kiểm tra kết nối. Không gọi `exchangeInfo` mỗi lệnh — payload đó nặng và có rate
limit riêng.

### 2.4 Sửa phạm vi, phát hiện lúc code thật (2026-09-01)

**Bỏ `maxLeverage` khỏi entity/parser.** Bản kế hoạch gốc (§5 dưới, bản cũ) có cột `maxLeverage`
trong bảng in mẫu. Khi code thật: đòn bẩy tối đa **không nằm trong** `exchangeInfo` — nó đến từ
một endpoint hoàn toàn khác, `GET /fapi/v1/leverageBracket`, và endpoint đó cần **key đã ký**
(không public như `exchangeInfo`). Dựng thêm một lời gọi ký request ở đúng task được note là
"chặn bởi `021A`" (không `021B`) sẽ kéo theo `TradingVenue`/credentials mà task này cố tình
không cần tới. Đòn bẩy thuộc về chỗ nó thực sự được dùng — lúc đặt lệnh (`021E`/`021F`), không
phải lúc làm tròn khối lượng.

**`futures_metadata_provider.py` không "dùng cache sẵn có" theo nghĩa đen.** `ISymbolMarketMetadataCache`
(`BOT-095E1`) hard-type vào `SymbolMarketMetadata` (entity spot) — cache lại `FuturesSymbolMetadata`
qua đúng port đó là nói dối ở tầng kiểu dữ liệu. Thay vào đó: `IFuturesSymbolMetadataCache` +
`InMemoryFuturesSymbolMetadataCache` — **cùng hình dạng**, file riêng, đúng tinh thần "cùng
abstraction level, khác nội dung" mà §2.1 đã áp dụng cho parser.

**`ExchangeSessionFactory` cần thêm một method,** `create_futures_metadata_client()` — trả về
`Client` thô (không phải `IExchangeClient`), luôn `testnet=True`, **bỏ qua** `market_data_venue`
đã cấu hình. Lý do: metadata cho việc đặt lệnh futures phải luôn tới từ đúng sàn lệnh sẽ đi
(Futures Testnet — ADR §3, `TradingVenue` không có member `MAINNET`), không phụ thuộc venue
**chart** người dùng đang chọn (`MarketDataVenue`, có thể là `MAINNET_PUBLIC`). Vẫn nằm trong
`exchange_session_factory.py` nên không phá bất biến "chỉ file này gọi `Client(...)`".

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/domain/entities/futures_symbol_metadata.py` | **Mới** — entity (không có `max_leverage`, xem §2.4) |
| `src/domain/value_objects/order_side.py` | **Mới** — `BUY`/`SELL`, hướng làm tròn giá cần biết chiều lệnh |
| `src/domain/policies/order_quantity_rounding_policy.py` | **Mới** — policy thuần, `Decimal` |
| `src/infrastructure/binance/futures_metadata_parser.py` | **Mới** — parse `/fapi/v1/exchangeInfo` |
| `src/application/ports/i_futures_symbol_metadata_cache.py` | **Mới** — port cache, song song `ISymbolMarketMetadataCache` (không dùng chung, xem §2.4) |
| `src/infrastructure/persistence/futures_symbol_metadata_cache.py` | **Mới** — cache in-memory thread-safe |
| `src/application/ports/i_market_metadata_provider.py` | **Mới** — port đọc metadata theo symbol (`get_or_fetch`/`refresh`) |
| `src/infrastructure/binance/futures_metadata_provider.py` | **Mới** — implement |
| `src/infrastructure/binance/exchange_session_factory.py` | + `create_futures_metadata_client()`, xem §2.4 |
| `tests/sanity/binance_fake_server.py` | `/fapi/v1/exchangeInfo` có filter thật, không chỉ symbol/status |
| `src/binance_bot_module.py` | Đăng ký cache + provider |

## 4. Kiểm thử

- **Unit (BVA, `testing-rule.md` §2):** biên `minNotional` — đúng bằng, dưới 1 xu, trên 1 xu.
  `stepSize` với 0/1/8 chữ số thập phân. Khối lượng dưới bước nhỏ nhất → 0, không âm.
- **Mutation-verify:** đối chiếu trực tiếp kết quả "làm tròn xuống" với "làm tròn gần nhất" trên
  cùng input biên — phải khác nhau, chứng minh test không xanh vô nghĩa (`BOT-106A`).
- **Unit:** parser với payload futures tĩnh (fixture, không gọi mạng), gồm symbol thiếu filter →
  không ném, trả giá trị mặc định có tên; cả `"notional"` (futures) lẫn `"minNotional"` (spot,
  chấp nhận phòng hờ) cho `MIN_NOTIONAL`.
- **Unit:** cache — round-trip, không phân biệt hoa/thường, overwrite, clear.
- **Unit:** provider — cache miss fetch cả catalog (không chỉ 1 symbol); cache hit không gọi
  mạng lần hai; symbol không có trong catalog → `None`, không phải metadata mặc định;
  `refresh()` luôn gọi mạng kể cả cache đang ấm.
- **Integration:** provider đọc qua `tests/sanity/binance_fake_server.py` thật (round-trip HTTP
  cục bộ, không qua mạng) → giá trị filter đúng, cache hit lần hai không cần server còn sống.
- **Sanity:** tier vẫn xanh sau khi đăng ký cache + provider vào DI thật.

## 5. Mốc chạy được

`scripts/epic021c_metadata_probe.py` — kéo metadata thật rồi **cho xem policy làm tròn quyết định
gì**, đây mới là thứ đáng nhìn (bảng filter thô thì đọc trên web Binance cũng có). Không có cột
`maxLeverage` — xem lý do cắt ở §2.4.

```bash
PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
    Sagittarius_Elite_Warrior/scripts/epic021c_metadata_probe.py \
    --symbol BTCUSDT --price 64000 --qty 0.0137 --qty 0.0011 --offline
```

Chạy thật (2026-09-01, phiên dev remote này — `--offline` bắt buộc, egress tới
`*.binance.*` bị chặn tầng chính sách, giống mọi mốc khác của epic này):

```text
BTCUSDT  stepSize=0.001  tickSize=0.10  minNotional=100  qtyPrec=3
  qty 0.0137 → 0.013   notional 832.00 USDT  ≥  100 → HỢP LỆ
  qty 0.0011 → 0.001   notional 64.00 USDT  <  100 → TỪ CHỐI (MIN_NOTIONAL)
```

`--offline` trỏ `tests/sanity/binance_fake_server.py` (filter thật, không phải chỉ symbol/status
— mở rộng ở task này). Trên máy có mạng thật, bỏ `--offline` để kéo catalog Futures Testnet
thật.

Giá trị thật của mốc này: `-1013` là mã lỗi mà bot sẽ đâm vào nếu policy sai, và nó xuất hiện
**sau khi** đã gửi lệnh. Ở đây anh thấy quyết định làm tròn **trước** khi có bất kỳ lệnh nào.

## 6. Ghi chú triển khai (2026-09-01)

Ba sửa phạm vi so với bản thiết kế gốc, tất cả chi tiết ở §2.4: bỏ `maxLeverage` (endpoint khác,
cần key, không phải job của task này); cache futures là port/impl riêng chứ không dùng chung
`ISymbolMarketMetadataCache` (sai kiểu dữ liệu); `ExchangeSessionFactory` có thêm
`create_futures_metadata_client()` (metadata luôn từ Futures Testnet, độc lập `MarketDataVenue`
đang cấu hình).

**Quyết định thiết kế đáng chú ý khác:**

- `round_price_to_tick` cần biết **chiều lệnh** (BUY làm tròn xuống, SELL làm tròn lên) — không
  có enum sẵn khớp nghĩa "chiều gửi lệnh REST" (`SignalAction` mang cả `HOLD`/`SHORT`/`COVER`,
  một từ vựng tín hiệu chiến lược, không phải tham số `side` của Binance). Thêm
  `domain/value_objects/order_side.py` (`BUY`/`SELL`) — VO nhỏ, đúng phạm vi, không tái dùng gượng
  ép một enum không khớp nghĩa.
- `is_notional_sufficient` trả về `NotionalCheck` (enum `SUFFICIENT`/`INSUFFICIENT`) đúng như
  §2.2 yêu cầu — "quyết định có tên, không phải bool trần".
- Dùng `Decimal(str(x))` không bao giờ `Decimal(float)` trong parser — chuyển thẳng từ `float`
  tái tạo lại sai số nhị phân trước khi `Decimal` kịp bắt đầu.

**Chưa đối chiếu được với payload futures thật đang sống** — cùng giới hạn `EPIC-021A` §2.2b đã
nêu (egress chặn toàn bộ `*.binance.*`, xác nhận 6 host). Shape filter (`PRICE_FILTER`/
`LOT_SIZE`/`MIN_NOTIONAL`, khoá `"notional"` cho futures khác `"minNotional"` của spot) viết từ
tài liệu đã biết, parser xử lý phòng thủ (thiếu filter → mặc định có tên, không ném) — nên rủi ro
nếu shape thật lệch là suy giảm về mặc định, không phải crash. Nên đối chiếu lại một lần trên máy
có mạng trước khi coi đây là đóng vĩnh viễn.

**Bằng chứng verify cuối cùng** (đúng 4 cổng `ci-rule.md`, chạy sau khi hoàn tất toàn bộ):

```
ruff check src tests scripts tools    → 3 lỗi, cả 3 pre-existing (scripts/shutdown_*probe.py,
                                          chưa từng đụng tới)
ruff format --check src tests scripts tools → 869 files already formatted
mypy (src+scripts, một lệnh) → Success: no issues found in 184 source files
pytest tests/sanity                    → 24 passed
pytest tests/unit + tests/integration  → 1 failed (pre-existing, không liên quan:
                                          test_pan_preview_moves_only_the_data_region_not_the_axes),
                                          3039 passed, 4 skipped, coverage 95%
```
