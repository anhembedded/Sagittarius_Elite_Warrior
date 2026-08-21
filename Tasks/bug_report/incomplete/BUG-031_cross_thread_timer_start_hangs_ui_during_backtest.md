# BUG-031 — `QBasicTimer::start: Timers cannot be started from another thread` treo UI ở màn hình Backtest

**Reported date:** 2026-08-22
**Severity:** 🔴 **P1** (Treo/đóng băng UI hoàn toàn)
**Status:** Open

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

## 2. Phân tích nguyên nhân & Giả thuyết (Investigation & Hypotheses)

Lỗi `QBasicTimer::start: Timers cannot be started from another thread` là cơ chế phòng vệ của Qt: một đối tượng kế thừa `QObject` (hoặc `QWidget`, `QQuickWidget`, `QTimer`, `pyqtgraph` component) đang sở hữu timer hoặc kích hoạt animation/timer nhưng lại bị gọi trực tiếp từ **background worker thread** (luồng phụ) thay vì chạy trên **Qt Main UI Thread**.

Các điểm nghi vấn cần kiểm tra:
1. **`GetHistoricalKlinesQuery` completion callback / Presenter worker slots:** Khi background query trả về dữ liệu klines, callback có trực tiếp thao tác vào `ChartCard` / `NativeChartItem` / `range_update_scheduler` / `cached_frame_interaction` mà không đi qua Qt Signal với QueuedConnection không?
2. **`LiveStream` EventBus / TradingStrategy handlers:** Trong khi live streaming đang nhận ticks trên background thread, có slot nào trên `BackTestPresenter` hoặc `DashboardPresenter` lắng nghe sự kiện event bus và gọi trực tiếp vào UI/Timer mà không dispatch qua `IThreadManager` / Qt Signals?
3. **`RangeUpdateScheduler` / `CachedFrameInteraction` timers:** Kiểm tra các hàm `start_range_update`, `_wheel_timer`, hoặc `QTimer.singleShot` trong `chart_card` có bị kích hoạt từ luồng background không.

---

## 3. Các bước tiếp theo (Suggested Next Steps per `bug-fix-rule.md`)

1. **Thêm logging chẩn đoán Thread ID (`QThread.currentThread()` / `threading.get_ident()`):**
   - Đặt log ở điểm bắt đầu các callback sau `GetHistoricalKlinesQuery` và các slot xử lý `LiveStream` / `RunStaticBacktestCommand`.
2. **Xác định chính xác call-chain dẫn đến `QBasicTimer::start` trên worker thread.**
3. **Viết Regression Test tái hiện:**
   - Viết test chứng minh gọi method đó từ thread phụ phát sinh lỗi / warning thread affinity.
4. **Áp dụng giải pháp điều hướng qua Qt Signal / Main Thread Dispatcher.**
5. **Chạy kiểm tra Full CI (`ci-local.ps1 -Full`) đảm bảo 0 log problem-level và đóng bug report.**
