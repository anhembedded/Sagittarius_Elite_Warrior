# BUG-072 — Segfault không ổn định trong `tests/integration/`, worker thread mid-`_run_load_history`

**Reported date:** 2026-08-31
**Severity:** Chưa đánh giá — không sai kết quả test khi nó không xảy ra
(3/4 lần chạy full suite gần đây sạch), nhưng khi xảy ra thì crash native cả
tiến trình CI
**Status:** 🔴 Mở — có bằng chứng thật, có giả thuyết mạnh (cùng lớp `BUG-056`),
chưa root-caused/chưa sửa — không tái hiện được đơn lẻ để bisect như `BUG-065`
**Found by:** verify cuối của [`BUG-065`](completed/BUG-065_state_coordinator_test_crashes_a_worker_under_full_parallel_load.md)
— chạy lại `pytest tests/ -q` sau khi `BUG-065`/`BUG-071` đã sửa, để xác nhận
CI thật sạch hoàn toàn, thì bắt được **1 crash khác**, ở vị trí và cơ chế
khác hẳn.

---

## Hiện tượng

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.. python -X faulthandler -m pytest tests/ -q
```

1/4 lần chạy full suite gần đây (sau khi đã sửa `BUG-065`/`BUG-071`) crash
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

**Main thread đang ở `pytest_runtest_setup`'s `_process_events()`** — tức
đang bơm event loop lúc SETUP của 1 test, **trong khi 1 `ThreadPoolExecutor`
worker thread khác đang thực thi giữa chừng** `DashboardPresenter`'s luồng
load-history/start-stream thật (`_run_load_history`/`_run_sync_and_start`).
Đây **chính xác** là hình dạng root cause `BUG-056` đã tìm ra (worker thread
+ main thread bơm event loop cùng lúc → GC/huỷ đối tượng Qt sai thread →
abort/segfault) — nhưng `BUG-056`'s fix (flush `DeferredDelete` +
`processEvents()` trước khi boot engine mới, trong `app_engine` fixture của
`tests/integration/presentation/ui/conftest.py`) rõ ràng **không phủ hết**
đường này, vì crash vẫn xảy ra sau khi fix đó đã có sẵn trong code từ lâu.

## Không tái hiện được đơn lẻ

| Cách chạy | Kết quả |
| :--- | :--- |
| `pytest tests/ -q` (toàn suite) | **crash** 1/4 lần thử gần đây |
| `pytest tests/integration/ -v` một mình | **sạch**, 2/2 lần thử |
| `pytest tests/integration/presentation/ui -v` một mình | **sạch**, 2/2 lần thử |

Không tái hiện được khi cô lập — đúng đặc điểm "không deterministic, phụ
thuộc trạng thái/thời gian tích luỹ của cả suite" mà `BOT-038` (đã đóng,
`Tasks/completed/BOT-038_intermittent_segfault_full_ui_integration_suite.md`)
từng mô tả cho **đúng khu vực code này** (`tests/integration/presentation/
ui/`) trước khi QML bị xoá khỏi app (`EPIC-006`). `BOT-038` đóng lại với kết
luận "không tái hiện nữa sau khi QML bị xoá, không chứng minh được bằng loại
trừ" — bug này có thể là 1 biến thể/tái xuất hiện của cùng lớp lỗi, qua 1 cơ
chế mới không cần QML (dùng thread pool + async runtime + scheduler thật của
`sagittarius_engine`, không phải `QQuickWidget`).

Per `.agents/rules/ci-rule.md` §3: crash native tái xuất hiện sau khi 1 bug
tương tự đã đóng thì phải mở bug **mới**, không reopen bug cũ — đây chính là
trường hợp đó, dù `BOT-038` đã đóng cách đây vài ngày.

## Giả thuyết (chưa xác minh)

`stream_lifecycle_controller.py`'s `_run_load_history`/`_run_sync_and_start`
chạy trên `ThreadManager`'s `ThreadPoolExecutor` — đây là autostart Dev Board
(`BOT-034`) khi mở Dashboard. Không file nào trong
`tests/integration/presentation/` (mức cha, KHÔNG có `conftest.py` riêng —
chỉ `tests/integration/presentation/ui/conftest.py` mới có) tự boot 1
`DashboardPresenter`, nên nghi vấn hàng đầu là: **1 test nào đó bên trong
`tests/integration/presentation/ui/` kết thúc trong khi autostart's
`_run_load_history`/`_run_sync_and_start` vẫn còn đang chạy trên thread pool,
và `main_window`/`app_engine` fixture's `thread_manager.shutdown(wait=True)`
không thực sự chờ đủ** — hoặc do task đó bị submit **sau** thời điểm
`shutdown(wait=True)` đã gọi (race giữa `navigate("dashboard")`'s autostart
và fixture teardown), để lại 1 worker vẫn chạy khi test KẾ TIẾP setup.

Không tái hiện được đơn lẻ (`tests/integration/presentation/ui` một mình
luôn sạch) gợi ý cần **thêm tải/thời gian tích luỹ từ các thư mục integration
khác chạy trước nó** (`application/`, `infrastructure/`, `presentation/` mức
cha) mới đủ để trúng đúng cửa sổ race — giống hệt kết luận `BOT-038` đã ghi.

## Hướng điều tra tiếp theo (đề xuất, chưa làm)

1. Rà lại TOÀN BỘ điểm `navigate("dashboard")`/autostart trong
   `tests/integration/presentation/ui/` — xác nhận `thread_manager.shutdown
   (wait=True)` trong `app_engine`/`main_window` fixture teardown THẬT SỰ
   chặn được task autostart nộp trễ (sau khi `navigate()` return nhưng trước
   khi fixture teardown bắt đầu).
2. Thử chạy lặp lại `pytest tests/ -q` nhiều lần (10+) để đo tần suất tái
   hiện thật, thay vì kết luận từ 1/4 lần.
3. Nếu tái hiện đủ ổn định, dùng kỹ thuật bisect bằng danh sách test ID chính
   xác (`pytest -q <id...>`) giống `BUG-065` đã làm — nhưng lưu ý: `BUG-065`
   bisect được vì crash đó **đơn luồng, deterministic theo state**; bug này
   có vẻ **đa luồng, phụ thuộc thời gian thật (race)**, nên bisect theo thứ
   tự test có thể không ổn định như `BUG-065`.
4. Không loại trừ khả năng đây thật ra **cùng 1 cơ chế `BOT-038`** dưới 1 lớp
   áo mới (thread pool thay vì QQuickWidget) — nếu vậy, hướng sửa hợp lý nhất
   là tổng quát hoá `app_engine`/`main_window` fixture's drain logic (đã có
   sẵn cho `ThreadManager`) để cover luôn autostart task nộp SAU
   `navigate()` return, trước khi test kết thúc — không chỉ ở fixture
   teardown.

## Không thuộc phạm vi

Không liên quan gì tới `BUG-065`/`BUG-071` (đã sửa, đã verify riêng, đóng
độc lập) — bug này lộ ra **sau khi** 2 bug kia đã sửa, trong lúc verify cuối
cùng bằng `pytest tests/ -q` lặp lại.
