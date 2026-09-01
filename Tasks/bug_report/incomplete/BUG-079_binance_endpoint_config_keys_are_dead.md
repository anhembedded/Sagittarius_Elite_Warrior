# BUG-079 — `BINANCE_REST_URL`/`BINANCE_WS_URL` là config chết: sửa chúng không đổi được gì

- **Trạng thái:** 🔴 Đang mở
- **Mức độ:** 🟡 P3 (chưa gây lỗi runtime; gây hiểu sai nghiêm trọng cho người cấu hình)
- **Ngày báo:** 2026-09-01
- **Phát hiện khi:** khảo sát code để lập [`EPIC-021`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/README.md)
- **Sẽ đóng bởi:** [`EPIC-021A`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/incomplete/EPIC-021A_khai_niem_moi_truong_san_va_client_factory.md)

---

## 1. Symptom

`app_config.json` khai hai endpoint, và `ConfigKeys` có hằng số cho cả hai
([`config_keys.py:11-12`](../../../src/config/config_keys.py)):

```json
"BINANCE_WS_URL":   "wss://stream.binance.com:9443",
"BINANCE_REST_URL": "https://api.binance.com",
```

Nhìn vào đây, kết luận tự nhiên — và **sai** — là: đổi hai dòng này sang testnet thì app sẽ nói
chuyện với testnet. Thực tế app vẫn bay thẳng lên mainnet, không có bất kỳ dấu hiệu nào cho thấy
cấu hình bị bỏ qua.

Đây đúng loại lỗi mà repo này đã trả giá nhiều lần: một phát biểu sai nằm im, không có gì đỏ, cho
tới khi ai đó tin nó.

## 2. Root cause

Không nơi nào trong `src/` đọc hai key này:

```bash
grep -rn "BINANCE_REST_URL\|BINANCE_WS_URL" --include=*.py src/
# → chỉ có 2 dòng KHAI BÁO trong config_keys.py. Không có lời gọi config.get(...) nào.
```

Lý do cơ chế: `PythonBinanceClient` tự dựng `Client(api_key, api_secret, requests_params=...)`
([`client.py:73-79`](../../../src/infrastructure/binance/client.py)) và `python-binance` khi đó
dùng hằng số nội bộ `Client.API_URL = "https://api{}.binance.{}/api"`. Websocket cũng vậy:
`await AsyncClient.create()` ([`binance_websocket_service.py:110`](../../../src/infrastructure/binance/binance_websocket_service.py))
→ `BinanceSocketManager` lấy `STREAM_URL` của chính thư viện. Endpoint **chưa bao giờ** là tham số
đến từ config của app.

**Bằng chứng bổ sung cho thấy sự thiếu vắng này gây tốn công thật:** tầng sanity muốn trỏ client
sang fake server đã phải monkey-patch class attribute toàn cục trong `try/finally`
([`tests/sanity/conftest.py:147,153`](../../../tests/sanity/conftest.py)):

```python
Client.API_URL = fake_url
...
Client.API_URL = real_client_api_url
```

Chấp nhận được trong một fixture; nhưng nó tồn tại **chính vì** không có đường cấu hình endpoint
hợp lệ.

## 3. Fix (thuộc `EPIC-021A`)

Xoá hẳn hai key chết, thay bằng `EXCHANGE_MARKET_DATA_VENUE` / `EXCHANGE_TRADING_VENUE` được
`ExchangeSessionFactory` đọc thật và biến thành endpoint + cờ `testnet` khi dựng client.

**Không giữ lại hai key cũ "cho tương thích"** — giữ chính là cách một config chết sống thêm một
năm nữa. Không có gì đọc chúng thì cũng không có gì gãy khi xoá.

Sau khi có cơ chế thật, `tests/sanity/conftest.py` bỏ monkey-patch và trỏ fake server qua chính
factory đó.

## 4. Regression test

- **Chặn bug này:** khẳng định mỗi `MarketDataVenue`/`TradingVenue` dựng ra client với đúng
  base URL và đúng cờ `testnet` — tức endpoint thật sự đến từ cấu hình.
- **Chặn cả lớp lỗi (quan trọng hơn):** một test duyệt mọi key trong `app_config.json` và khẳng
  định mỗi key đều có ít nhất một nơi đọc trong `src/`. Hôm nay repo có **2** key chết; test này
  làm chúng không thể tích tụ thêm trong im lặng. Verify hai chiều: pass sạch sau khi xoá, và đỏ
  khi cố tình thêm một key không ai đọc.
