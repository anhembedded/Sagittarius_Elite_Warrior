# BUG-041 — App không thực sự thoát tiến trình khi có job nền đang chạy trên `ThreadManager`

**Trạng thái:** 🔴 Chưa sửa — nguyên nhân đã xác minh thật, fix chưa làm (ngoài phạm vi
`EPIC-006`, để lại cho task riêng)
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

## 3. Fix thật cần làm (chưa làm — ngoài phạm vi `EPIC-006`)

Cooperative cancellation xuyên suốt: truyền 1 `threading.Event` (hoặc token tương đương) vào
`ScanAllDatabasesQuery` handler
(`src/application/use_cases/queries/scan_all_databases/handler.py`), check giữa mỗi
symbol/interval trong vòng lặp quét, `set()` event đó từ `ThreadManagerExtension.shutdown()`
trước khi gọi `executor.shutdown()`. Cần quyết định API shape ở `IThreadManager`
(`Sagittarius_Engine`) trước — task riêng, không phải 1-dòng fix.

## 4. Không liên quan `EPIC-006`

Phát hiện giữa lúc làm `EPIC-006E` (Backtest QML migration) nhưng nguyên nhân nằm hoàn toàn ở
tầng threading/Application layer, không phải QML/QtWidgets. Không block epic này.
