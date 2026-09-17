# BUG-116 — Đặt lệnh Limit thủ công luôn bị từ chối: `LIMIT order is missing time_in_force.`

**Reported date:** 2026-09-10
**Severity:** 🟠 P2 — chặn đứng toàn bộ nhánh lệnh Limit của thẻ đặt lệnh thủ công
(EPIC-024B); lệnh Market không bị ảnh hưởng.
**Status:** ✅ Đã sửa 2026-09-10 — root-caused, regression-tested, verified.
**Found by:** user tự chạy app thật trên Testnet, click "Limit" trên thẻ đặt lệnh
thủ công, gửi log lỗi thật.

---

## 1. Symptom

```
Error placing manual order: LIMIT order is missing time_in_force.
...
App - ERROR - ExecuteOrderCommand failed: LIMIT order is missing time_in_force.
```

Lặp lại mỗi lần chọn "Limit" trên thẻ đặt lệnh thủ công rồi gửi — không phải
flake. Lệnh Market không gặp lỗi này.

## 2. Root cause

`Order.time_in_force` chỉ có ý nghĩa với `OrderType.LIMIT` (docstring của chính
`Order`), và `map_order_to_futures_params()`
(`src/infrastructure/binance/futures_order_payload_mapper.py`) đã có sẵn guard
đúng đắn: từ chối gửi bất kỳ lệnh LIMIT nào thiếu `time_in_force`
(`"LIMIT order is missing time_in_force."`). Guard này **không sai** — nó đang
làm đúng việc của nó.

Cái sai nằm ở phía trước: `PreviewOrderQueryHandler.execute()`
(`src/application/use_cases/queries/preview_order/handler.py`) dựng `Order(...)`
nhưng **chưa từng gán `time_in_force`** — field này luôn nhận giá trị mặc định
`None` của chính nó, với mọi loại lệnh, kể từ khi được tạo ở `EPIC-021E`. Lỗi
tiềm ẩn từ đó đến giờ vì nhánh chiến lược tự động (`LiveTradingCoordinator`) chỉ
bao giờ gửi lệnh `MARKET` — không caller thật nào chạm tới nhánh LIMIT của guard
cho đến khi thẻ đặt lệnh thủ công (`EPIC-024B`) — caller LIMIT thật đầu tiên —
được người dùng bấm thật.

Không phải thiếu exception handling như user đoán ban đầu: đây là một validation
guard đang chặn đúng một giá trị thiếu thật sự ở tầng domain, không phải một lỗi
runtime cần try/except.

## 3. Fix

`PreviewOrderQueryHandler.execute()` gán `time_in_force=TimeInForce.GTC` khi
`query.order_type is OrderType.LIMIT`, giữ `None` cho `MARKET` — không đổi hành
vi Market, chỉ lấp đúng chỗ trống LIMIT. GTC (Good-Til-Canceled) là mặc định
đúng cho một lệnh Limit thường: không nơi nào trong UI hiện tại cho người dùng
chọn time-in-force khác (không có IOC/FOK nào được thẻ đặt lệnh thủ công expose).

## 4. Regression test

`tests/unit/application/use_cases/queries/test_preview_order.py`:
- `test_limit_order_defaults_to_good_til_canceled` — chạy riêng lẻ TRƯỚC khi sửa,
  xác nhận đỏ đúng lý do: `AssertionError: assert None is <TimeInForce.GTC: 'GTC'>`
  (repr đầy đủ của `Order(...)` cho thấy `time_in_force=None`), khớp nguyên văn
  lỗi thật user gặp khi field này được đưa tới `map_order_to_futures_params()`.
  Sau fix: xanh.
- `test_market_order_has_no_time_in_force` — lệnh Market vẫn `None`, không bị
  fix này ảnh hưởng.

## 5. Xác minh

- `pytest tests/unit/application/use_cases/queries/test_preview_order.py`: 8 passed.
- Regression sweep liên quan (`preview_order`/`order_payload_mapper`/
  `execute_order`/`manual_order`): 49 passed, 0 failed/error.
- `ruff check`/`ruff format --check` sạch trên `handler.py` và test file đã sửa.
- `mypy` sạch trên `handler.py`.
- `order_preview_to_dict()` (`src/presentation/cli/order_preview_formatter.py`)
  đã xử lý `time_in_force` None-safe từ trước — không cần sửa.

## 6. Ghi chú quy trình

Không đoán field/giá trị thay thế khi chưa rõ nguyên nhân — kiểm tra toàn bộ
pipeline (`Order`, `PreviewOrderQuery`, `TimeInForce`, mapper, CLI) trước khi kết
luận đây là thiếu gán ở `PreviewOrderQueryHandler`, không phải lỗi ở guard hay
thiếu exception handling như user đoán ban đầu — đúng theo `fix-bug-rule.md` §1
(root cause trước, không đoán).

Đánh số **116** (không phải 115) — `BUG-115` đã bị lấy trước lúc merge bởi một
phiên song song (`QQuickWidget` clear-colour đen/xuyên thấu trên hardware
compositor thật, `BOT-132`/`BOT-133`), phát hiện lúc merge nhánh vào
`master-warrior`. Cùng lớp va chạm số đã xảy ra nhiều lần trước đây
(`BUG-078`/`BUG-104`/`BUG-105`/`BUG-106`/`BUG-109`) — xem README §"Đánh số tay
đã hỏng một lần".
