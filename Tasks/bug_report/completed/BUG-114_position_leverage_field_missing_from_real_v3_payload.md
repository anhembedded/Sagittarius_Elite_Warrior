# BUG-114 — `GetOpenPositionsQuery`/`EnableTradingCommand` crash trên tài khoản có vị thế thật: `/fapi/v3/positionRisk` không có field `leverage`/`marginType` như code giả định

**Reported date:** 2026-09-09
**Severity:** 🔴 P1 — bất kỳ tài khoản có vị thế mở thật nào cũng làm hỏng
`GetOpenPositionsQuery` và `EnableTradingCommand` vĩnh viễn, không phải ngẫu nhiên —
chặn đứng cả bảng Vị thế và luồng bật giao dịch.
**Status:** ✅ Đã sửa 2026-09-09 — root-caused bằng bằng chứng thật, regression-tested,
verified.
**Found by:** user tự chạy app thật trên Testnet, gửi log lỗi + màn hình Positions
thật trên Binance UI xác nhận vị thế có thật (20x).

---

## 1. Symptom

```
2026-09-09 23:10:25,484 - App.TradingClient - ERROR - map_futures_position_payload_to_live_position failed on a real payload — raw payload for BUG-114 diagnosis: {'symbol': 'ETHUSDT', 'positionSide': 'BOTH', 'positionAmt': '0.010', 'entryPrice': '2489.88', 'breakEvenPrice': '2490.8759520000003', 'markPrice': '2492.02649225', 'unRealizedProfit': '0.02146492', 'liquidationPrice': '0', 'isolatedMargin': '0', 'notional': '24.92026492', 'marginAsset': 'USDT', 'isolatedWallet': '0', 'initialMargin': '1.24601325', 'maintMargin': '0.12460132', 'positionInitialMargin': '1.24601325', 'openOrderInitialMargin': '0', 'adl': 1, 'bidNotional': '0', 'askNotional': '0', 'updateTime': 1788967154080}
2026-09-09 23:10:25,485 - App - ERROR - EnableTradingCommand failed: 'leverage'
```

`GetOpenPositionsQuery failed: 'leverage'` lặp lại mỗi lần gọi, cùng lý do — không
phải flake.

## 2. Root cause

`map_futures_position_payload_to_live_position()`
(`src/infrastructure/binance/futures_order_payload_mapper.py`) đọc thẳng
`payload["leverage"]`/`payload.get("marginType", "")` — shape này viết theo tài
liệu Binance từ trước, **chưa từng xác minh với lệnh gọi thật** (sandbox CI/dev bị
chặn egress `*.binance.*`, đã tự khai từ `futures_account_reader.py`).
`futures_position_information()` (`python-binance`) gọi
`/fapi/v3/positionRisk` — **response thật của endpoint V3 không có cả hai field
này** (bằng chứng: payload thật ở trên, `KeyError: 'leverage'`). `leverage`/
`marginType` chỉ tồn tại ở version cũ hơn của endpoint này mà code đã lỡ giả định
vẫn còn.

Đối chiếu độc lập: user chụp màn Binance Testnet UI ngay trước đó — vị thế
ETHUSDT thật đang **20x**. Kiểm tra công thức margin của chính Binance
(`initialMargin = notional / leverage`) trên đúng payload thật:
`24.92026492 / 1.24601325 = 20.000...` — khớp đúng 20x độc lập xác nhận, trên cả
3 payload thật user gửi.

## 3. Fix

Thay 2 field đọc trực tiếp bằng 2 hàm suy ra từ field **thật sự có** trên payload
V3:

- `leverage`: `round(notional / initialMargin)` — công thức margin chính Binance
  dùng, không phải suy đoán tuỳ ý; verify khớp đúng 20x trên payload thật.
- `margin_type`: `isolatedMargin`/`isolatedWallet` khác 0 → `ISOLATED`, ngược lại
  (cả hai đều `"0"`, đúng như payload thật Cross) → `CROSSED`.

Cả hai đều **lệch khỏi nguyên tắc** module tự ghi ("never computes, only parses")
— ghi rõ lý do ngay trong code: field gốc mà app dựa vào bao lâu nay hoá ra không
tồn tại trên wire thật, và không có field nào khác đã-được-xác-minh báo trực tiếp
giá trị này.

Dọn lại đoạn log chẩn đoán tạm (`BUG-114-TMP`, thêm ở PR trước để lấy payload thật)
— đã có bằng chứng, không cần giữ nữa.

## 4. Regression test

`tests/unit/infrastructure/binance/test_futures_order_payload_mapper.py::
TestPositionMapping::test_real_v3_payload_with_no_leverage_or_margin_type_fields_maps_cleanly`
— dùng **đúng payload thật** user gửi làm fixture (`_REAL_V3_PAYLOAD_20X_CROSS`).
Mutation-verify: tạm khôi phục `int(payload["leverage"])`, xác nhận test đỏ đúng
`KeyError: 'leverage'` — khớp nguyên văn lỗi thật user gặp — rồi khôi phục fix,
xác nhận xanh lại. 2 test cũ (`test_maps_a_long_position`/
`test_zero_liquidation_price_maps_to_none`) cập nhật fixture theo shape V3 thật
(bỏ `leverage`/`marginType`, thêm `notional`/`initialMargin`/`isolatedMargin`).

## 5. Xác minh

- `pytest tests/unit/infrastructure/binance/test_futures_order_payload_mapper.py tests/unit/infrastructure/binance/test_futures_trading_client.py tests/integration/infrastructure/binance/test_futures_trading_client_order_lifecycle_against_fake_server.py tests/integration/application/test_manual_order_pipeline_against_fake_server.py tests/integration/application/test_live_trading_pipeline_against_fake_server.py`: 29 passed.
- `ruff check`/`ruff format --check` sạch trên mọi file đã sửa.
- `mypy --config-file pyproject.toml` sạch trên 2 file `src/` đã sửa.
- CI gate đầy đủ (`ci-local.ps1 -Full`) chạy sau khi gộp, xác nhận bằng grep log file thật.

## 6. Ghi chú quy trình

Không đoán field/giá trị thay thế khi chưa có bằng chứng thật — đúng theo
`fix-bug-rule.md` §2 (thêm log chẩn đoán tạm trước, PR riêng đã push/merge để
lấy payload thật) và `domain-truth-rule.md` (không hiển thị sai đòn bẩy thật).
Payload thật do user tự gửi qua log — không cần chạm tới API key/secret nào cả
(user có đề nghị đưa key, đã từ chối: sandbox này bị chặn egress `*.binance.*`
nên dù có key cũng không gọi được, và dán key vào chat là rủi ro không cần
thiết dù chỉ là Testnet).
