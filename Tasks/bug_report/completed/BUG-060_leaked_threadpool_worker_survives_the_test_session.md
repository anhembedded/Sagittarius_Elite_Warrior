# BUG-060 — Một `ThreadPoolExecutor` worker sống sót qua cả phiên test

| Trường | Giá trị |
| :--- | :--- |
| **Trạng thái** | ✅ **Đóng 2026-08-26 — không tái hiện được**, đo bằng probe đã kiểm chứng (§Kết luận) |
| **Mức độ** | Trung bình (bẩn phiên test; đúng lớp hazard của `BUG-052`/`BUG-059` ở production) |
| **Phát hiện** | 2026-08-26, khi chạy full suite với thứ tự cố định |
| **Liên quan** | `BUG-059` (process không thoát sau graceful shutdown), `BUG-041` |
| **Probe** | [`scripts/bug060_thread_exit_probe.py`](../../../scripts/bug060_thread_exit_probe.py) |

## Hiện tượng gốc

Ba test trong `test_app_bootstrapper_thread_diagnostic.py` cùng đỏ khi chạy
chung cả suite, riêng thì xanh:

```
E  AssertionError: Expected 'warning' to not have been called. Called 1 times.
E  Calls: [call("1 non-daemon thread(s) still alive after engine shutdown —
E     ... 'ThreadPoolExecutor-44_0'")]
```

Phần test assert nhầm phạm vi đã sửa trong PR #114 (fixture `only_these_threads`).
Câu hỏi còn lại — **worker có thật sự rò không** — là nội dung bug này.

## Kết luận: không tái hiện được

Full suite, một lần gọi duy nhất, 12 xdist worker + process điều phối,
`2279 passed, 4 skipped`:

```
THREAD NON-DAEMON CÒN SỐNG NGAY TRƯỚC KHI _python_exit JOIN
  (không có)
```

Giờ tường 136.5s so với 136.0s pytest tự báo — chênh 0.5s, không có treo lúc thoát.

Nguyên nhân nhiều khả năng đã được đóng bởi hai thay đổi trước đó, không phải
bởi bug này: teardown `thread_manager.shutdown(wait=True)` thêm vào
`tests/integration/presentation/ui/conftest.py` (công việc `BUG-056`), và
PR #114. **Không tìm ra root cause** — điều kiện gây ra nó đơn giản là không
còn. Probe được giữ lại để chạy lại bất cứ lúc nào nghi ngờ.

## Hai lần đo sai trước khi đo đúng — phần đáng đọc nhất của hồ sơ này

Hai probe đầu **đều báo "sạch" hoặc báo rò giả**, và cả hai đều đọc y hệt một
kết quả thật.

**Sai lầm 1 — đo trước khi fixture teardown chạy.** Probe đầu diff
`threading.enumerate()` trong `pytest_runtest_teardown`. Hook đó chạy *trước*
finalizer của fixture, nên **18 test** hiện ra như đang rò, gồm cả những test
dọn dẹp hoàn hảo. Danh sách 18 dòng `LEAK after ...` trông rất thuyết phục.
Chuyển sang `pytest_runtest_logfinish` (chạy sau toàn bộ setup/call/teardown)
thì cả 18 biến mất.

**Sai lầm 2 — dùng `atexit`, vốn chạy quá MUỘN.** Nghiêm trọng hơn nhiều, vì
nó cho ra sự im lặng, và im lặng thì dễ bị đọc thành "không có rò". Thứ tự
finalize của CPython là

```
Py_FinalizeEx -> threading._shutdown() -> ... -> callback của atexit
```

và `threading._shutdown()` vừa chạy danh sách `_threading_atexits` vừa **join
mọi thread non-daemon** — kiểm chứng ngay trong source của nó: *"Call
registered threading atexit functions before threads are joined"*, rồi *"Join
all non-deamon threads"*. `concurrent.futures.thread._python_exit` nằm trên
danh sách đó, **không** nằm trên `atexit`.

Nên một probe `atexit` báo cáo *sau khi* mọi thread non-daemon đã bị join, và
**về mặt cấu trúc chỉ có thể in ra rỗng**. Tôi đã chạy nó trên unit,
integration, sanity và cả full suite, nhận "không có" bốn lần, và suýt kết
luận từ đó. Bản sửa đăng ký lên đúng danh sách kia
(`threading._register_atexit`, danh sách được duyệt ngược nên nó chạy ngay
trước `_python_exit`).

**Bài học rút ra, đã ghi vào docstring của probe:** một probe chưa được chứng
minh là *bắt được* rò thật thì tệ hơn không có probe. Positive control dùng để
kiểm chứng — một test cố tình rò executor — nằm trong docstring; bản `atexit`
trượt nó, bản `threading._register_atexit` bắt đúng tên worker.

## Cách chạy lại

```bash
PYTHONPATH=scripts:. BUG060_PROBE_OUT=/tmp/probe.txt QT_QPA_PLATFORM=offscreen \
  pytest tests -p bug060_thread_exit_probe -n 12
cat /tmp/probe.txt     # rỗng = không rò
```

## Ghi chú: `booted_app` không phải rò

Probe trung gian từng chỉ vào `ThreadPoolExecutor-10_0` sống dai qua mọi test
sanity. Đó là fixture `booted_app` **scope=session** đang làm đúng việc của
nó, và `app.stop()` dọn nó ở cuối. Không phải khiếm khuyết.
