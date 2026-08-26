# BUG-060 — Một `ThreadPoolExecutor` worker sống sót qua cả phiên test

| Trường | Giá trị |
| :--- | :--- |
| **Trạng thái** | 🔴 Mở — chưa tìm ra test nào rò |
| **Mức độ** | Trung bình (bẩn phiên test; đúng lớp hazard của `BUG-052` ở production) |
| **Phát hiện** | 2026-08-26, khi chạy full suite với thứ tự cố định (`-p no:randomly`) |
| **Liên quan** | `BUG-052` (process không thoát sau graceful shutdown), `BUG-041` |

## Hiện tượng

Chạy full suite với thứ tự cố định, ba test trong
`tests/unit/presentation/ui/test_app_bootstrapper_thread_diagnostic.py` cùng đỏ:

```
E  AssertionError: Expected 'warning' to not have been called. Called 1 times.
E  Calls: [call("1 non-daemon thread(s) still alive after engine shutdown —
E     the process will hang at exit until they finish (BUG-052 class):
E     'ThreadPoolExecutor-44_0'")]
```

Chạy riêng file đó: **4 passed**. Chỉ đỏ khi chạy chung cả suite.

Đáng chú ý: `_log_surviving_non_daemon_threads()` **không hề sai** ở đây — nó
báo đúng một thứ có thật. Worker `ThreadPoolExecutor-44_0` thật sự còn sống.
Cái sai chỉ là ba test kia assert lên global thread state của cả process mà
chúng không sở hữu; phần đó đã sửa (xem "Đã làm" bên dưới) và **không** đóng
bug này.

## Vì sao vẫn để mở

`ThreadPoolExecutor` tạo worker **non-daemon**, và chúng sống cho tới khi pool
được `shutdown()`. Một test nào đó dựng `IThreadManager`/executor, `submit()`
việc vào đó, rồi kết thúc mà không shutdown — nên worker ở lại tới hết phiên.

Đây **đúng là** cơ chế `BUG-052` mô tả: CPython đăng ký
`concurrent.futures.thread._python_exit()` như một atexit hook, join mọi worker
của mọi executor bất kể `wait=` truyền gì. Một worker rò trong suite hôm nay là
một worker rò trong app ngày mai. Suite đang chứng minh chính cái hazard nó
được viết ra để bắt.

## Bước điều tra tiếp theo

Chưa làm — chưa xác định được test nào rò:

1. Thêm một fixture `autouse` phạm vi session chụp `threading.enumerate()`
   trước/sau **mỗi** test, in ra test đầu tiên làm số worker non-daemon tăng.
   Số `44` trong `ThreadPoolExecutor-44_0` là bộ đếm executor toàn process —
   nó cho biết đã có 44 executor được tạo trước đó, không cho biết ai.
2. Test đó thiếu `shutdown()` hay có `shutdown(wait=False)` với task không
   hợp tác huỷ (đúng shape `BUG-041`)? Hai hướng sửa khác hẳn nhau.
3. Nếu là fixture dùng chung, sửa ở fixture; nếu là một test lẻ, sửa tại chỗ.

## Đã làm (không phải bản sửa cho bug này)

`test_app_bootstrapper_thread_diagnostic.py` giờ tự kiểm soát cái nó assert:
fixture `only_these_threads` truyền thẳng danh sách thread vào phép đếm, nên ba
test "phải im lặng" mô tả đúng kịch bản của chúng thay vì mô tả cả suite. Một
test vẫn chạy trên `threading.enumerate()` thật và chỉ assert theo **tên**
thread nó tạo ra — không assert số lượng, vì mọi thread non-daemon còn sống
khác đều là survivor mà diagnostic báo đúng.

Điều đó làm CI xanh **một cách trung thực** (test không còn assert nhầm phạm
vi), nhưng worker rò thì vẫn còn nguyên đó.
