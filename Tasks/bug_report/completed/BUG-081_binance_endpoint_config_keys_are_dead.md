# BUG-081 — `BINANCE_REST_URL`/`BINANCE_WS_URL` là config chết: sửa chúng không đổi được gì

- **Trạng thái:** ✅ Đã sửa
- **Mức độ:** 🟡 P3 (chưa gây lỗi runtime; gây hiểu sai nghiêm trọng cho người cấu hình)
- **Ngày báo:** 2026-09-01
- **Ngày sửa:** 2026-09-01
- **Phát hiện khi:** khảo sát code để lập [`EPIC-021`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/README.md)
- **Đóng bởi:** [`EPIC-021A`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/completed/EPIC-021A_khai_niem_moi_truong_san_va_client_factory.md)

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

## 5. Đã sửa như thế nào (`EPIC-021A`)

Fix đúng như §3 mô tả: xoá `BINANCE_REST_URL`/`BINANCE_WS_URL` khỏi `ConfigKeys` và
`app_config.json`, thay bằng `EXCHANGE_MARKET_DATA_VENUE` — đọc thật bởi
`resolve_market_data_venue()` (`binance_endpoints.py`), gọi từ composition root
(`binance_bot_module.py`) để dựng `ExchangeSessionFactory`, factory này là nơi **duy nhất**
được phép gọi `binance.client.Client(...)` (khoá bằng AST guard, xem dưới).

**Không giữ được "mỗi key một nơi đọc, verify tự động" như §4 dự tính ban đầu.** Khảo sát lại
`app_config.json` lúc viết test cho thấy các key `log.*` được đọc như chuỗi literal truyền
thẳng vào tầng config của engine (`app_bootstrapper.py`: `"log.level": verbosity.log_level`),
không qua `ConfigKeys.X` attribute access — một scanner "grep tên attribute" sẽ báo sai (false
positive) cho toàn bộ nhóm `log.*`. Quyết định: bỏ scanner tổng quát, giữ test hẹp hơn nhưng
đúng — khẳng định 2 key chết đã biến mất VÀ key thay thế thật sự được gọi từ composition root
qua đúng chuỗi hàm, không phải chỉ có mặt trong file. Lý do đầy đủ nằm ở docstring của chính
test file.

**Regression test thật** (viết trước fix, xác nhận fail đúng lý do — 2 key cũ vẫn còn — trước
khi sửa, theo `bug-fix-rule.md`):
`tests/unit/config/test_binance_endpoint_config_keys_are_dead.py` — 3 test, khẳng định (1) 2 key
chết không còn trong `ConfigKeys` enum, (2) không còn trong `app_config.json`, (3)
`resolve_market_data_venue`/`ConfigKeys.EXCHANGE_MARKET_DATA_VENUE` thật sự được gọi từ
`binance_bot_module.py`/`binance_endpoints.py`.

**Test bổ sung khoá lại cơ chế** (không chỉ khoá 2 key chết mà khoá cả cách chúng được thay
thế đúng, tránh tái diễn):
- `tests/unit/infrastructure/binance/test_binance_endpoints.py` — `resolve_testnet_flag`,
  `klines_type_for`, `resolve_market_data_venue` (thành công/fallback/cảnh báo giá trị lạ).
- `tests/unit/infrastructure/binance/test_only_the_session_factory_constructs_binance_client.py`
  — AST guard: quét `src/`+`scripts/` cho `Client(...)`, khẳng định chỉ
  `exchange_session_factory.py` có shape này; kèm test mutation tự-verify guard bắt được vi phạm
  thật.
- `tests/integration/infrastructure/binance/test_exchange_session_factory_against_fake_server.py`
  — round-trip HTTP thật (local, không qua mạng) cho cả hai venue.

**Bằng chứng verify cuối cùng** (`ruff check`, `ruff format`, `mypy src scripts` một lệnh,
pytest full suite + sanity — đúng cổng `ci-local.ps1 -Full` yêu cầu):

```
ruff check   → 3 lỗi, cả 3 đều pre-existing ở 2 file scripts/ chưa từng đụng tới
ruff format  → 842 files already formatted
mypy         → Success: no issues found in 169 source files
pytest       → 1 failed (pre-existing, không liên quan), 2966 passed, 4 skipped
sanity       → 24 passed
```

Không có regression mới so với baseline.
