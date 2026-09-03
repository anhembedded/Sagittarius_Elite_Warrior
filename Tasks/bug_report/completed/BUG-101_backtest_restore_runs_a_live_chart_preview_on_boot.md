# BUG-101 — Restoring the Backtest form runs a live chart-preview query the instant the app boots

**Reported date:** 2026-09-03
**Fixed date:** 2026-09-03
**Severity:** 🟠 P2 — no crash, but the app is unusable for several seconds right after launch, and
it does real network/DB work the user never asked for.
**Status:** ✅ Fixed — xem §3.

---

## 1. Hiện tượng (Symptom)

Báo cáo kèm log dev-mode thật. App boot lên, `last_route` được restore về `backtest` (màn hình
người dùng đang mở ở phiên trước), và **ngay lập tức**, trước khi user chạm vào bất cứ thứ gì:

```
2026-09-03 11:07:30,796 - App - DEBUG - [PresenterManager] Lazy Loading Screen: backtest
2026-09-03 11:07:30,999 - App - INFO - Executing query: GetHistoricalKlinesQuery
2026-09-03 11:07:31,000 - App - DEBUG - Payload: GetHistoricalKlinesQuery(symbol='ETHUSDT',
  interval=<TimeFrame.ONE_SECOND: '1s'>, limit=200000, ...)
2026-09-03 11:07:31,000 - App.BackTestPresenter - INFO - [backtest-config] execution mode set to HISTORICAL_TICK
...
2026-09-03 11:07:38,289 - App.QueryHandler - INFO - BACKTEST_TRACE action=query_execute_complete symbol='ETHUSDT' rows=200000
2026-09-03 11:07:38,315 - App - INFO - Executing query: GetBacktestRangeCoverageQuery
```

~7.5 giây, 200,000 dòng `1s` klines, chạy trước khi user bấm bất kỳ nút nào. User yêu cầu: "app
phải ở trạng thái idle, không chạy bất cứ job nào" khi vừa boot lên — chỉ nên **nhớ giá trị input**
(symbol/timeframe/…) để hiện sẵn trên form, không được **replay** giá trị đó như một hành động của
user.

## 2. Root cause

`state_persistence.py::restore()` (Backtest's `IStateContributor.restore_state`) tự khẳng định
trong chính docstring của nó: *"Opening the screen still runs nothing."* Lời hứa đó bị vi phạm
trên thực tế, vì thứ tự khởi tạo trong `BackTestPresenter.__init__`:

```python
self._connect_ui_signals()      # (1) nối selectedSymbolChanged/selectedTimeframeChanged/...
...                              #     → các handler gọi _request_chart_preview()
self._connect_engine_events()
...
self._state_coordinator.restore_into(self)   # (2) set lại đúng những property đó
```

`restore_into()` áp giá trị đã nhớ (từ phiên trước) bằng `setattr(view_model, field.prop, value)`
— **đúng những setter** mà user gõ tay cũng dùng. Vì (1) đã nối tín hiệu **trước** (2), việc restore
một `selectedSymbol`/`selectedTimeframe`/`timeRangePreset` khác giá trị mặc định phát ra
`...Changed`, và handler tương ứng (`_on_symbol_selection_changed`/`_on_timeframe_changed`/
`_on_time_range_changed`/`_on_custom_time_changed`) gọi thẳng `_request_chart_preview()` →
`ChartPreviewCoordinator.request_preview()` → `IThreadManager.submit(...)` → dispatch thật
`GetHistoricalKlinesQuery`/`GetBacktestRangeCoverageQuery` trên background thread.

Không phải do "save UI state" nói chung — `main_window.py` (route/geometry/sidebar),
`dashboard_presenter.py`, và `data_management_presenter.py` đều restore đúng cách: chúng chỉ nối
signal restored-value vào `_mark_state_dirty` (bookkeeping thuần), **sau** khi restore chạy xong,
hoặc (route/geometry) restore chỉ ghi một biến chứ không tự điều hướng. Chỉ riêng
`BackTestPresenter` nối các signal đó vào handler **có tác dụng phụ mạng/DB** và nối **trước** khi
restore chạy.

## 3. Fix

Thêm cờ `self._restoring_state` (đặt `True` quanh đúng lời gọi `restore_into()`, `False` sau đó
qua `try/finally`), và chặn tại **một điểm hội tụ duy nhất** — `_request_chart_preview()` — thay vì
sửa từng handler riêng lẻ, vì mọi handler restore-nhạy-cảm (`_on_symbol_selection_changed`,
`_on_timeframe_changed`, `_on_time_range_changed`, `_on_custom_time_changed`) đều gọi đúng
phương thức này để bắn job thật:

```python
def _request_chart_preview(self) -> None:
    if self._restoring_state:
        return
    self._chart_preview.request_preview()
```

`_on_config_input_changed()` (dirty-tracking FSM cục bộ, không mạng/DB) vẫn chạy bình thường khi
restore — vô hại, và cần thiết để nút Run bật đúng trạng thái. Giá trị form vẫn được restore đầy đủ
(`selectedSymbol`/`selectedTimeframe`/... vẫn đổi, hiện đúng trên UI) — chỉ riêng **hành động mạng**
bị chặn trong lúc restore.

`main_window.py`'s `last_route` restore-and-navigate, và restore của `dashboard_presenter.py`/
`data_management_presenter.py`, đã được xác minh (đọc code, không suy đoán) là **đã đúng** —
không chạm tới, không mở rộng phạm vi ngoài root cause thật.

## 4. Regression test (viết trước, xác nhận đỏ đúng lý do trước khi sửa)

`tests/unit/presentation/ui/screens/test_backtest_presenter_state.py::
test_restoring_symbol_and_timeframe_does_not_run_a_live_chart_preview` — restore
`{"symbol": "SOLUSDT", "timeframe": "15m"}` rồi assert
`container.resolve(IThreadManager).submit` **không** được gọi trong lúc dựng `BackTestPresenter`,
và **vẫn** được gọi bình thường khi user chỉnh sửa thật sau đó (chứng minh cờ không rò rỉ vĩnh
viễn).

Trước khi sửa: **đỏ đúng lý do** — `AssertionError: Expected 'submit' to not have been called.
Called 2 times.` (một lần cho mỗi field restore). Sau khi sửa: xanh.

`test_restoring_never_runs_anything` (test cũ, dùng `capital`/`pyramiding`) **không** bắt được bug
này — hai field đó không nối tới `_request_chart_preview()`, nên test đó là dương tính giả (pass cả
trước và sau khi có bug) cho đúng path này; test mới lấp đúng khoảng trống.

Toàn bộ `tests/unit/presentation/ui/screens/backtest/` +
`tests/unit/presentation/ui/screens/test_backtest_presenter.py` +
`tests/unit/presentation/ui/screens/test_backtest_presenter_state.py`: **314/314 xanh**.
`mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases src scripts` →
`Success: no issues found in 245 source files`.
