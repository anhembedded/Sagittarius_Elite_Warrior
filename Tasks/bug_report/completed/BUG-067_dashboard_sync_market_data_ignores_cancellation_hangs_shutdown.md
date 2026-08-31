# BUG-067 — Dashboard Live Stream sync bỏ qua cancellation, thread kẹt làm treo tiến trình khi tắt app

**Reported date:** 2026-08-30  
**Severity:** 🔴 **P1**  
**Status:** ✅ Fixed 2026-08-30 (root-caused / reproduced / regression-tested / verified)

---

## 1. Hiện tượng (Symptom)

Khi người dùng khởi động Live Stream trên Dev Board (ví dụ cặp `0GTRY` khung `1s` tải 7 ngày lịch sử từ Binance) rồi tắt ứng dụng trong lúc tiến trình tải dữ liệu đang chạy:

1. Giao diện và các module của Engine tắt bình thường (`App stopped.`).
2. Tuy nhiên tiến trình Python không thể kết thúc (process hangs on exit), buộc phải tắt bằng Task Manager / `kill`.
3. Log ghi nhận cảnh báo vi phạm luồng `BUG-052` class:

```text
2026-08-30 17:33:23,015 - App - INFO - App stopped.
2026-08-30 17:33:23,016 - App - WARNING - 1 non-daemon thread(s) still alive after engine shutdown — the process will hang at exit until they finish (BUG-052 class): 'ThreadPoolExecutor-0_1'
    'ThreadPoolExecutor-0_1' is stuck at:
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Elite_Warrior\src\presentation\ui\screens\dashboard\stream_lifecycle_controller.py", line 462, in _run_sync_and_start
    self._sync_market_data(symbols, interval, start_time, end_time)
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Elite_Warrior\src\presentation\ui\screens\dashboard\stream_lifecycle_controller.py", line 438, in _sync_market_data
    self.dispatcher.dispatch(SyncMarketDataCommand, sync_cmd)
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Engine\sagittarius_engine\kernel\dispatcher.py", line 58, in dispatch
    result = self.context.middleware_pipeline.execute(
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Engine\sagittarius_engine\kernel\middleware_pipeline.py", line 58, in execute
    return next_handler()
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Engine\sagittarius_engine\middleware\pydantic_validation_middleware.py", line 184, in process
    return next_handler()
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Engine\sagittarius_engine\kernel\dispatcher.py", line 59, in <lambda>
    handler, input_dto, lambda: handler.execute(input_dto)
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Elite_Warrior\src\application\use_cases\sync\sync_market_data\handler.py", line 50, in execute
    self._sync_single_symbol(symbol, command)
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Elite_Warrior\src\application\use_cases\sync\sync_market_data\handler.py", line 77, in _sync_single_symbol
    for chunk in self.exchange_client.stream_historical_klines(
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Elite_Warrior\src\infrastructure\binance\client.py", line 226, in stream_historical_klines
    yield from self._stream_raw_klines_as_market_data(
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Elite_Warrior\src\infrastructure\binance\client.py", line 250, in _stream_raw_klines_as_market_data
    for k in generator:
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Elite_Warrior\src\infrastructure\binance\client.py", line 129, in _generate_raw_klines_with_retry
    for k in generator:
  File "C:\Users\hoang\Documents\Claude\Sagittarius_Elite_Warrior\.venv\Lib\site-packages\binance\client.py", line 1128, in _historical_klines_generator
    time.sleep(1)
```

---

## 2. Nguyên nhân gốc rễ (Root Cause)

1. Trong [`stream_lifecycle_controller.py`](file:///c:/Users/hoang/Documents/Gemini/Sagittarius-Elite-Warrior/src/presentation/ui/screens/dashboard/stream_lifecycle_controller.py#L462):
   - Hàm `_run_sync_and_start` nhận `token: CancellationToken`.
   - Nhưng hàm `_sync_market_data` hoàn toàn **không truyền `cancellation_requested=token.is_cancelled`** vào `SyncMarketDataCommand`.
   - Vì thế khi người dùng tắt stream hoặc tắt app, `token.cancel()` được gọi nhưng `SyncMarketDataCommandHandler` và `PythonBinanceClient` không hề nhận được tín hiệu hủy, tiếp tục lặp vô hạn tải dữ liệu qua network.
2. `StreamLifecycleController` không có cơ chế `shutdown()` để giải phóng `ExclusiveAction` và kích hoạt hủy token khi ứng dụng tắt.
3. `PythonBinanceClient` không có phương thức `close()` để ngắt các kết nối socket đang chờ đọc (`requests.Session`) khi engine shutdown.

---

## 3. Cách khắc phục (Fix)

1. **Truyền cancellation callback:**
   - Cập nhật `_sync_market_data` nhận `cancellation_requested: CancellationCheck | None = None` và truyền vào `SyncMarketDataCommand`.
   - Trong `_run_sync_and_start`: truyền `cancellation_requested=token.is_cancelled`.
2. **Triệu hồi shutdown trên StreamLifecycleController:**
   - Bổ sung `StreamLifecycleController.shutdown()` hủy token và giải phóng slot hành động.
   - Gọi `self._stream_controller.shutdown()` bên trong [`DashboardPresenter.shutdown()`](file:///c:/Users/hoang/Documents/Gemini/Sagittarius-Elite-Warrior/src/presentation/ui/screens/dashboard/dashboard_presenter.py#L734).
3. **Đóng session mạng khi Engine tắt:**
   - Thêm phương thức `close()` trên [`PythonBinanceClient`](file:///c:/Users/hoang/Documents/Gemini/Sagittarius-Elite-Warrior/src/infrastructure/binance/client.py) để đóng `requests.Session`.
   - Gọi `exchange_client.close()` trong [`BinanceBotModule.shutdown()`](file:///c:/Users/hoang/Documents/Gemini/Sagittarius-Elite-Warrior/src/binance_bot_module.py#L315).

---

## 4. Kiểm thử hồi quy (Regression Test)

Đã viết test kiểm tra tự động tại:
[`tests/unit/presentation/ui/screens/dashboard/test_stream_lifecycle_cancellation.py`](file:///c:/Users/hoang/Documents/Gemini/Sagittarius-Elite-Warrior/tests/unit/presentation/ui/screens/dashboard/test_stream_lifecycle_cancellation.py)
- `test_stream_lifecycle_controller_passes_cancellation_to_sync_command`: PASSED ✅
- `test_stream_lifecycle_controller_shutdown_cancels_token_and_actions`: PASSED ✅
- `test_python_binance_client_close_closes_session`: PASSED ✅
