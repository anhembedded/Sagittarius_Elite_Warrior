# BUG-055 — Full gate treo/crash worker ở `tests/integration/presentation/ui/`: deadlock giữa `coverage.py` và Qt event loop

**Reported date:** 2026-08-26
**Severity:** 🟡 P2 — không sai kết quả, nhưng làm cổng verification bắt buộc không tin được
**Status:** 🔴 Open — **đã bắt được stack thủ phạm**, chưa sửa. Ghi lại để lượt sau
không mất một buổi mò như phiên này.

---

## 1. Hiện tượng (Symptom)

Chạy cổng bắt buộc (`pytest tests --cov ... -n 6`, đúng thứ `ci-local.ps1 -Full` gọi)
trên Linux 4 core, **7 lần chạy trong cùng một phiên** cho ra 4 kết quả khác nhau, mỗi
lần hỏng ở **một test khác nhau** nhưng **luôn** trong `tests/integration/presentation/ui/`:

| Lần | Cấu hình | Kết quả |
| :---: | :--- | :--- |
| 1 | `-n 6` + `--cov` | `worker 'gw0' crashed` — `test_dev_board_async_race_conditions.py::test_duplicate_closed_tick_for_same_timestamp_overwrites_not_duplicates` |
| 2 | `-n 6` + `--cov` | `worker 'gw0' crashed` — `test_dev_board_custom_scripts.py::test_unchecking_a_script_stops_it_from_running_on_the_next_load` |
| 3 | `-n 6` + `--cov` | ✅ 1802 passed, coverage 91,86% |
| 4 | `-n 6` + `--cov` | Treo vô hạn ở `test_dev_board_custom_scripts.py::test_unchecking_a_script...` — **CPU time đóng băng ở 42s trong khi wall chạy từ 655s lên 1254s** |
| 5 | `-n 6` + `--cov` | 1802 passed + 1 fail: `test_database_user_flow.py::test_database_cancel_button_cancels_active_sync_flow` (`qtbot.waitUntil` timeout 2000ms) |
| 6 | `-n 6` + `--cov` | Treo ở `test_dev_board_indicators.py::test_rsi_14_registers_as_a_subplot_script` |
| 7 | `-n 2` + `--cov` | 1802 passed + 1 `worker 'gw0' crashed` (lại đúng `test_unchecking_a_script...`) |

Mỗi test bị nêu tên, khi chạy **riêng file đó**, đều xanh ngay:

```
tests/integration/presentation/ui/test_dev_board_custom_scripts.py   3 passed in 10.02s
tests/integration/presentation/test_database_user_flow.py            1 passed in  3.03s
tests/integration/presentation/ui/  (cả nhóm, tuần tự)              36 passed in 111.39s
```

## 2. Root cause — đã bắt được stack

Chạy full suite **không xdist** (1 process duy nhất) cũng treo, và lần này dump được:

```
$ py-spy dump --pid 11432
Thread 11432 (idle): "MainThread"
    lock_data (coverage/collector.py:236)
    sizeHint (src/presentation/ui/components/app_log_panel.py:70)
    _process_events (pytestqt/plugin.py:220)
    pytest_runtest_setup (pytestqt/plugin.py:179)
    ...
```

Tiến trình nằm ở `futex_do_wait`, **43s CPU trên 1.212s wall**.

Main thread đang chờ **lock nội bộ của `coverage.py`** (`collector.py:236 lock_data`),
trong khi đang ở giữa một callback `sizeHint()` của Qt do `pytest-qt` bơm event
(`_process_events`). Đây là lớp lỗi reentrancy quen thuộc: Qt gọi ngược vào Python từ
trong C++ event loop, tracer của coverage phải lấy lock, mà lock đó đang do thread khác
giữ → deadlock. Cùng một điều kiện, ở tầng dưới `-n 6` thì biểu hiện thành
`worker crashed` (native) thay vì treo.

**Bằng chứng loại trừ coverage là biến độc lập:** cùng cây code, cùng `-n 6`, **chỉ bỏ
`--cov`**:

```
1803 passed, 4 skipped in 158.32s
```

Không crash, không treo, không flake.

## 3. Tại sao nó lọt vào tới giờ

`BOT-038` từng loại hẳn `tests/integration/presentation/ui/` khỏi cổng vì đúng lớp
segfault này. Ngày **2026-08-25** exclusion đó bị **gỡ**, với lý do ghi trong
`ci-local.ps1`: *"7 runs ... produced zero crash markers across the board"*. Số liệu ở
§1 mâu thuẫn trực tiếp với kết luận đó — 4/7 lần hỏng. Khác biệt có thể là số core
(máy này 4 core mà script mặc định 6 worker) hoặc phiên bản `coverage`/PySide6.

## 4. Suggested next steps

*(Chưa làm — hồ sơ này chỉ ghi nhận + chốt root cause, không sửa.)*

1. Xác nhận trên máy Windows của repo: chạy `ci-local.ps1 -Full` vài lần, xem có lặp
   lại tỉ lệ ~50% không. Nếu có thì đây **không** phải chuyện riêng của Linux/4-core.
2. Ba hướng sửa, chọn sau khi có số liệu bước 1:
   - Bỏ `tests/integration/presentation/ui/` ra khỏi **job có `--cov`**, chạy nó ở job
     riêng không coverage (giữ được cả coverage gate lẫn nhóm test, không phải xoá test
     nào — hợp `bug-fix-rule` §4).
   - Hoặc `--cov` với `concurrency=thread` / kiểm tra cấu hình `coverage` cho đa luồng.
   - Hoặc khôi phục exclusion của `BOT-038` — **hướng tệ nhất**, vì lại quay về "tier bị
     loại thì chứng minh được gì".
3. Cập nhật đoạn comment biện minh trong `ci-local.ps1` (dòng ~356) — hiện nó khẳng
   định crash "không tái hiện", đọc vào sẽ tin nhầm.

## 5. Ghi chú cho lượt sau

- **Đừng đọc console**, và cũng đừng chỉ nhìn dòng tổng kết pytest: cả 4 dạng hỏng ở §1
  đều **không** phải assertion fail. `worker crashed` và treo vô hạn không xuất hiện như
  test failure bình thường.
- Dấu hiệu nhận ra treo (khác với chậm): so `times` với `etimes` trong `ps` — CPU time
  đứng yên trong khi wall tăng nghĩa là deadlock, không phải tải nặng.
- `py-spy dump --pid <pid>` là công cụ duy nhất trong phiên này chỉ thẳng được thủ phạm.
