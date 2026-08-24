# BUG-041 — App không thực sự thoát tiến trình khi có job nền đang chạy trên `ThreadManager`

**Trạng thái:** ✅ Fixed 2026-08-24 — root-caused, regression-tested ở unit +
process level, full CI verified
**Phát hiện:** 2026-08-24, user chạy app tay, thấy phải Ctrl+C mới thoát, log tiếp tục ghi
~68 giây sau khi "App stopped" đã in ra

---

## 1. Triệu chứng

Chạy app, vào Data Management, bấm auto-discover (quét toàn bộ Storage Vault — 1350 symbol ×
6 khung giờ). Đóng app / Ctrl+C. Log in ra đầy đủ chuỗi shutdown, kết ở dòng:

```
2026-08-24 17:02:22,417 - App - INFO - App stopped.
```

Nhưng tiến trình Python **không thoát** — một dòng log tiếp tục xuất hiện **68 giây sau đó**:

```
2026-08-24 17:03:30,037 - App - DEBUG - ScanAllDatabasesQuery completed successfully.
```

## 2. Nguyên nhân thật — xác minh bằng code, không đoán

[`ThreadManagerExtension.shutdown()`](../../../../Sagittarius_Engine/sagittarius_engine/extensions/thread_manager/thread_manager_module.py)
gọi `thread_manager.shutdown(wait=False)` với comment "individual tasks should still implement
cancellation tokens" — nhưng **không task nào trong `ScanCoordinator`
(`src/presentation/ui/screens/data_management/coordinators/scan_coordinator.py`) implement
cancellation token thật**. `run_auto_discover()`/`run_scan_all()` chỉ check
`_tracker.is_current_pending()` **sau khi** `dispatcher.dispatch(ScanAllDatabasesQuery, ...)` đã
return — quá muộn để dừng job đang chạy giữa chừng, chỉ ngăn UI cập nhật từ kết quả stale.

Verify trực tiếp source CPython 3.14 (`concurrent/futures/thread.py`): `ThreadPoolExecutor` tự
đăng ký `threading._register_atexit(_python_exit)` — hàm này **join mọi worker thread đã tạo
trong toàn tiến trình, bất kể `wait=` truyền vào `.shutdown()` là gì**:

```python
def _python_exit():
    global _shutdown
    with _global_shutdown_lock:
        _shutdown = True
    items = list(_threads_queues.items())
    for t, q in items:
        q.put(None)
    for t, q in items:
        t.join()          # <-- luôn join, không quan tâm wait=False
```

Đây là hành vi built-in của CPython (không phải bug của repo này) — `wait=False` chỉ khiến lệnh
gọi `.shutdown()` tự nó không block, nhưng interpreter vẫn treo ở bước thoát tiến trình chờ
worker thread thật sự xong. Vì `run_auto_discover()` không có cách nào ngắt sớm vòng quét 1350×6,
job đó chạy tới khi tự xong — đúng khớp với độ trễ 68s quan sát được.

## 3. Fix

Không cần đổi API `IThreadManager` ở Engine. `MainWindow.shutdown()` đã shutdown presenter
trước Engine, nên ownership đúng nằm ở app:

1. `ScanCoordinator` tạo và đăng ký một `CancellationToken` riêng **trước khi** mỗi scan được
   submit. Cách này phủ cả race “shutdown xảy ra trước khi worker bắt đầu chạy”.
2. `DataManagementPresenter.shutdown()` và nút Cancel gọi `ScanCoordinator.cancel()` để hủy
   mọi scan đang queued/running.
3. `ScanAllDatabasesQuery` mang callback `cancellation_requested`; handler kiểm tra trước shard
   discovery và trước từng symbol/interval pair. Các task executor đã queued lập tức trả về mà
   không mở/thăm DB mới.
4. Handler giữ log DEBUG dương tính:
   `Database scan observed cancellation and skipped queued pairs.` để chứng minh đường hủy thật
   sự chạy, đồng thời hữu ích cho chẩn đoán shutdown sau này.

## 4. Regression test và verification

- Red trước fix: 4 test fail đúng vì query không nhận `cancellation_requested`, coordinator
  không có `cancel()`, và presenter shutdown không gọi cancellation scan.
- Green sau fix: 49 unit tests liên quan scan/presenter pass.
- Process probe vĩnh viễn:
  `tests/integration/presentation/test_shutdown_database_scan_process.py` chạy
  `scripts/shutdown_database_scan_probe.py` với 2.000 pair, mỗi pair chậm 50 ms. Sau khi cancel,
  process hoàn tất trong khoảng 1,1 giây (timeout 5 giây) và phát đúng cancellation log. Không
  có fix, workload này cần khoảng 10 giây với 10 inner workers.
- `scripts/ci-local.ps1 -Full`: Ruff/format/Mypy pass, 1.700 tests + 38 sanity pass,
  coverage 93,07%, run log không có WARNING/ERROR/CRITICAL.

## 5. Không liên quan `EPIC-006`

Phát hiện giữa lúc làm `EPIC-006E` (Backtest QML migration) nhưng nguyên nhân nằm hoàn toàn ở
tầng threading/Application layer, không phải QML/QtWidgets. Không block epic này.
