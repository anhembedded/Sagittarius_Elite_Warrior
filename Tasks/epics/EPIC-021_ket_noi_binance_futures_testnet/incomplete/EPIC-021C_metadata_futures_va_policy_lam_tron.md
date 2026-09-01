# EPIC-021C — Metadata Futures vào production + policy làm tròn khối lượng/giá

- **Trạng thái:** 🔴 Chưa bắt đầu
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

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/domain/entities/futures_symbol_metadata.py` | **Mới** — entity |
| `src/domain/policies/order_quantity_rounding_policy.py` | **Mới** — policy thuần, `Decimal` |
| `src/infrastructure/binance/futures_metadata_parser.py` | **Mới** — parse `/fapi/v1/exchangeInfo` |
| `src/application/ports/i_market_metadata_provider.py` | **Mới** — port đọc metadata theo symbol |
| `src/infrastructure/binance/futures_metadata_provider.py` | **Mới** — implement, dùng cache sẵn có |
| `src/binance_bot_module.py` | Đăng ký provider |

## 4. Kiểm thử

- **Unit (BVA, `testing-rule.md` §2):** biên `minNotional` — đúng bằng, dưới 1 tick, trên 1 tick.
  `stepSize` với 0/1/8 chữ số thập phân. Khối lượng nhỏ hơn `minQty` → 0, không phải số âm.
- **Mutation-verify bắt buộc:** đổi làm tròn xuống thành làm tròn gần nhất → test phải đỏ. Nếu
  vẫn xanh thì test chưa chứng minh gì (đúng bài học `BOT-106A`).
- **Unit:** parser với payload futures thật đã lưu (fixture tĩnh, không gọi mạng), gồm cả symbol
  thiếu filter → không ném, trả giá trị mặc định có tên.
- **Integration:** provider đọc qua fake server (`EPIC-021J` mở rộng) → cache hit lần hai không
  phát request thứ hai.

## 5. Mốc chạy được

`scripts/epic021c_metadata_probe.py` — kéo metadata thật rồi **cho xem policy làm tròn quyết định
gì**, đây mới là thứ đáng nhìn (bảng filter thô thì đọc trên web Binance cũng có):

```bash
PYTHONPATH=. python Sagittarius_Elite_Warrior/scripts/epic021c_metadata_probe.py \
  --symbol BTCUSDT --price 64000 --qty 0.0137 --qty 0.0011
```

```text
BTCUSDT  stepSize=0.001  tickSize=0.10  minNotional=100  qtyPrec=3  maxLeverage=125
  qty 0.0137 → 0.013   notional 832.00 USDT  ≥ 100  → HỢP LỆ
  qty 0.0011 → 0.001   notional  64.00 USDT  <  100 → TỪ CHỐI (MIN_NOTIONAL)
```

Chạy được với `--offline` trỏ fake server (`EPIC-021J`) để không cần mạng.

Giá trị thật của mốc này: `-1013` là mã lỗi mà bot sẽ đâm vào nếu policy sai, và nó xuất hiện
**sau khi** đã gửi lệnh. Ở đây anh thấy quyết định làm tròn **trước** khi có bất kỳ lệnh nào.
