# BUG-054 — Thoát app: shutdown chạy hết, log "App stopped." nhưng **tiến trình không return**

**Reported date:** 2026-08-26
**Severity:** Chưa đánh giá (chưa điều tra)
**Status:** 🔴 Open — chỉ mới ghi nhận hiện tượng theo yêu cầu người báo,
**chưa điều tra root cause**.

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
