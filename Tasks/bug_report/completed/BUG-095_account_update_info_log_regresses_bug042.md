# BUG-095 — 4 dòng log `ACCOUNT_UPDATE`/`ORDER_TRADE_UPDATE` per-event ở mức INFO — tái diễn đúng lớp lỗi `BUG-042`

**Reported date:** 2026-09-03
**Severity:** 🟡 P2 — không crash trực tiếp, nhưng đúng cơ chế đã từng đơ UI thread ở `BUG-042`
(log INFO per-event đổ vào `LogListModel` trên UI thread khi tần suất event cao).
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`futures_user_data_stream.py::_handle_message()`/`_handle_account_update()` có 4 điểm
`logger.info(...)` chạy **mỗi khi** nhận được `ORDER_TRADE_UPDATE`, tính equity sample, vị thế đổi,
hoặc vị thế đóng — tức là mỗi message websocket thật từ sàn, tần suất có thể rất cao khi có nhiều
lệnh khớp/vị thế biến động liên tục. `logging-rule.md` Rule 4 & 6 (đã áp dụng để đóng `BUG-042` ở
`PaperExchange`) quy định rõ: log per-fill/per-event phải ở `DEBUG`, không phải `INFO` — `INFO` là
mức `SignalLogHandler` UI thật sự tiêu thụ và vẽ lên `LogListModel`.

## 2. Root cause

4 dòng log trong `_handle_message()`/`_handle_account_update()` được viết ở mức `INFO` từ lúc
`EPIC-021H` dựng stream ban đầu — đúng lớp lỗi `BUG-042` (đã đóng ở `PaperExchange` cho luồng
backtest) nhưng chưa từng được áp dụng lại cho luồng live user-data-stream mới xây sau đó. Docstring
module còn nói sai — khẳng định renewal log ở mức INFO là chủ ý, không phải một khoảng trống chưa
kịp sửa.

## 3. Fix

4 dòng `logger.info(...)` đổi thành `logger.debug(...)`: dòng `ORDER_TRADE_UPDATE`, dòng equity
sample, dòng vị thế đổi, dòng vị thế đóng — mỗi dòng kèm comment ngắn trỏ về `BUG-095`. Docstring
module sửa lại cho đúng thực tế (không còn khẳng định renewal log ở INFO).

## 4. Regression test

`tests/unit/infrastructure/binance/test_futures_user_data_stream.py`:
- `test_order_trade_update_logs_at_debug_not_info`
- `test_account_update_position_lines_log_at_debug_not_info` (assertion cuối chỉ kiểm tra
  `"ACCOUNT_UPDATE" in record.message` — thu hẹp có chủ đích để không false-fail trên một
  WARNING hợp lệ khác cùng test)
- `test_equity_sample_logs_at_debug_not_info`

Xác nhận đỏ trước fix (`caplog` bắt được record ở mức `INFO` thay vì `DEBUG`), xanh sau fix.
