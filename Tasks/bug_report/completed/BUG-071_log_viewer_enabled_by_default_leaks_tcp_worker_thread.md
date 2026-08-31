# BUG-071 — `log.viewer.enabled: true` mặc định làm rò một thread TCP nền qua suốt phiên test

**Reported date:** 2026-08-31
**Severity:** 🟡 P2 (không sai kết quả test, nhưng là 1 trong nhiều thread nền
tích luỹ suốt phiên CI đơn-tiến-trình; xem `BUG-065` cho cơ chế crash nó góp
phần vào điều tra, dù không phải nguyên nhân chính)
**Status:** ✅ Đã sửa 2026-08-31 — root-caused, reproduced, regression-tested,
verified
**Found by:** điều tra CI crash "Sagittarius Elite Warrior CI" job "Lint & Test"
step "Run Pytest with Coverage" — segfault/abort nguyên bản tại
`test_history_pagination_controller.py` (xem `BUG-065` cho crash chính; đây là
1 phát hiện phụ tìm ra trong lúc điều tra, tách riêng vì là 1 lỗi khác, độc
lập)

---

## Hiện tượng

`src/config/app_config.json` khai `"log.viewer.enabled": true` — bật tính
năng stream mọi dòng log qua TCP tới một tool GUI đồng hành
(`Sagittarius_LogViewer`) trên `127.0.0.1:9999`. Mỗi lần `create_app()`
(`src/main.py`) chạy — tức mỗi test trong `tests/integration/` và
`tests/sanity/` boot 1 `App` thật — `StdLogger(config_manager)` gắn thêm 1
`TcpLogViewerHandler` (`sagittarius_engine/infrastructure/logging/
tcp_log_viewer_handler.py`) lên logger `"App"` dùng chung toàn tiến trình.
Handler này spawn 1 thread nền thật, tên `Sagittarius-TcpLogWorker`, lặp vô
hạn: `queue.get(timeout=0.5)` → thử `socket.create_connection(("127.0.0.1",
9999))` → `OSError` (không có gì lắng nghe ở CI) → đóng socket → `time.sleep
(1.0)` → lặp lại.

`StdLogger.__init__` có dọn handler của lần dựng TRƯỚC khi dựng 1 `StdLogger`
MỚI (cùng logger `"App"` singleton) — nhưng không ai dựng "lần tiếp theo" sau
khi test integration/sanity **cuối cùng** trong phiên chạy xong, nên thread
này sống tiếp, hoạt động liên tục, suốt phần còn lại của tiến trình pytest
đơn — tức là suốt cả `tests/unit/` chạy sau đó trong CI thật (`pytest tests/
-q`, không `-n`, một tiến trình duy nhất cho toàn bộ suite).

## Bằng chứng tái hiện

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.. python -X faulthandler -m pytest tests/ -q
```

Trước khi sửa, faulthandler dump tại thời điểm crash (xem `BUG-065` cho toàn
bộ traceback) liệt kê, trong số các thread nền còn sống:

```
Thread 0x00007f2f2ac916c0 (most recent call first):
  File ".../sagittarius_engine/infrastructure/logging/tcp_log_viewer_handler.py", line 124 in _network_worker
```

Regression test dựng lại đúng cơ chế mà không cần suite đầy đủ — gọi thẳng
`StdLogger(config_manager)` với **đúng file `app_config.json` thật**, đúng
đường `create_app()` đi:

```
tests/unit/test_bug071_log_viewer_disabled_by_default.py::test_the_real_app_config_does_not_enable_the_tcp_log_viewer FAILED
tests/unit/test_bug071_log_viewer_disabled_by_default.py::test_a_std_logger_built_from_the_real_app_config_spawns_no_tcp_worker_thread FAILED
  AssertionError: StdLogger spawned ['Sagittarius-TcpLogWorker'] from the real app_config.json ...
```

## Root cause

`src/config/app_config.json:8` khai `"log.viewer.enabled": true` — **ngược
với** default của chính `LoggerConfig` engine (`viewer_enabled: bool = False`,
`sagittarius_engine/infrastructure/logging/logger_config.py`). Đây là tiện
ích dành cho **1 máy dev cụ thể** đang chạy `Sagittarius_LogViewer`, không
phải cấu hình phù hợp để commit làm mặc định chung — CI/test không có gì lắng
nghe ở `127.0.0.1:9999`, nên mọi App boot trong `tests/integration/`/
`tests/sanity/` đều rò 1 thread nền loop-mãi-mãi cho tới hết tiến trình.

**Không phải nguyên nhân chính của crash native đã báo cáo** — `BUG-065`
chứng minh crash đó tái hiện được (và không đổi gì) ngay cả khi chỉ chạy
`tests/unit/` một mình, nơi không có `App` nào được boot nên thread này không
hề tồn tại. Đây là 1 phát hiện phụ, độc lập, đáng sửa riêng.

## Fix

`src/config/app_config.json`: `"log.viewer.enabled": true` → `false`, khớp
đúng default an toàn của `LoggerConfig`. Một developer thật sự muốn dùng
LogViewer tự bật lại qua `user_config.json` (lớp ghi-đè cục bộ, không phải
default chung của repo).

## Regression test

`tests/unit/test_bug071_log_viewer_disabled_by_default.py` — 2 test:
1. `test_the_real_app_config_does_not_enable_the_tcp_log_viewer` — assertion
   cấp config, đọc thẳng `app_config.json` thật.
2. `test_a_std_logger_built_from_the_real_app_config_spawns_no_tcp_worker_thread`
   — assertion hành vi, dựng `StdLogger` thật từ config thật, kiểm
   `threading.enumerate()` không có thread `Sagittarius-TcpLogWorker` nào mới.

Cả hai **fail đúng lý do** trước khi sửa (xem log ở trên), **pass** sau khi
sửa.

## Xác minh

- `pytest tests/unit/test_bug071_log_viewer_disabled_by_default.py -v`: 2
  passed.
- `pytest tests/ -q` (toàn suite, tuần tự, không `-n`, khớp đúng lệnh CI thật)
  — sau khi sửa cả `BUG-071` và `BUG-065`: không còn thread
  `Sagittarius-TcpLogWorker` nào trong faulthandler dump của bất kỳ crash nào
  khác trong phiên (không còn crash nào để dump nữa — xem `BUG-065`).
