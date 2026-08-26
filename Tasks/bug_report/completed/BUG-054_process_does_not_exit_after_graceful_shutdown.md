# BUG-054 — Thoát app: shutdown chạy hết, log "App stopped." nhưng **tiến trình không return**

**Reported date:** 2026-08-26
**Severity:** 🔴 **P1** — tiến trình zombie, phải `kill -9` (không chết bằng `SIGTERM`)
**Status:** ✅ **Fixed 2026-08-26** — cơ chế tái hiện được 1:1 bằng fault injection,
regression test đỏ-đúng-lý-do (treo vô hạn) trước fix, xanh sau. Xem §7 về phần
**chưa** xác định được: job cụ thể nào còn chạy trong phiên của người báo.

---

## 1. Hiện tượng (Symptom)

Người dùng đóng app. Chuỗi shutdown chạy **hết, không lỗi, không exception** — tất cả
extension đều `Stopping` → `Disposing`, AsyncRuntime dừng, dòng cuối cùng là `App stopped.`
lúc `09:37:34,685`. **Nhưng tiến trình Python không thoát**: không có dòng log nào nữa và
process vẫn treo, không trả về shell.

Nói cách khác: đây **không phải** shutdown treo giữa chừng — shutdown *thành công*, chỉ có
interpreter không chịu exit sau đó.

Phiên này là **cùng một phiên** với [`BUG-053`](BUG-053_ui_freeze_during_historical_tick_backtest.md):
boot `08:15:18`, chạy Historical Tick Backtest (2.592.000 tick) xong lúc `08:24:29`, ngồi
im ~73 phút, rồi đóng app lúc `09:37:25`.

### Trích log nguyên văn (toàn bộ đoạn shutdown)

```text
2026-08-26 08:24:29,222 - App.ChartCard - INFO - [chart-data] ChartCard(BTCUSDT): chart type applied=candlestick
2026-08-26 09:37:25,859 - App - INFO - App is stopping gracefully...
2026-08-26 09:37:25,925 - App - INFO - Scheduler stopped.
2026-08-26 09:37:25,931 - App - INFO - Stopping Hosted Service 'LiveStreamEngineAdapter'...
2026-08-26 09:37:25,932 - App.LiveStreamAdapter - INFO - Engine shutting down, ensuring stream is stopped...
2026-08-26 09:37:25,942 - App - INFO - Stopping extension 'HealthExtension'...
2026-08-26 09:37:25,944 - App - INFO - Disposing extension 'HealthExtension'...
2026-08-26 09:37:25,945 - App - INFO - Stopping extension 'BinanceBotModule'...
2026-08-26 09:37:34,655 - App - INFO - Disposing extension 'BinanceBotModule'...
2026-08-26 09:37:34,657 - App - INFO - Stopping extension 'ThreadManagerExtension'...
2026-08-26 09:37:34,661 - App - INFO - Disposing extension 'ThreadManagerExtension'...
2026-08-26 09:37:34,661 - App - INFO - Stopping extension 'LoggerExtension'...
2026-08-26 09:37:34,663 - App - INFO - Disposing extension 'LoggerExtension'...
2026-08-26 09:37:34,664 - App - INFO - Stopping extension 'AssetValidatorExtension'...
2026-08-26 09:37:34,664 - App - INFO - Disposing extension 'AssetValidatorExtension'...
2026-08-26 09:37:34,665 - App - INFO - Stopping extension 'DependencyValidatorExtension'...
2026-08-26 09:37:34,665 - App - INFO - Disposing extension 'DependencyValidatorExtension'...
2026-08-26 09:37:34,670 - App - INFO - Stopping AsyncRuntime event loop...
2026-08-26 09:37:34,684 - App - INFO - AsyncRuntime event loop stopped.
2026-08-26 09:37:34,685 - App - INFO - App stopped.
```

*(Hết log — sau dòng này không còn gì, tiến trình vẫn sống.)*

## 2. Quan sát thô từ log (chưa phải root cause — **chưa điều tra**)

Chỉ ghi những gì đọc **trực tiếp** được:

1. Toàn bộ shutdown mất **8,8 giây** (`09:37:25,859` → `09:37:34,685`), và **8,71s trong
   số đó nằm gọn ở một chỗ duy nhất**: giữa `Stopping extension 'BinanceBotModule'...`
   (`25,945`) và `Disposing extension 'BinanceBotModule'...` (`34,655`). Mọi extension khác
   đều xong trong 1–3ms.
2. `ThreadManagerExtension` `Stopping` → `Disposing` mất **4ms** — tức lúc nó dừng thì đã
   không còn phải chờ job nào.
3. **Không có dòng nào sau `App stopped.`** — nên log tự nó không nói được ai đang giữ
   tiến trình lại. Cần công cụ ngoài (dump thread) mới thấy.
4. Trước đó phiên này đã chạy Historical Tick Backtest nạp **2.592.000 tick** và người dùng
   để app đứng yên ~73 phút trước khi đóng — **chưa biết** có liên quan hay không, ghi lại
   vì đây là điều kiện phiên đã có thật.

## 3. Kỳ vọng (Expected)

Sau `App stopped.`, tiến trình Python thoát hẳn, shell nhận lại prompt, exit code 0.
Không cần `Ctrl+C` / `kill`.

## 4. Root cause

**Cơ chế: `teardown()` xong không có nghĩa là tiến trình chết được.** Chỗ treo
nằm sau dòng log cuối cùng, trong chính trình tự thoát của CPython chứ không
phải trong code của app.

Chuỗi sự kiện:

1. `app_bootstrapper.main()` chạy `teardown()` → `app_engine.stop()` → log
   `App stopped.` **Xong sạch, không lỗi** — đúng như log của người báo.
2. Cả hai pool chạy nền của hệ thống đều là `ThreadPoolExecutor`:
   `ThreadManager` (engine, app dùng cho mọi `presenter.submit()`) và
   `TaskManager` (`background_executor` 20 worker + `critical_executor` 10).
   Từ Python 3.9, worker của `ThreadPoolExecutor` là **non-daemon**, không còn
   cờ `daemon` để đặt.
3. Cả hai đều được tắt bằng `shutdown(wait=False, cancel_futures=True)` —
   `ThreadManagerExtension.shutdown()` ghi rõ lý do: *"wait=False ensures we do
   not block the shutdown sequence"*. `wait=False` trả về ngay; task **đang
   chạy** thì không bị huỷ (`cancel_futures` chỉ huỷ cái còn nằm trong hàng đợi).
4. `main()` gọi `sys.exit()` → CPython chạy `atexit` → `concurrent.futures.thread._python_exit`
   **join mọi worker thread, không timeout**.
5. Một task chưa xong ở bước 3 → bước 4 treo **vĩnh viễn**, sau dòng log cuối,
   không in thêm gì.

Nói gọn: `wait=False` không tránh được việc chờ, nó chỉ **dời** việc chờ từ chỗ
có log và có timeout sang chỗ không có gì cả.

### Bằng chứng — tái hiện 1:1

**(a) Cơ chế trần**, không dính gì tới app:

```python
ex = ThreadPoolExecutor(max_workers=4)
ex.submit(lambda: time.sleep(3600))
ex.shutdown(wait=False, cancel_futures=True)
print("App stopped.")
sys.exit(0)
```

```
shutdown(wait=False) returned; threads: [('MainThread', False), ('ThreadPoolExecutor-0_0', False)]
App stopped.
EXIT=124   ← timeout, tiến trình treo
```

**(b) Chính ứng dụng thật.** `scripts/bug054_stuck_worker_exit_probe.py` là
`main()` cộng đúng **một** dòng — một task không bao giờ trả về, submit vào
`IThreadManager` thật. Chạy với đường thoát cũ (`sys.exit()`), log dừng đúng
chỗ log của người báo dừng:

```
2026-08-26 03:10:26,403 - App - INFO - Stopping AsyncRuntime event loop...
2026-08-26 03:10:26,403 - App - INFO - AsyncRuntime event loop stopped.
2026-08-26 03:10:26,404 - App - INFO - App stopped.
```

…rồi treo. Đáng chú ý: **`SIGTERM` không giết được nó** — handler
`setup_qt_signal_handling()` gọi `app.quit()`, mà event loop thì đã chết từ
lâu, nên tín hiệu vào rồi rơi vào hư không và `join()` chạy tiếp. Phải
`SIGKILL`. Khớp với mô tả "thoát app, nhưng process not return".

### Khớp lại với các quan sát ở §2

| Quan sát §2 | Ý nghĩa sau khi biết cơ chế |
| :--- | :--- |
| #3 không có dòng nào sau `App stopped.` | Đúng định nghĩa: chỗ treo nằm **ngoài** code app, sau `atexit` |
| #2 `ThreadManagerExtension` dừng trong 4ms | Đúng — `shutdown(wait=False)` **không chờ**. 4ms này từng bị đọc nhầm thành "không còn job nào", thực ra nó không nói gì về job cả |
| #1 8,71s ở `BinanceBotModule.stop()` | Là `DatabaseManager.dispose_all()`, chậm nhưng **hoàn tất** (dưới ngưỡng 10s/bước của `App._run_stop_step`, không có dòng `did not stop within`). Chậm, không phải nguyên nhân treo |

## 5. Fix

Thêm `src/presentation/ui/common/process_exit.py`; `main()` gọi `exit_process(exit_code)`
thay cho `sys.exit(exit_code)`. Ba bước, theo đúng thứ tự đó:

1. Không còn thread non-daemon nào → `sys.exit()` y như cũ. **Đường sạch không
   đổi một chút nào** — nếu mọi lần thoát đều đi đường cưỡng bức thì sẽ bỏ qua
   `atexit` và flush buffer ở cả những lần chạy lành lặn, tức là đổi lấy một bug
   tệ hơn.
2. Còn thread → chờ tối đa 5s (task gần xong là trường hợp phổ biến), log
   `INFO` cho biết đang chờ ai.
3. Hết 5s vẫn còn → log `WARNING` kèm **tên và stack của từng thread**, flush
   logging, rồi `os._exit(exit_code)` — lời gọi duy nhất không đi qua đám
   `join()` kia.

Bước 3 quan trọng không kém bước thoát: log của người báo chết ở `App stopped.`
với **không một chữ nào** về thứ đang giữ tiến trình lại, nên chính người báo
cũng không thể chỉ ra thủ phạm. Từ giờ lần treo tiếp theo tự khai tên nó.

**Tại sao đủ:** không còn đường nào để một worker giữ tiến trình sống vô hạn;
xấu nhất là chậm thêm 5 giây, có log giải thích.

## 6. Regression test

**`tests/sanity/test_bug054_stuck_worker_exit.py`** — tầng duy nhất chứng minh
được: chạy `scripts/bug054_stuck_worker_exit_probe.py` bằng `subprocess.run(...)`
với budget 45s. Trước fix: treo vô hạn (`TimeoutExpired`, phải `SIGKILL`). Sau
fix: exit code 0 trong 9,5s, và log có đủ `App stopped.`, `[process-exit]`, tên
thread `ThreadPoolExecutor`.

**`tests/unit/presentation/ui/common/test_process_exit.py`** — 4 test cho phần
in-process mà tầng kia không nhìn thấy: đường sạch vẫn `sys.exit` (không được
cưỡng bức mọi lần), thread non-daemon sống dai thì cưỡng bức **và bị nêu tên**,
worker xong trong grace period thì vẫn đi đường sạch, thread daemon không bao
giờ bị tính (watchdog monitor thread của engine là daemon — tính nhầm là mọi lần
thoát lành mạnh đều đi đường cưỡng bức).

Chọn tầng theo `bug-fix-rule.md` §3: một test in-process không thể giết tiến
trình, một test tiến trình không cho biết nó đã rẽ nhánh nào. Cần cả hai.

## 7. Phần CHƯA xác định được — đọc trước khi đóng lại lần sau

**Không xác định được job cụ thể nào còn chạy trong phiên của người báo.** Log
kết thúc trước điểm treo, và tiến trình đó không còn để dump. Những gì log
**loại trừ** được:

- Không phải task của `TaskManager`: `TaskManager.shutdown()` log
  `WARNING - TaskManager shutting down with N active tasks still running: ...`
  khi còn task — log không có dòng này.
- Không phải bước shutdown nào bị treo: `App._run_stop_step` log
  `did not stop within 10s` cho bước quá hạn — cũng không có.

Còn lại `ThreadManager` (pool app dùng cho presenter), **không log gì cả** khi
tắt. Đó là lý do bước 3 của fix tồn tại: lần sau nó tự chỉ mặt.

Fix này chữa **lớp lỗi** (tiến trình luôn thoát được, và luôn nói vì sao), không
chữa riêng job kia. Nếu `WARNING [process-exit]` xuất hiện trên máy thật, hãy mở
hồ sơ tiếp cho đúng job mà nó nêu tên — một worker chạy mãi vẫn là bug riêng của
nó, chỉ là không còn treo được máy nữa.
