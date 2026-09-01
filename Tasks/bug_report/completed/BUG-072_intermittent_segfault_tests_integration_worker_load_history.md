# BUG-072 — Segfault không ổn định trong `tests/integration/`, worker thread mid-`_run_load_history`

**Reported date:** 2026-08-31
**Fixed date:** 2026-09-01
**Severity:** Cao — crash native cả tiến trình CI khi trúng
**Status:** ✅ Fixed 2026-09-01 — root-caused, regression-tested, log evidence
sống xác nhận đúng cơ chế nghi vấn
**Found by:** verify cuối của [`BUG-065`](BUG-065_state_coordinator_test_crashes_a_worker_under_full_parallel_load.md)
— chạy lại `pytest tests/ -q` sau khi `BUG-065`/`BUG-074` đã sửa, để xác nhận
CI thật sạch hoàn toàn, thì bắt được **1 crash khác**, ở vị trí và cơ chế
khác hẳn.

---

## Hiện tượng

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.. python -X faulthandler -m pytest tests/ -q
```

1/4 lần chạy full suite gần đây (sau khi đã sửa `BUG-065`/`BUG-074`) crash
`Segmentation fault` rất sớm — ~2% tiến độ, trong `tests/integration/`.
Faulthandler dump:

```
Thread 0x00007f8e85f4f6c0 (most recent call first):
  File "src/presentation/ui/components/indicator_scripts/runner.py", line 248 in feed
  File "src/presentation/ui/components/indicator_scripts/runner.py", line 309 in feed_all
  File "src/presentation/ui/screens/dashboard/stream_lifecycle_controller.py", line 371 in _run_load_history
  File "src/presentation/ui/screens/dashboard/stream_lifecycle_controller.py", line 483 in _run_sync_and_start
  File "/usr/lib/python3.12/concurrent/futures/thread.py", line 58 in run
  ...

Thread ...: sagittarius_engine's Scheduler._run (condition wait)
Thread ...: sagittarius_engine's AsyncRuntime._run_loop (x2)

Current thread (most recent call first):
  File ".../pytestqt/plugin.py", line 220 in _process_events
  File ".../pytestqt/plugin.py", line 179 in pytest_runtest_setup
```

Dòng ngay trước lúc crash: `_pythonToCppCopy: Cannot copy-convert 0x... (
_FakeResponse) to C++.` — cùng `_FakeResponse` mà
`tests/integration/presentation/ui/conftest.py` dùng thay `MagicMock` để sửa
`BUG-056`.

**Xác nhận sống, 2026-09-01:** chạy lại `pytest tests/ -q` lặp lại để verify
fix bên dưới, log bắt được **đúng dòng cảnh báo đó lần nữa**, cùng bản chất:

```
_pythonToCppCopy: Cannot copy-convert 0x7f0909fd4130 (_FakeResponse) to C++.
```

## Root cause

`ChartPreviewCoordinator.run_preview()`
(`src/presentation/ui/screens/backtest/coordinators/chart_preview_coordinator.py`)
dispatch hai query trên 1 worker thread rồi emit kết quả qua
`BackTestPresenter._previewDataReadySignal = Signal(int, object, list, list,
list)` — một signal cross-thread, Qt tự queue việc giao nó tới main thread.

Dòng `raw_klines` unwrap đúng: `getattr(response, "data", response)` — chấp
nhận cả 2 hình dạng: production trả thẳng giá trị (không bọc), còn
`tests/integration/presentation/ui/conftest.py`'s `mock_dispatch` bọc trong
`_FakeResponse.data` (double thay `MagicMock`, xem `BUG-056`). Nhưng dòng
`coverage` **thiếu đúng unwrap đó**:

```python
coverage = self._dispatcher.dispatch(
    GetBacktestRangeCoverageQuery,
    GetBacktestRangeCoverageQuery(...),
)
self._emit_preview_ready(preview_id, coverage, ...)
```

`GetBacktestRangeCoverageQueryHandler.execute()` trả thẳng
`BacktestRangeCoverage` (dataclass, không `.data`) — nên trong production
`coverage` đúng. Nhưng `mock_dispatch` (test suite) **không đặc-cách**
`GetBacktestRangeCoverageQuery` — nó rơi vào nhánh `else`, và trước khi sửa,
nhánh đó gán `response.data = []`, khiến biến `response` (kiểu
`_FakeResponse`, `__slots__ = ("data", "success")`) — chứ không phải giá trị
`.data` bên trong nó — được emit thẳng qua signal, vì thiếu unwrap.

`_FakeResponse` không có metatype nào Qt/shiboken biết, nên
`_pythonToCppCopy` cảnh báo đúng như log. Vì signal này queue cross-thread,
sự kiện bị lỗi marshaling đó có thể nằm chờ và được xử lý ở
`_process_events()` của **một test khác hẳn**, sau này — khớp chính xác hình
dạng crash quan sát được: main thread đang bơm event loop lúc SETUP của 1
test, trong khi 1 worker thread khác (không liên quan) đang chạy giữa chừng.

Hai file khác đã bị loại trừ trong lúc điều tra (không phải nguồn):
`stream_lifecycle_controller.py`'s signal riêng đều gõ kiểu chặt, đều emit dữ
liệu thuần đã unwrap trước; `thread_manager.shutdown(wait=True)` trong
`app_engine`/`main_window` fixture teardown chặn được mọi task còn treo —
không phải nơi background task "sống sót" qua shutdown.

## Fix

1. `chart_preview_coordinator.py::run_preview()` — áp đúng unwrap
   `getattr(response, "data", response)` cho `coverage`, giống hệt
   `raw_klines` hai dòng phía trên (idiom đã có sẵn trong chính hàm này).
2. `tests/integration/presentation/ui/conftest.py::mock_dispatch` — thêm
   nhánh đặc-cách `GetBacktestRangeCoverageQuery`, trả về 1
   `BacktestRangeCoverage` thật (fully covered, khớp `MOCK_KLINE_COUNT`) thay
   vì rơi vào nhánh `else: response.data = []`. Không chỉ tránh riêng lỗi
   marshaling — trước fix này, mọi hành vi phụ thuộc coverage trong test
   suite (`set_data_coverage`/`set_needs_data_sync`) đều nhận `[]` (một
   `list`) thay vì `BacktestRangeCoverage`, silently sai kiểu nhưng không
   crash nên chưa ai phát hiện.

## Regression test

`tests/unit/presentation/ui/screens/backtest/coordinators/test_chart_preview_coordinator.py::test_run_preview_unwraps_a_test_doubles_response_envelope`
— dựng 1 dispatcher giả bọc `coverage` trong `SimpleNamespace(data=...)`
(đúng hình dạng `_FakeResponse` gây lỗi), gọi `run_preview()` trực tiếp, và
assert đối tượng coverage đến `emit_preview_ready` chính là đối tượng **bên
trong** `.data` (identity check `is`), không phải cái envelope bọc nó.

Xác nhận fail đúng lý do trước fix (`emitted_coverage is inner_coverage` sai
— coordinator emit thẳng envelope), pass sau khi thêm dòng
`getattr(coverage_response, "data", coverage_response)`.

`pytest tests/unit/presentation/ui/screens/backtest/coordinators/test_chart_preview_coordinator.py -q`
— 8/8 pass (7 test cũ + 1 mới).

## Không tái hiện được đơn lẻ full suite — vẫn hợp lý với root cause

| Cách chạy | Kết quả |
| :--- | :--- |
| `pytest tests/ -q` (toàn suite) | crash 1/4 lần thử trước fix |
| `pytest tests/integration/ -v` một mình | sạch |
| `pytest tests/integration/presentation/ui -v` một mình | sạch |

Khớp với cơ chế: cần Backtest screen's preview đã submit **và** Dashboard
autostart's `_run_load_history` cùng đang treo lúc 1 test khác setup — tổ hợp
timing hiếm, chỉ tích luỹ đủ khi chạy toàn bộ `tests/integration/` cùng lúc
với các thư mục khác. Không cần bisect đơn luồng như `BUG-065`: bằng chứng
tĩnh (đọc code, khớp chính xác dòng cảnh báo) đủ mạnh để root-cause mà không
cần cô lập crash trực tiếp — cùng tinh thần `BUG-052` (không lấy được repro
tuyệt đối cô lập không có nghĩa là không sửa được).

`BOT-038` (đã đóng, `Tasks/completed/BOT-038_intermittent_segfault_full_ui_integration_suite.md`)
từng mô tả crash không tái hiện được ở đúng khu vực `tests/integration/
presentation/ui/` trước khi QML bị xoá (`EPIC-006`) — bug này là bug **mới**
(`.agents/rules/ci-rule.md` §3: crash native tái xuất hiện sau khi 1 bug
tương tự đã đóng thì phải mở bug mới), qua 1 cơ chế mới hoàn toàn khác
(loose-typed `Signal(object)` mang test double, không phải QML).

## Không thuộc phạm vi

Không liên quan gì tới `BUG-065`/`BUG-074`/`BUG-073` (đã sửa, đã verify
riêng, đóng độc lập) — bug này lộ ra **sau khi** những bug kia đã sửa, trong
lúc verify cuối cùng bằng `pytest tests/ -q` lặp lại.
