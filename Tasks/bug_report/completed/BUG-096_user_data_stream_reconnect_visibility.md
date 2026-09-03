# BUG-096 — Reconnect của User Data Stream gần như vô hình: sentinel lỗi của thư viện bị bỏ qua, và `ReadLoopClosed` không được coi là lỗi cần reconnect

**Reported date:** 2026-09-03
**Severity:** 🟠 P2 — mất kết nối tới sàn có thể xảy ra âm thầm, không log, không tự phục hồi đúng
cách trong một số trường hợp thực tế của `python-binance`.
**Status:** ✅ **Đã sửa (2026-09-03)** — 3 phần độc lập, cùng chủ đề "khả năng quan sát khi mất kết
nối".

---

## 1. Hiện tượng (Symptom)

Đọc trực tiếp source đã cài của `python-binance`
(`.venv/lib/python3.12/site-packages/binance/ws/reconnecting_websocket.py`,
`binance/exceptions.py`) để xác minh hành vi thật (không đoán, vì egress `*.binance.*` bị chặn
trong sandbox này):

1. `ReconnectingWebsocket._read_loop()` đẩy một sentinel `{"e": "error", "type": ..., "m": ...}`
   qua chính queue mà `.recv()` đọc, mỗi lần có một lần connection blip (trước khi tự reconnect).
   `_handle_message()` của app không có nhánh nào xử lý `event_type == "error"` — sentinel này bị
   rơi vào nhánh `else` im lặng, không log, không có dấu vết một lỗi kết nối vừa xảy ra và tự phục
   hồi.
2. Sau khi `MAX_RECONNECTS=5` bị thư viện dùng hết, `_read_loop()` chết hẳn
   (`_handle_read_loop = None`); lần `.recv()` kế tiếp raise `ReadLoopClosed` — một `Exception`
   thường, **không phải** `OSError`. `_run_stream()`'s except-clause hiện tại chỉ bắt `OSError`,
   nên `ReadLoopClosed` bay thẳng lên, crash task nền thay vì được coi là "cần reconnect".
3. Module docstring khẳng định renewal/reconnect được log ở INFO — sai (xem `BUG-095`).

## 2. Root cause

Cả 2 vấn đề kỹ thuật đều từ việc code app viết dựa trên giả định về hành vi thư viện chưa được đối
chiếu với source thật — `_run_stream()`'s except-clause được viết cho lớp lỗi mạng "hiển nhiên"
(`OSError`), không tính tới cách riêng `python-binance` báo lỗi kết nối (sentinel qua queue,
`ReadLoopClosed` là `Exception` trần).

## 3. Fix

- `from binance.exceptions import ReadLoopClosed` — thêm import.
- `except OSError as exc:` → `except (OSError, ReadLoopClosed) as exc:` kèm comment giải thích
  `ReadLoopClosed` là gì và tại sao nó thuộc cùng nhóm "cần reconnect" dù không phải `OSError`.
- `_LIBRARY_ERROR_EVENT = "error"` — hằng số đặt tên cho sentinel event type của thư viện.
- `_handle_message()` thêm nhánh `elif event_type == _LIBRARY_ERROR_EVENT:
  logger.warning("User data stream reported a connection issue: %s (%s)", payload.get("m"),
  payload.get("type"))` — sentinel giờ có dấu vết log thật, ở mức WARNING (đúng mức cho một sự
  kiện đáng chú ý nhưng tự phục hồi).
- Docstring module sửa lại đúng thực tế (paragraph "BUG-096 correction").

## 4. Regression test

`tests/unit/infrastructure/binance/test_futures_user_data_stream.py`:
- `test_library_error_sentinel_is_logged_not_silently_dropped` — gửi message
  `{"e": "error", "type": ..., "m": ...}` qua `_handle_message()`, xác nhận có đúng một
  `logger.warning` với nội dung message gốc.
- `test_read_loop_closed_triggers_a_reconnect_not_a_crash` (async) — `DyingSocket` raise
  `ReadLoopClosed` ở lần `recv()` đầu, `RevivedSocket` (lần `futures_user_data_stream()` thứ hai)
  trả message hợp lệ; patch `asyncio.sleep` để test không chờ backoff thật; xác nhận stream tự
  phục hồi, không raise ra ngoài `_run_stream()`.

Xác nhận đỏ trước fix (`ReadLoopClosed` bay thẳng ra khỏi `_run_stream()`, sentinel `"error"` không
sinh log nào), xanh sau fix.
