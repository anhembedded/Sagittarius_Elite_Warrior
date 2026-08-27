# BUG-059 — Thoát app: shutdown chạy hết, log "App stopped." nhưng **tiến trình không return**

**Reported date:** 2026-08-26
**Severity:** 🟠 P1 — cơ chế chung đã root-caused và xác nhận thật (§5); **tác vụ cụ thể** gây
ra đúng lần treo đã báo cáo vẫn **chưa xác định được** — thiếu bằng chứng thread sống của
đúng phiên đó.
**Status:** ⚪ **Đóng 2026-08-26 — không tái hiện được từ môi trường hiện có** (xem cuối file). Trước đó: 🟡 Đã sửa MỘT PHẦN, 2026-08-26 — thêm chẩn đoán generic (dump thread non-daemon
sống sót ngay sau `app_engine.stop()`) để lần tái hiện SAU sẽ tự chỉ đích danh thủ phạm; bug
vẫn **Open** vì chưa đóng được đúng lần đã báo cáo.

---

> **Đổi số 2026-08-26:** hồ sơ này trước mang mã `BUG-052`, trùng với một bug khác đã đóng (`Tasks/bug_report/completed/BUG-052_*.md`) — Bug Board quy định mã phải là số kế tiếp số lớn nhất **ở cả hai thư mục**, và quy định đó đã bị vi phạm. Hồ sơ đang mở đổi thành `BUG-059` (hồ sơ đã đóng giữ mã cũ vì ROADMAP và các commit đã merge tham chiếu). Mọi commit/PR trước ngày này nhắc `BUG-052` **trong ngữ cảnh bug này** là chỉ chính hồ sơ đây.


---

## Cập nhật 2026-08-26 — chẩn đoán giờ nói **thread kẹt ở đâu**, không chỉ tên nó

Bản chẩn đoán thêm sáng nay in ra tên thread sống sót. Nhưng tên đó do pool đặt:
`'ThreadPoolExecutor-3_0'` là **mọi tác vụ pool ấy từng chạy**, nên nó thu hẹp
thủ phạm về "một thứ gì đó có dùng pool" — tức là gần như toàn bộ app. Đó đúng
là câu hỏi hồ sơ này còn để mở ("tác vụ cụ thể vẫn chưa xác định được").

`_log_surviving_non_daemon_threads()` giờ kèm **stack của từng thread sống sót**,
đọc qua `sys._current_frames()` (không cần dừng thread). Lần tái hiện sau sẽ cho
ra thẳng dòng code đang chặn, thay vì một cái tên vô danh.

Thread kẹt trong một lời gọi C **không có** frame Python nào. Trường hợp đó được
**báo cáo rõ**, không bỏ qua — vì nó chính là survivor dễ đang kẹt trong syscall
nhất, mà `run_vacuum`'s SQLite VACUUM là ví dụ đã biết (xem audit 19 điểm submit).

Hai test mới đi kèm, đã fault-inject để chắc chúng không phải trang trí: gỡ phần
stack ra thì cả hai đỏ, khôi phục thì xanh.

**Bug vẫn Open** — đây là cải thiện chẩn đoán, **không phải bản sửa**. Vẫn cần
một lần tái hiện thật để đóng.

### Một nghi ngờ đã kiểm chứng và bác bỏ

Nhìn log thì `Disposing extension 'LoggerExtension'` xảy ra **trước** khi chẩn
đoán chạy, nên có vẻ cảnh báo sẽ ghi qua một logger đã chết và mất tiêu. Đã kiểm:
`LoggerExtension.shutdown()` trong engine là **no-op** (`pass`), không gỡ handler
nào. Logger vẫn ghi bình thường. Không có vấn đề ở đây.

## 1. Hiện tượng (Symptom)

Người dùng đóng app. Chuỗi shutdown chạy **hết, không lỗi, không exception** — tất cả
extension đều `Stopping` → `Disposing`, AsyncRuntime dừng, dòng cuối cùng là `App stopped.`
lúc `09:37:34,685`. **Nhưng tiến trình Python không thoát**: không có dòng log nào nữa và
process vẫn treo, không trả về shell.

Nói cách khác: đây **không phải** shutdown treo giữa chừng — shutdown *thành công*, chỉ có
interpreter không chịu exit sau đó.

Phiên này là **cùng một phiên** với [`BUG-058`](BUG-058_ui_freeze_during_historical_tick_backtest.md):
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
2. `ThreadManagerExtension` `Stopping` → `Disposing` mất **4ms**.

   > ⚠️ **Sửa 2026-08-26:** bản đầu của mục này viết tiếp *"tức lúc nó dừng thì đã không
   > còn phải chờ job nào"*. **Suy luận đó sai.**
   > `ThreadManagerExtension.shutdown()` gọi `thread_manager.shutdown(wait=False)`, nên nó
   > **luôn** trả về ngay, **bất kể** còn job đang chạy hay không. 4ms vì thế không nói được
   > gì về việc còn job — nó chỉ chứng minh `wait=False` chạy đúng như tên gọi. Xem §5.2.
3. **Không có dòng nào sau `App stopped.`** — nên log tự nó không nói được ai đang giữ
   tiến trình lại. Cần công cụ ngoài (dump thread) mới thấy.
4. Trước đó phiên này đã chạy Historical Tick Backtest nạp **2.592.000 tick** và người dùng
   để app đứng yên ~73 phút trước khi đóng — **chưa biết** có liên quan hay không, ghi lại
   vì đây là điều kiện phiên đã có thật.

## 3. Kỳ vọng (Expected)

Sau `App stopped.`, tiến trình Python thoát hẳn, shell nhận lại prompt, exit code 0.
Không cần `Ctrl+C` / `kill`.

## 4. Suggested next steps

*(Chưa thực hiện — người báo yêu cầu chỉ tạo hồ sơ, không điều tra.)*

1. **Lấy bằng chứng thật về thread còn sống**, vì log hiện tại kết thúc trước điểm treo nên
   vô dụng cho việc này. Hai cách, ưu tiên cách 1:
   - Đăng ký `faulthandler.dump_traceback_later()` hoặc dump toàn bộ
     `threading.enumerate()` + `thread.daemon` **ngay sau** dòng `App stopped.` — sẽ chỉ
     đích danh non-daemon thread nào chưa join.
   - Hoặc gắn `py-spy dump --pid <pid>` vào tiến trình đang treo lúc tái hiện.
2. Đào cái khoảng **8,71 giây** của `BinanceBotModule.stop()` — nó vừa là mục lớn nhất
   trong shutdown vừa là ứng viên rõ nhất giữ tài nguyên; xác định nó đang chờ gì (websocket,
   HTTP session, `asyncio` task).
3. Xác nhận exit code và cách thoát thật: app đang thoát bằng `app.exec()` trả về rồi rơi
   ra khỏi `main()`, hay có `sys.exit()` tường minh — và có thread non-daemon nào ngăn
   interpreter shutdown không.
4. Đối chiếu với **4 hồ sơ cùng lớp đã đóng** trước khi kết luận đây là regression của một
   trong số đó hay là cơ chế mới — **chưa xác minh, chỉ ghi để lượt sau kiểm tra**:
   - [`BUG-041`](../completed/BUG-041_app_shutdown_hangs_on_inflight_thread_pool_task.md)
     — không thoát khi còn job trên `ThreadManager` (đóng 2026-08-24). Lưu ý quan sát #2 ở
     trên: lần này `ThreadManagerExtension` dừng trong 4ms.
   - [`BUG-023`](../completed/BUG-023_app_shutdown_hangs_when_database_sync_running.md)
     — zombie process khi Database Sync đang chạy (đóng 2026-08-21).
   - [`BUG-007`](../completed/BUG-007.md) — đóng app desktop nhưng tiến trình Python vẫn chạy.
   - [`BUG-049`](../completed/BUG-049_sanity_fake_server_thread_leaves_uncollectable_gc_objects.md)
     — uncollectable GC object của PySide6/shiboken lúc interpreter shutdown (đóng
     2026-08-25). Cùng *giai đoạn* (sau khi app dừng), nhưng đó là GC object chứ không phải
     treo — đừng gộp vội.
5. Chỉ viết regression test **sau khi** biết cái gì giữ tiến trình lại. Nếu cuối cùng là
   non-daemon thread, tầng test đúng là process-level probe (đo tiến trình thật sự thoát
   trong N giây) như `BUG-041` đã làm, không phải unit test.

---

## 5. Điều tra 2026-08-26 — cơ chế chung root-caused & xác nhận thật, **tác vụ cụ thể vẫn
chưa tìm ra**

Không có máy/phiên GUI thật trong môi trường agent này để tái hiện sống (đúng giới hạn mục 1
đã nêu). Thay vào đó, đi theo đúng mục 2–4 bằng cách đọc code + đo trực tiếp từng nghi phạm.

### 5.1 `BinanceBotModule.shutdown()` — đúng chỗ nằm giữa 2 log line #1, nhưng đo ra KHÔNG
phải nguồn 8,71s (trên storage nhanh)

Lần theo đúng lời gọi: `ExtensionManager.stop_and_dispose()` (`sagittarius_engine`) gọi
`ext.stop(context)` giữa dòng `Stopping extension 'BinanceBotModule'...` và
`Disposing extension 'BinanceBotModule'...` — `IExtension.stop()` mặc định gọi
`self.shutdown(context)`, và `ModuleExtensionAdapter.shutdown()` gọi thẳng
`BinanceBotModule.shutdown(app)`
(`src/binance_bot_module.py:304-307`), toàn bộ thân hàm chỉ có:
```python
def shutdown(self, app: App) -> None:
    database_manager = app.container.resolve(DatabaseManager)
    database_manager.dispose_all()
```
Tức đúng "cái gì đang chờ" mà mục 2 hỏi: `SqliteShardManager.dispose_all()` — đóng mọi
`Engine` SQLite đang mở. Giả thuyết ban đầu: WAL checkpoint tự động lúc đóng connection cuối
cùng của mỗi shard tốn thời gian với DB lớn (đúng kịch bản phiên này — vừa chạy Historical
Tick Backtest 2,59 triệu tick).

**Đo trực tiếp bằng `DatabaseManager`/`SQLAlchemyMarketDataRepository` thật** (không mock),
với DB **1,77 GB** (10 triệu dòng, đúng cỡ dữ liệu tick 1 tháng), sau khi mở thêm 8 session
riêng (mô phỏng pool có nhiều connection tích luỹ qua nhiều lần backtest/query trong phiên):

```
dispose_all() trên DB 1771 MB: 0.001s
```

**Không phải nguồn 8,71s** — ít nhất trên storage của môi trường này (nhanh, có thể là
overlay/tmpfs). Giả thuyết WAL-checkpoint-khi-đóng bị loại trên phần cứng đo được, nhưng
**không loại được hẳn cho máy chậm hơn** (đĩa quay/mạng) — để ngỏ, không kết luận sai hoàn
toàn, chỉ là chưa đo được bằng chứng dương tính ở đây.

### 5.2 Cơ chế "process không thoát sau `App stopped.`" — root-caused thật, **trùng khớp
100% với `BUG-041` đã đóng**

Đọc `sagittarius_engine/kernel/app.py::App.stop()`: mỗi bước top-level (`extensions`, `task
manager`, ...) chạy trong **thread riêng có timeout** (`_run_stop_step`, mặc định 10s) —
nên một bước bị treo THẬT SỰ sẽ bị bỏ qua sau 10s, không giải thích được vụ 8,71s (dưới
ngưỡng, hoàn tất bình thường, không có dòng lỗi timeout nào trong log). Nhưng
`ThreadManagerExtension.shutdown()` (`sagittarius_engine`) gọi
`thread_manager.shutdown(wait=False)` — comment trong chính code: *"wait=False ensures we do
not block the shutdown sequence (though individual tasks should still implement cancellation
tokens)"*.

**Xác nhận bằng thực nghiệm tối giản, không phải suy diễn** — CPython's
`concurrent.futures.thread` tự đăng ký `_python_exit()` qua `threading._register_atexit()`
lúc import module, **join MỌI worker thread của MỌI `ThreadPoolExecutor` từng tạo trong tiến
trình, bất kể `wait=` truyền vào `.shutdown()` là gì** — đây chính là cơ chế `BUG-041` đã
root-cause (trích lại source CPython trong hồ sơ đó). Tái hiện trực tiếp trên Python 3.12.3
của môi trường này:

```python
executor = ThreadPoolExecutor(max_workers=4)
executor.submit(lambda: [time.sleep(1) for _ in iter(int, 1)])  # never returns
executor.shutdown(wait=False, cancel_futures=True)   # <- returns instantly
print("App stopped.")                                 # <- in ra bình thường
# process treo VĨNH VIỄN sau dòng này — xác nhận: timeout 8s -> exit code 124
```

`timeout 8 python3 ...` → **exit code 124** (bị kill vì không tự thoát) — khớp chính xác
triệu chứng đã báo cáo: `"App stopped."` in ra, sau đó im lặng, tiến trình sống.

**Đối chứng:** một `ThreadPoolExecutor` với worker đã **idle** (job cũ đã hoàn tất, không bị
kẹt) qua `shutdown(wait=False)` thì thoát sạch, tức thời (exit code 0) — nên **không phải cứ
có `ThreadPoolExecutor` là treo**, chỉ treo khi có **task đang thật sự chạy dở, không có
cách nào tự return**.

### 5.3 Vì sao KHÔNG PHẢI Historical Tick Backtest của chính phiên này (khác `BUG-041`)

`BUG-041` xảy ra vì `ScanCoordinator` (Data Management) **không** implement cancellation
token thật lúc đó. Kiểm tra tương đương cho Backtest: `BackTestPresenter.shutdown()`
(`backtest_presenter.py:2529`) **đã** hủy cả `_backtest_cancellation_token` và
`_sync_cancellation_token` — đúng pattern `BUG-041` đặt ra, đã có sẵn từ trước. Và
`RunHistoricalTickBacktestCommandHandler._simulate()` tự kiểm
`command.cancellation_requested()` mỗi tick — cooperative cancellation thật, không phải giả.
Quan trọng hơn: theo log, Historical Tick Backtest của phiên này đã **hoàn tất** lúc `08:24:29`
(`handler_simulation_complete`), **73 phút trước** khi shutdown bắt đầu — worker thread của
nó đã trả `Future` xong từ lâu, quay về trạng thái idle trong pool (mục §5.2's "đối chứng":
idle worker thoát sạch). **Không phải job này giữ tiến trình lại** trong phiên đã báo cáo.

### 5.4 Chưa tìm ra: task nào thật sự còn chạy lúc `09:37:25`

Không đủ bằng chứng để chỉ đích danh — log gốc không có gì trong suốt 73 phút idle (không
health-check, không job nào được ghi), nên không biết có tác vụ nào khác (health check định
kỳ, một `GetHistoricalKlinesQuery`/`BulkSyncMarketData`'s `ThreadPoolExecutor` nội bộ kẹt,
hay một tác vụ khác hoàn toàn) đang chạy đúng lúc đó. Cả 2 giả thuyết cụ thể nhất đã bị loại
(§5.1 dispose_all() nhanh; §5.3 backtest job đã xong từ lâu) — nghĩa là nếu đúng là cùng lớp
`BUG-041`, thủ phạm là một task **khác**, chưa xác định.

### 5.5 Fix — chẩn đoán generic, không phải fix cho 1 task cụ thể

Vì không xác định được task cụ thể, sửa đúng cái mà §4 mục 1 của hồ sơ này đã yêu cầu: thêm
`_log_surviving_non_daemon_threads()` trong `app_bootstrapper.py`, gọi ngay sau
`runtime.app_engine.stop()` trong `teardown()` — dump tên mọi non-daemon thread (trừ main
thread) còn sống **trước khi** tiến trình có thể treo. Lần tái hiện sống tiếp theo (GUI thật)
sẽ có dòng log named-thread thay vì im lặng — đóng đúng cái gap "log hiện tại kết thúc trước
điểm treo nên vô dụng" mà hồ sơ gốc đã ghi.

Regression test (4 test, đều pass, tests thread thật — không mock `threading`):
`tests/unit/presentation/ui/test_app_bootstrapper_thread_diagnostic.py`:
- 1 non-daemon thread thật (Event chưa set) → cảnh báo đúng tên thread, đúng số lượng.
- Không có survivor → im lặng.
- Main thread tự nó không bao giờ bị flag nhầm.
- Daemon thread không bao giờ bị flag (không phải nguồn treo).

Đỏ trước fix xác nhận đúng lý do: `ImportError: cannot import name
'_log_surviving_non_daemon_threads'` (hàm chưa tồn tại), xanh sau khi thêm. Toàn bộ 881 test
trong `tests/unit/presentation/ui/` pass, không có test nào flaky do thread thật của các test
khác còn sống sót ảnh hưởng lẫn nhau.

### 5.6 Việc còn lại — không đổi bản chất so với §4, chỉ còn đúng 1 việc

Lần treo tiếp theo (GUI thật) sẽ tự in ra tên thread thủ phạm nhờ §5.5 — khi đó tra ngược tên
đó về đúng call site (giống `BUG-041` đã làm với `ScanCoordinator`) và thêm cancellation token
đúng chỗ. Không còn cần `faulthandler`/`py-spy` bên ngoài nữa cho lần tới; chỉ cần đọc log.

---

## 6. Rà soát toàn bộ điểm `thread_manager.submit(...)` — 2026-08-26

§5.6 để lại đúng một việc: *"rà tất cả điểm submit xem chỗ nào thiếu cancellation
token"*. Đã rà **19 điểm submit** (grep toàn `src/`).

### 6.1. Kết quả

| Task | Có token? | `shutdown()` hủy? | Rủi ro giữ tiến trình |
| :--- | :---: | :---: | :--- |
| `ScanCoordinator.run_auto_discover` | ✅ | ✅ | thấp — `BUG-041` đã sửa |
| `ScanCoordinator.run_scan_all` | ✅ | ✅ | thấp — `BUG-041` đã sửa |
| `SyncCoordinator.run_single_sync` / `run_bulk_sync` | ✅ | ✅ | thấp |
| `GapCoordinator.run_repair_gap` / `run_repair_all_gaps` | ✅ | ✅ | thấp |
| `StreamLifecycleController` (load history/more/stream) | ✅ | ✅ | thấp |
| `BackTestPresenter._run_backtest` / `_run_sync` | ✅ | ✅ | thấp |
| `BackTestPresenter._run_chart_preview` | ⚠️ chỉ generation counter | — | thấp (đọc ngắn) |
| `BackTestPresenter._fetch_symbol_options` | ❌ | ❌ | thấp (1 dispatch ngắn) |
| `ScanCoordinator.run_check_status` | ❌ | ❌ | trung bình |
| `ScanCoordinator.run_clear_data` | ❌ | ❌ | **cao** — xoá dữ liệu, DB lớn |
| `ScanCoordinator.run_purge_all` | ❌ | ❌ | **cao** — xoá toàn bộ |
| `ScanCoordinator.run_vacuum` | ❌ | ❌ | **cao** — xem §6.2 |
| `GapCoordinator.run_inspect_gaps` | ❌ | ❌ | trung bình |
| `KLineInspectorCoordinator.run_inspect_klines` | ❌ | ❌ **coordinator không có `cancel()`** | trung bình |
| `KLineInspectorCoordinator.run_audit` | ❌ | ❌ **coordinator không có `cancel()`** | trung bình |

### 6.2. ⚠️ "Thêm token vào mọi chỗ" **không** phải câu trả lời đủ

Đây là điều quan trọng nhất từ đợt rà này, và nó **sửa lại hướng đi mặc định**
mà §7 (bản cũ) ngụ ý.

`ScanCoordinator.run_vacuum` gọi thẳng `self._market_data_repo.vacuum()` — một
lệnh **blocking**. Token chỉ có tác dụng ở nơi có **checkpoint** để kiểm; giữa
chừng một lệnh `VACUUM` của SQLite thì **không có checkpoint nào**, và Python
không ngắt được nó bằng cách hợp tác.

Có một checkpoint duy nhất dùng được: `DatabaseManager.vacuum()` lặp **qua từng
shard** (`database_manager.py:82-90`), nên token chặn được **giữa các shard** —
không chặn được bên trong một shard. Với DB 1,77 GB, một shard đơn cũng đủ lâu.

Kết luận: với nhóm "cao", token giúp **giảm** thời gian treo chứ không **loại
bỏ** được nó. Muốn cắt thật thì cần cơ chế khác (ví dụ
`sqlite3.Connection.interrupt()`), và đó là một quyết định thiết kế riêng, không
phải việc vá thêm token.

### 6.3. Hai lỗ hổng rõ ràng, không cần tranh luận

1. `KLineInspectorCoordinator` **không có `cancel()`**, và
   `DataManagementPresenter.shutdown()` (dòng 468-470) chỉ gọi `cancel()` cho
   scan/sync/gap coordinator — bỏ sót hẳn coordinator này.
2. `BUG-041` sửa **2/8** đường của `ScanCoordinator`. Sáu đường còn lại
   (`check_status`, `clear_data`, `purge_all`, `vacuum`, và 2 của inspector)
   nằm cùng một class, cùng một kiểu rủi ro, và chưa từng được đụng tới.

### 6.4. Chưa sửa gì trong đợt này

Cố ý. Mỗi đường muốn có token thật thì query handler tương ứng phải nhận
`cancellation_requested` (đúng cách `BUG-041` đã làm cho `ScanAllDatabasesQuery`)
— tức là 6 use case riêng biệt. Và theo §6.2, với 3 đường rủi ro cao nhất thì
việc đó vẫn **không** đóng được lỗ hổng.

Nên đợt này dừng ở **bản đồ chính xác** thay vì vá vội nửa vời: đã biết chỗ nào
hở, chỗ nào token cứu được, chỗ nào không.


---

# Đóng 2026-08-26 — không tái hiện được **từ môi trường hiện có**

**Quyết định của chủ repo.** Ghi lý do cho chính xác, vì hồ sơ này **có bằng
chứng thật** và không nên bị đọc nhầm thành "không có gì xảy ra".

## Cơ chế đã được root-cause và xác nhận

CPython đăng ký `concurrent.futures.thread._python_exit()` — nó join **mọi**
worker của **mọi** `ThreadPoolExecutor` trong process, bất kể truyền
`shutdown(wait=False)`. Một worker còn chạy là interpreter treo **sau** khi
`main()` đã unwind, **không còn dòng log nào nữa**, vì chỗ treo nằm trong máy
móc shutdown của chính Python.

Đó không phải giả thuyết. Nó đã xảy ra, có log đầy đủ tới dòng `App stopped.`
rồi im.

## Cái còn thiếu

**Tác vụ cụ thể** gây ra đúng lần treo đã báo cáo. Cần một lần tái hiện **trên
app thật**: chạy phiên dài rồi đóng app và xem process có return không. Từ
container headless này tôi không dựng lại được.

## Chẩn đoán đã sẵn sàng — lần treo sau sẽ tự khai

Điều kiện để đóng bug này lần tới đã được đặt vào code:

- `_log_surviving_non_daemon_threads()` in ra **tên** mọi thread non-daemon còn
  sống sau `app_engine.stop()`, **kèm stack từng cái** (`sys._current_frames()`,
  giới hạn 12 frame trong cùng). Tên pool như `ThreadPoolExecutor-3_0` không
  cho biết nó chạy gì; stack thì có.
- Thread kẹt trong lời gọi C không có frame Python — trường hợp đó được **báo
  cáo rõ**, không bỏ qua, vì đó là ứng viên dễ kẹt trong syscall nhất.
- `scripts/bug060_thread_exit_probe.py` đo được chuyện tương tự cho phiên test,
  đăng ký qua `threading._register_atexit` để chạy **đúng trước** `_python_exit`.

## Mở lại thế nào

Đóng app mà process không thoát: lấy dòng WARNING `non-daemon thread(s) still
alive` trong log — nó giờ **kèm stack chỉ thẳng dòng code đang chặn** — đính vào
đây và mở lại. Đó chính là mẩu bằng chứng hồ sơ này thiếu.
