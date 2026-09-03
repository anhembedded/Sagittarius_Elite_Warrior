# BUG-090 — `minNotional` không được kiểm tra trước khi gửi lệnh thật; exchange reject/network lỗi có thể làm crash CLI/coordinator

**Reported date:** 2026-09-03
**Severity:** 🔴 **P1** — an toàn giao dịch + ổn định tiến trình: một lệnh chắc chắn bị sàn từ chối
vẫn được gửi đi (tốn round-trip, có thể dính rate-limit thật), và một exception từ sàn hoặc mạng
không được bắt có thể crash cả `trade-once --live` lẫn vòng lặp live coordinator.
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`ExecuteOrderCommandHandler` tính `preview` (bao gồm `preview.notional_check`) nhưng chỉ dùng nó
để hiển thị — không có nhánh nào chặn việc gửi lệnh khi `NotionalCheck.INSUFFICIENT`. Lệnh vẫn đi
tới `ITradingClient.submit_order(...)` thật, sàn sẽ trả lỗi `-4164` (MIN_NOTIONAL) — nhưng
`trade_once_cmd.py` không bọc `app.dispatch(...)` trong try/except nào cho các exception loại
`BinanceAPIException`/`BinanceRequestException`/`RequestException`, và
`live_trading_coordinator.py`'s vòng lặp cũng không bọc `self._dispatcher.dispatch(...)` — một
exception ở đây bay thẳng lên, crash tiến trình.

## 2. Root cause

- `src/application/use_cases/trading/execute_order/handler.py` — tính `preview` xong không có
  early-return nào dựa trên `preview.notional_check`; 4 kiểm tra trading-limit chạy sau đó nhưng
  không có kiểm tra nào tương đương cho notional.
- `src/presentation/cli/trade_once_cmd.py` — gọi `app.dispatch(ExecuteOrderCommand, command)` trần,
  không try/except.
- `src/application/services/live_trading_coordinator.py` — cùng pattern, `self._dispatcher.dispatch(
  ExecuteOrderCommand, command)` trần trong vòng lặp chạy nền liên tục.

## 3. Fix

- `src/application/use_cases/trading/execute_order/result.py` — thêm
  `ExecuteOrderNotionalRejection(str, Enum)` với member `MIN_NOTIONAL`; `ExecuteOrderResult.blocked_by`
  mở rộng type để nhận giá trị này.
- `handler.py` — ngay sau khi tính `preview`: nếu `preview.notional_check is
  NotionalCheck.INSUFFICIENT`, trả `ExecuteOrderResult(ExecuteOrderNotionalRejection.MIN_NOTIONAL,
  preview, (), None)` **trước** 4 kiểm tra trading-limit, không gọi mạng.
- `trade_once_formatter.py::format_result()` — thêm nhánh in thông báo thân thiện cho
  `ExecuteOrderNotionalRejection.MIN_NOTIONAL` trước fallthrough DRY-RUN/LIVE.
- `trade_once_cmd.py` — bọc `app.dispatch(ExecuteOrderCommand, command)` trong try/except:
  `OrderRejectedByExchangeError`, `InvalidOrderForSubmissionError`,
  `(BinanceAPIException, BinanceRequestException, RequestException)` — mỗi nhánh in thông báo lỗi
  thân thiện, không crash.
- `live_trading_coordinator.py` — bọc `self._dispatcher.dispatch(ExecuteOrderCommand, command)`:
  `except OrderRejectedByExchangeError as exc: logger.warning(...); return`, rồi
  `except Exception as exc: # noqa: BLE001 ...; logger.error(...); return`. Bắt rộng
  (`Exception`) là chủ ý — theo `architecture-rule.md` §3, tầng `application/` không được import
  kiểu exception riêng của SDK hạ tầng (`binance.exceptions`, `requests.exceptions`), nên không thể
  bắt hẹp theo tên lớp cụ thể ở đây; comment giải thích rõ lý do trong code. `OrderRejectedByExchangeError`
  là kiểu domain, import được an toàn.

## 4. Regression test

- `tests/unit/application/use_cases/trading/test_execute_order.py::TestNotionalRejection::
  test_blocked_by_min_notional_before_any_network_order_call` — xác nhận `submit_order` **không**
  bao giờ được gọi khi `notional_check` là `INSUFFICIENT`.
- `tests/unit/presentation/cli/test_trade_once_cmd.py` (file mới) —
  `test_a_live_order_rejected_by_the_exchange_prints_a_friendly_message_not_a_crash`,
  `test_a_network_failure_during_live_dispatch_prints_a_friendly_message_not_a_crash`.
- `tests/unit/application/services/test_live_trading_coordinator.py` —
  `test_exchange_rejection_is_logged_not_raised`,
  `test_a_network_failure_during_dispatch_is_logged_not_raised`.

Xác nhận đỏ trước fix (mock `submit_order` raise `BinanceAPIException`/`RequestException`, dispatch
gọi trần → test crash với đúng exception đó thay vì log), xanh sau fix.
