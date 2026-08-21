# BUG-031 — `QBasicTimer::start: Timers cannot be started from another thread` treo UI ở màn hình Backtest

**Reported date:** 2026-08-22
**Severity:** 🔴 **P1** (Treo/đóng băng UI hoàn toàn)
**Status:** ✅ Fixed 2026-08-22 (Root-caused / Reproduced / Regression-tested / Verified via Full CI)

---

## 1. Hiện tượng (Symptom)

Khi thao tác ở màn hình Backtest (chạy Static Backtest với symbol như `ETHUSDT` hoặc chuyển đổi biểu đồ trong khi `LiveStream` / background queries đang hoạt động), tiến trình xuất hiện liên tiếp thông điệp lỗi của Qt runtime:

```text
QBasicTimer::start: Timers cannot be started from another thread
QBasicTimer::start: Timers cannot be started from another thread
```

Toàn bộ giao diện người dùng (UI) bị đóng băng/treo (hang UI), không phản hồi tương tác click, cuộn hoặc chuyển tab.

### Bằng chứng Log thực tế (Captured Log Evidence)

```text
2026-08-22 00:36:34,710 - App - INFO - Executing command: SyncMarketDataCommand
2026-08-22 00:36:34,711 - App.SyncMarketData - INFO - Starting sync for symbols: ['ETHUSDT'] at interval 1m
2026-08-22 00:36:34,711 - App.SyncMarketData - INFO - [ETHUSDT] Syncing from explicit start time: 2026-08-21 17:33:00+00:00
2026-08-22 00:36:34,711 - App.ExchangeClient - INFO - Streaming historical klines for ETHUSDT at 1m from 21 Aug 2026 17:33:00 to 21 Aug 2026 17:36:34
2026-08-22 00:36:34,954 - App.ExchangeClient - INFO - Successfully streamed 2 klines for ETHUSDT.
2026-08-22 00:36:34,955 - App.SyncMarketData - INFO - [ETHUSDT] Successfully synced 2 klines.
2026-08-22 00:36:34,955 - App - INFO - Executing query: GetBacktestRangeCoverageQuery
2026-08-22 00:36:34,988 - App - INFO - Executing query: GetBacktestRangeCoverageQuery
2026-08-22 00:36:35,025 - App - INFO - Executing command: RunStaticBacktestCommand
2026-08-22 00:36:35,026 - App.RunStaticBacktest - INFO - BACKTEST_TRACE action=handler_execute_start symbol='ETHUSDT' timeframe='1m' strategy='support_resistance' start=None end=datetime.datetime(2026, 8, 21, 17, 35, 34, 634608, tzinfo=datetime.timezone.utc) has_params=False
2026-08-22 00:36:35,032 - App.RunStaticBacktest - INFO - BACKTEST_TRACE action=handler_klines_loaded count=10083
2026-08-22 00:36:35,032 - App.RunStaticBacktest - INFO - BACKTEST_TRACE action=handler_simulation_start
2026-08-22 00:36:35,033 - App.RunStaticBacktest - INFO - BACKTEST_TRACE action=handler_out_of_sample_split in_sample=7058 out_of_sample=3025
2026-08-22 00:36:35,033 - App.PaperExchange - INFO - [paper-exchange] Initialized for ETHUSDT | Initial Capital: 10,000.00 | Sizing: percent_of_equity (100.0) | Pyramiding: 1 | Slippage: 0 ticks | Commission: 0.1 (percent)
2026-08-22 00:36:35,159 - App.LiveStream - INFO - [Live Stream] ETHUSDT | Price: 2420.19 | Vol: 318.6019 | Closed: False
2026-08-22 00:36:35,159 - App.TradingStrategy - INFO - Processing tick for ETHUSDT at 2420.19
2026-08-22 00:36:35,366 - App.PaperExchange - INFO - [paper-exchange] Initialized for ETHUSDT | Initial Capital: 10,000.00 | Sizing: percent_of_equity (100.0) | Pyramiding: 1 | Slippage: 0 ticks | Commission: 0.1 (percent)
2026-08-22 00:36:35,519 - App.PaperExchange - INFO - [paper-exchange] Initialized for ETHUSDT | Initial Capital: 10,000.00 | Sizing: percent_of_equity (100.0) | Pyramiding: 1 | Slippage: 0 ticks | Commission: 0.1 (percent)
2026-08-22 00:36:36,029 - App.RunStaticBacktest - INFO - BACKTEST_TRACE action=handler_complete trades=0 net_profit_percent=0.0 out_of_sample=True
2026-08-22 00:36:36,030 - App.RunStaticBacktest - INFO - Static backtest complete for ETHUSDT: 0 trades, net profit 0.00%
2026-08-22 00:36:36,030 - App - INFO - Executing query: GetHistoricalKlinesQuery
2026-08-22 00:36:36,030 - App.QueryHandler - INFO - BACKTEST_TRACE action=query_execute_start symbol='ETHUSDT' timeframe='1m' limit=200000 start=None end=datetime.datetime(2026, 8, 21, 17, 35, 34, 634608, tzinfo=datetime.timezone.utc) order_by_desc=True
QBasicTimer::start: Timers cannot be started from another thread
QBasicTimer::start: Timers cannot be started from another thread
```

---

## 2. Nguyên nhân gốc rễ (Root Cause)

1. **Khởi động Timer sai luồng tại `_bind_top_panel_height` (`backtest_view.py:178`)**:
   - `BackTestView._bind_top_panel_height` kết nối signal `root.implicitHeightChanged` (từ QML root item `BackTestTopPanel.qml`) với closure `sync_height`.
   - `sync_height` sử dụng `QTimer.singleShot(0, apply_height)` để hoãn việc resize widget.
   - Khi QML tính toán lại thuộc tính layout trong các tình huống cập nhật hoặc chuyển trạng thái FSM, `root.implicitHeightChanged` được emit trực tiếp (direct invocation) trên luồng thực thi.
   - Nếu việc cập nhật diễn ra từ worker thread, `QTimer.singleShot` cố gắng kích hoạt `QBasicTimer::start()` từ worker thread (nơi không có Qt event loop).
   - Qt C++ runtime in cảnh báo `QBasicTimer::start: Timers cannot be started from another thread`, làm cờ `resize_pending` bị kẹt ở `True`, luồng QML/GUI bị lock và đóng băng giao diện.

2. **Thiếu `@Slot(str)` tại `BackTestViewModel.set_ui_mode` (`backtest_view_model.py:1282`)**:
   - `BackTestViewModel.set_ui_mode` ghi đè phương thức của `BaseQmlViewModel` nhưng không có decorator `@Slot(str)`, làm mất khả năng tự động marshal qua `Qt.QueuedConnection` khi được gọi từ các luồng khác.

---

## 3. Giải pháp (Fix)

1. **Sử dụng `QMetaObject.invokeMethod(self, "_apply_top_panel_height", Qt.ConnectionType.QueuedConnection)`**:
   - Chuyển `apply_height` và `apply_minimum_height` thành các `@Slot()` chính thức trên `BackTestView`.
   - Sử dụng cơ chế gọi hàng đợi luồng (`QueuedConnection`) của Qt để bảo đảm mọi thao tác điều chỉnh kích thước `setFixedHeight` / `setMinimumHeight` luôn được đẩy về Main GUI Thread an toàn tuyệt đối.

2. **Bổ sung `@Slot(str)` cho `BackTestViewModel.set_ui_mode`**:
   - Đảm bảo tuân thủ đầy đủ Layer 1 Thread-Affinity Sanity Guard (`unprotected_mutators`).

---

## 4. Regression Test & Verification

- **Test file:** `tests/unit/presentation/ui/screens/test_bug031_cross_thread_timer.py`
  - `test_backtest_view_model_set_ui_mode_has_slot_decorator`: Đảm bảo `set_ui_mode` được bảo vệ bởi `@Slot`.
  - `test_backtest_view_sync_height_safe_from_worker_thread`: Giả lập phát tín hiệu `implicitHeightChanged` từ background thread và xác nhận layout update hoàn tất không lỗi timer.
- **Verification:**
  - `.\scripts\ci-local.ps1 -Full` -> **PASS 100% (1763 unit tests, 50 sanity tests, 0 warnings/errors, 93.56% coverage)**.
