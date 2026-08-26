# BUG-053 — UI đơ nhiều lần (5.1s → 69.1s) trong lúc chạy Historical Tick Backtest

**Reported date:** 2026-08-26
**Severity:** Chưa đánh giá (chưa điều tra)
**Status:** 🔴 Open — chỉ mới ghi nhận hiện tượng theo yêu cầu người báo,
**chưa điều tra root cause**.

---

## 1. Hiện tượng (Symptom)

Trong một phiên chạy app thật (`main_window.py`, Qt platform `wayland`, DPR 2), UI **đơ
(block) nhiều lần** — watchdog `UI FREEZE DETECTED` bắn **5 lần** trong khoảng 4 phút, lần
lâu nhất **69,1 giây**. App không crash, mỗi lần đều tự phục hồi (`UI Thread recovered from
freeze`).

Bảng các lần đơ, đọc thẳng từ log người báo cung cấp:

| # | Thời điểm cảnh báo | Thời lượng đơ | Đang chạy gì (theo log gần nhất trước đó) |
| :---: | :--- | :---: | :--- |
| 1 | `08:20:05,306` | **5.1s** | `RunHistoricalTickBacktestCommand` (`5m` / tick `1s`, 604.800 tick), `handler_ticks_loaded` lúc `08:19:57` |
| 2 | `08:22:37,745` | **69.1s** | `RunHistoricalTickBacktestCommand` (`1h` / tick `1s`, 2.592.000 tick) bắt đầu `08:21:05`, chưa tới `ticks_loaded` |
| 3 | `08:23:31,488` | **13.8s** | cùng lần chạy `1h` ở trên, vẫn chưa tới `ticks_loaded` (`08:23:40`) |
| 4 | `08:24:04,808` | **5.3s** | sau `PaperExchange` init `08:23:40`, đang mô phỏng |
| 5 | `08:24:14,863` | **5.5s** | vẫn trong mô phỏng, tới `simulation_complete` lúc `08:24:28` |

Ngưỡng watchdog đang là `5.0s`.

### Trích log nguyên văn (rút gọn phần không liên quan)

```text
2026-08-26 08:19:48,951 - App.RunHistoricalTickBacktest - INFO - REALTIME_BACKTEST_TRACE action=handler_execute_start symbol='BTCUSDT' interval='5m' tick_resolution='1s' strategy='ema_trend_confirm_pullback' start=... end=...
2026-08-26 08:19:57,736 - App.RunHistoricalTickBacktest - INFO - REALTIME_BACKTEST_TRACE action=handler_ticks_loaded count=604800
2026-08-26 08:19:57,736 - App.PaperExchange - INFO - [paper-exchange] Initialized for BTCUSDT | ...
2026-08-26 08:20:05,306 - App - WARNING - 🚨 UI FREEZE DETECTED: Qt Main Thread unresponsive for 5.1s (Threshold: 5.0s).
Current Main Thread Stack Trace:
  File ".../src/presentation/ui/main_window.py", line 171, in <module>
    main()
  File ".../src/presentation/ui/app_bootstrapper.py", line 233, in main
    exit_code = runtime.app.exec()

2026-08-26 08:20:05,648 - App.RunHistoricalTickBacktest - INFO - REALTIME_BACKTEST_TRACE action=handler_simulation_complete ticks=604800 bars_committed=2017
2026-08-26 08:20:05,703 - App - INFO - UI Thread recovered from freeze. Event loop responsive.
```

```text
2026-08-26 08:21:05,559 - App.RunHistoricalTickBacktest - INFO - REALTIME_BACKTEST_TRACE action=handler_execute_start symbol='BTCUSDT' interval='1h' tick_resolution='1s' strategy='ema_trend_confirm_pullback' start=2026-07-27... end=2026-08-26...
2026-08-26 08:22:37,745 - App - WARNING - 🚨 UI FREEZE DETECTED: Qt Main Thread unresponsive for 69.1s (Threshold: 5.0s).
Current Main Thread Stack Trace:
  File ".../src/presentation/ui/main_window.py", line 171, in <module>
    main()
  File ".../src/presentation/ui/app_bootstrapper.py", line 233, in main
    exit_code = runtime.app.exec()
  File ".../.venv/lib/python3.14/site-packages/pyqtgraph/graphicsItems/TextItem.py", line 177, in boundingRect
    return self.textItem.mapRectToParent(self.textItem.boundingRect())

2026-08-26 08:22:38,130 - App - INFO - UI Thread recovered from freeze. Event loop responsive.
2026-08-26 08:23:31,488 - App - WARNING - 🚨 UI FREEZE DETECTED: Qt Main Thread unresponsive for 13.8s (Threshold: 5.0s).
Current Main Thread Stack Trace:
  File ".../src/presentation/ui/main_window.py", line 171, in <module>
    main()
  File ".../src/presentation/ui/app_bootstrapper.py", line 233, in main
    exit_code = runtime.app.exec()

2026-08-26 08:23:31,478 - App - INFO - UI Thread recovered from freeze. Event loop responsive.
2026-08-26 08:23:40,407 - App.RunHistoricalTickBacktest - INFO - REALTIME_BACKTEST_TRACE action=handler_ticks_loaded count=2592000
2026-08-26 08:23:40,428 - App.PaperExchange - INFO - [paper-exchange] Initialized for BTCUSDT | ...
2026-08-26 08:24:04,808 - App - WARNING - 🚨 UI FREEZE DETECTED: Qt Main Thread unresponsive for 5.3s (Threshold: 5.0s).
...
2026-08-26 08:24:14,863 - App - WARNING - 🚨 UI FREEZE DETECTED: Qt Main Thread unresponsive for 5.5s (Threshold: 5.0s).
...
2026-08-26 08:24:28,517 - App.RunHistoricalTickBacktest - INFO - REALTIME_BACKTEST_TRACE action=handler_simulation_complete ticks=2592000 bars_committed=721
2026-08-26 08:24:28,707 - App - INFO - UI Thread recovered from freeze. Event loop responsive.
```

Log đầy đủ của phiên (từ boot `08:15:18` tới `08:24:29`) do người báo dán trong hội thoại
ngày 2026-08-26. **Cùng phiên đó** còn lộ ra một lỗi thứ hai, khác hẳn triệu chứng, đã tách
hồ sơ riêng: [`BUG-054`](BUG-054_process_does_not_exit_after_graceful_shutdown.md) — shutdown
chạy hết nhưng tiến trình không thoát.

## 2. Quan sát thô từ log (chưa phải root cause — **chưa điều tra**)

Chỉ ghi lại những gì đọc **trực tiếp** được trên log, không suy diễn cơ chế:

1. **Cả 5 lần đơ đều nằm trong cửa sổ thời gian của `RunHistoricalTickBacktestCommand`**
   (2 lần chạy: `5m`/604.800 tick và `1h`/2.592.000 tick).
2. Trong cùng phiên, **4 lần `RunStaticBacktestCommand`** (`08:15:33` 48.131 nến,
   `08:16:53`, `08:17:02`, `08:17:15`, `08:18:49`) **không** làm watchdog bắn lần nào.
3. **4/5 stack trace dừng ngay ở `runtime.app.exec()`** — tức bản dump không nêu được
   frame nào nằm dưới event loop, nên tự nó **không chỉ ra** ai đang chặn. Chỉ lần 69.1s có
   thêm 1 frame `pyqtgraph/graphicsItems/TextItem.py:177 boundingRect`.
4. **Bất thường về thứ tự log:** lần đơ #3 có dòng `UI FREEZE DETECTED` ghi
   `08:23:31,488` nhưng dòng `UI Thread recovered` lại ghi `08:23:31,478` — **sớm hơn 10ms**
   so với chính cảnh báo mà nó phục hồi. Có thể là vấn đề riêng của cơ chế watchdog/logging
   (thứ tự emit hoặc timestamp), tách khỏi bug đơ UI.
5. Khoảng `08:22:37` → `08:23:40` (giữa `handler_execute_start` và `handler_ticks_loaded`
   của lần `1h`) là giai đoạn **nạp 2.592.000 tick**, kéo dài ~2 phút 35 giây, và chứa 2
   trong 5 lần đơ.

## 3. Kỳ vọng (Expected)

UI vẫn phản hồi (di chuột, đổi tab, bấm huỷ) trong suốt lúc Historical Tick Backtest chạy —
công việc nặng phải nằm ngoài Qt main thread; watchdog không được bắn.

## 4. Suggested next steps

*(Chưa thực hiện — người báo yêu cầu chỉ tạo hồ sơ, không điều tra.)*

1. Trước hết sửa chỗ khiến chính bằng chứng vô dụng: **stack dump của watchdog dừng ở
   `app.exec()`**, không có frame nào bên dưới, nên 4/5 lần đơ không truy được. Xác định
   watchdog đang chụp stack bằng cách nào và vì sao chỉ thấy 2–3 frame.
2. Tái hiện với `--debug` trên đúng đường `RunHistoricalTickBacktestCommand` ở range lớn
   (`1h` / tick `1s` / 30 ngày ≈ 2.59M tick) rồi đọc file log (không đọc console — theo
   `CLAUDE.md` §2).
3. Cần tách bạch **3 pha** trong lần chạy, vì log cho thấy đơ ở cả 3: nạp tick
   (`execute_start` → `ticks_loaded`), mô phỏng (`ticks_loaded` → `simulation_complete`), và
   vẽ lại chart (`ChartCard [chart-data]` ngay sau đó).
4. Đối chiếu với 2 hồ sơ đã đóng cùng khu vực trước khi kết luận trùng lặp hay không —
   **chưa xác minh, chỉ ghi để lượt sau kiểm tra**:
   [`BUG-033`](../completed/BUG-033_realtime_backtest_progress_flood_freezes_ui_thread.md)
   (progress signal flood cùng màn hình Realtime Backtest, đóng 2026-08-23) và
   [`BUG-042`](../completed/BUG-042_paper_exchange_log_flood_freezes_ui_thread.md)
   (log flood của `PaperExchange`, đóng 2026-08-24).
5. Ghi nhận riêng quan sát #4 mục 2 (timestamp `recovered` sớm hơn `DETECTED`) — nếu xác
   nhận là lỗi độc lập thì tách hồ sơ riêng, đừng gộp vào đây.
6. Chỉ viết regression test **sau khi** biết pha nào chặn main thread — hiện chưa đủ dữ
   kiện để test đúng chỗ.
