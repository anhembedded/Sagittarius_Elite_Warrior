# BUG-091 — Order status/type lạ từ sàn làm parser raise `KeyError`, mất trắng cập nhật thay vì suy giảm an toàn

**Reported date:** 2026-09-03
**Severity:** 🟠 **P2** — một trường hợp Binance thêm một status/type mới (hoặc gửi giá trị app
chưa từng thấy) làm rớt hẳn `ORDER_TRADE_UPDATE` đó, không có cách nào phục hồi ngoài restart.
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`user_data_event_parser.py::parse_order_trade_update()` và
`futures_order_payload_mapper.py::map_futures_order_payload_to_order()` đọc trực tiếp
`OrderStatus[raw_status]` / `OrderType[raw_type]` / `TimeInForce(raw_tif)` — indexing/constructor
kiểu Enum raise `KeyError`/`ValueError` nếu giá trị thô không khớp member đã khai báo. Vì lệnh này
chạy trong `_handle_message()` của websocket stream (không có try/except bọc riêng cho lỗi parse),
một giá trị lạ (Binance thêm status/type mới, hoặc một edge-case app chưa biết) làm crash toàn bộ
đường xử lý message đó — cập nhật bị mất, không log, không có dấu vết.

## 2. Root cause

Không có "catch-all" cho hai enum này, khác với `OrderRejectionReason` — enum đó đã có sẵn
`UNKNOWN` như một chủ đích thiết kế đã dùng ở `binance_error_translator.py`. `OrderStatus` và
`OrderType` chưa từng cần catch-all vì trước EPIC-021 không có đường nào parse dữ liệu **sống**
trực tiếp từ sàn — mọi test trước đó dùng giá trị đã biết trước.

## 3. Fix

- `src/domain/trading/order_status.py` — thêm `UNKNOWN = "unknown"`; `_VALID_TRANSITIONS[OrderStatus.UNKNOWN]`
  = tập hợp cả 6 status thật (một khi rơi vào UNKNOWN, lần cập nhật kế tiếp với status thật hợp lệ
  vẫn được chấp nhận, không tự khoá state máy).
- `src/domain/trading/order_type.py` — thêm `UNKNOWN = "unknown"`.
- `src/infrastructure/binance/order_enum_parsing.py` (file mới) — 3 helper dùng chung:
  `order_status_or_unknown(raw) -> OrderStatus`, `order_type_or_unknown(raw) -> OrderType`,
  `time_in_force_or_none(raw) -> TimeInForce | None` — mỗi hàm bọc lookup trong try/except, không
  bao giờ raise, log cảnh báo khi rơi vào nhánh fallback.
- `user_data_event_parser.py::parse_order_trade_update()` và
  `futures_order_payload_mapper.py::map_futures_order_payload_to_order()` đổi sang dùng 3 helper
  này thay vì lookup Enum trần.

## 4. Regression test

`tests/unit/infrastructure/binance/test_user_data_event_parser.py`:
- `test_an_unrecognized_status_falls_back_to_unknown_not_a_raise`
- `test_an_unrecognized_order_type_falls_back_to_unknown_not_a_raise`
- `test_an_unrecognized_time_in_force_falls_back_to_none_not_a_raise`

`tests/unit/infrastructure/binance/test_futures_order_payload_mapper.py`:
- `test_an_unrecognized_type_and_status_fall_back_to_unknown_not_a_raise`

Xác nhận đỏ trước fix (`KeyError`/`ValueError` raise thẳng thay vì trả `UNKNOWN`), xanh sau fix.
