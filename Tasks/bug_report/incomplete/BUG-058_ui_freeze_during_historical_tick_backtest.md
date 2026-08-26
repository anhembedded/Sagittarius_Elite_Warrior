# BUG-058 — UI đơ nhiều lần (5.1s → 69.1s) trong lúc chạy Historical Tick Backtest

**Reported date:** 2026-08-26
**Severity:** 🟠 P1 (freeze #2, root-caused và sửa) — 2 freeze còn lại (#4/#5, sau
`ticks_loaded`) **chưa root-caused**.
**Status:** 🟡 **Đã sửa MỘT PHẦN, 2026-08-26** — freeze #1/#2/#3 (giai đoạn nạp tick,
gồm cả outlier 69,1s nặng nhất) đã root-caused, sửa, đo lại bằng bằng chứng thật (§5).
Freeze #4/#5 (giai đoạn mô phỏng, sau `ticks_loaded`) **vẫn Open** — chưa có cơ chế
được xác nhận cho 2 lần đó, xem §6.

---

> **Đổi số 2026-08-26:** hồ sơ này trước mang mã `BUG-051`, trùng với một bug khác đã đóng (`Tasks/bug_report/completed/BUG-051_*.md`) — Bug Board quy định mã phải là số kế tiếp số lớn nhất **ở cả hai thư mục**, và quy định đó đã bị vi phạm. Hồ sơ đang mở đổi thành `BUG-058` (hồ sơ đã đóng giữ mã cũ vì ROADMAP và các commit đã merge tham chiếu). Mọi commit/PR trước ngày này nhắc `BUG-051` **trong ngữ cảnh bug này** là chỉ chính hồ sơ đây.


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
hồ sơ riêng: [`BUG-059`](BUG-059_process_does_not_exit_after_graceful_shutdown.md) — shutdown
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

## 5. Điều tra 2026-08-26 — freeze #1/#2/#3 (giai đoạn nạp tick): root-caused, sửa,
đo lại bằng bằng chứng thật

Đúng bước 2/3 ở §4: tái hiện được **cơ chế**, không phải qua GUI thật (không có màn hình
thật/Binance thật trong môi trường phiên này) mà bằng cách đo trực tiếp đúng lệnh gọi
`IMarketDataRepository` mà `RunHistoricalTickBacktestCommandHandler` dùng, dưới một
`QApplication` thật (`QT_QPA_PLATFORM=offscreen`) với một `QTimer` heartbeat 50ms trên main
thread — cùng cơ chế đo mà `UIWatchdog` thật dùng (`sagittarius_engine`'s
`extensions/pyside_mvc/safety/ui_watchdog.py`), chỉ mịn hơn (50ms so với 1000ms) để bắt được
cả những khoảng ngắn hơn ngưỡng cảnh báo 5s.

### Root cause

`RunHistoricalTickBacktestCommandHandler.execute()` (handler.py) gọi
`self._repository.get_klines(...)` — **một lệnh gọi đồng bộ duy nhất** vật chất hoá **toàn bộ**
dải tick (tới hàng triệu dòng với range rộng/`tick_resolution` mịn) thành 1 list Python trước
khi vòng lặp mô phỏng kịp bắt đầu. Đây **chính xác** là bug `BUG-025` đã tìm ra và sửa cho
`RunStaticBacktestCommandHandler` ("Đường dữ liệu ... Backtest (DB→RAM) không streaming") —
nhưng `RunHistoricalTickBacktestCommandHandler` (BOT-076, engine tick-driven, tách biệt vĩnh
viễn khỏi Static theo chính docstring của nó) **chưa bao giờ được áp cùng fix**, vẫn dùng
`get_klines()` thay vì `count_klines()`+`stream_klines()`.

Khớp đúng quan sát #5 ở §2 trên: freeze nặng nhất (69,1s) và freeze #3 (13,8s) đều nằm **trong**
cửa sổ `handler_execute_start` → `handler_ticks_loaded` — tức đúng lúc `get_klines()` đang chạy.
Freeze #1 (5,1s) nằm ngay **sau** `handler_ticks_loaded` của lần chạy `5m` — thời điểm log dòng
đó không đồng nghĩa công việc materialize đã hoàn toàn xong (GC/finalization của list vừa dựng
có thể còn đang chạy khi log dòng tiếp theo được ghi).

### Bằng chứng đo được (đo thật, không suy diễn)

DB SQLite thật (`DatabaseManager`/`SQLAlchemyMarketDataRepository`, cùng lớp production), nạp
1.500.000 kline tổng hợp cho `BTCUSDT`/`1s`, đo trên background thread trong khi main thread
chạy `app.exec()` thật với heartbeat 50ms:

| Đường dữ liệu | Thời gian tải | Heartbeat gap lớn nhất | Số gap >1s | Số gap >0.5s |
| :--- | :---: | :---: | :---: | :---: |
| `get_klines()` (`query.all()`, cũ) | **69,9s** | **1,879s** | 4 | 9 |
| `count_klines()`+`stream_klines()` (`yield_per(1000)`, mới) | **27,98s** | **0,088s** | 0 | 0 |

Streaming vừa **nhanh hơn 2,5×** vừa **không còn gap heartbeat nào vượt 0,1s** (so với
heartbeat khoẻ mạnh ~0,05-0,09s) — trong khi `get_klines()` cũ tạo ra 4 gap thật sự vượt 1
giây, kể cả khi hàm này **đã chạy trên background thread** (`ThreadManager`, xem
`backtest_presenter.py::_run_backtest`'s docstring "submitted to IThreadManager") — chạy nền
không tự bảo vệ main thread khỏi một cú vật chất hoá Python khổng lồ duy nhất.

*(Lưu ý loại trừ đã thử trước khi tìm ra cơ chế này: một vòng lặp Python thuần 3 triệu lần lặp
với alloc/arithmetic tương tự, không chạm DB, **không** gây gap nào trên cùng stack — nên đây
không phải hiện tượng GIL-starvation chung chung từ CPU work, mà đặc thù của việc vật chất hoá
hàng triệu ORM row/dataclass trong 1 lệnh gọi.)*

### Fix

`RunHistoricalTickBacktestCommandHandler` đổi sang đúng pattern `BUG-025` đã dùng cho
`RunStaticBacktestCommandHandler`: `count_klines()` lấy tổng số tick trước (không vật chất hoá
gì), rồi `_simulate()` tiêu thụ `stream_klines()` (generator, `yield_per(1000)`) thay vì
`list[MarketData]`. `last_tick` được theo dõi tăng dần trong vòng lặp (thay `ticks[-1]`) —
cùng bất biến `BUG-025` đã đặt ra cho phía Static (`RuntimeError` nếu stream rỗng dù
`count_klines()` báo có dữ liệu, thay vì crash `None` bên trong `force_close()`).

### Regression test

`tests/unit/application/use_cases/test_run_historical_tick_backtest.py::test_handler_never_calls_get_klines`
— khẳng định trực tiếp `repository.get_klines` **không bao giờ** được gọi, còn
`count_klines`/`stream_klines` **có** được gọi. Xác nhận đỏ đúng lý do trước khi sửa
(`TypeError: object of type 'Mock' has no len()` — đúng chỗ code cũ gọi `len(ticks)` trên kết
quả `get_klines()` chưa được mock cấu hình), xanh sau khi sửa. Toàn bộ 12 test hiện có của
handler này + `test_backtest_with_broker_simulation.py` (đường tick-driven) đều pass không đổi
assertion nào, chỉ đổi cách mock repository (từ `get_klines.return_value` sang
`count_klines`/`stream_klines` `.side_effect`, đúng convention `BUG-025` đã thiết lập cho phía
Static test).

## 6. Freeze #4/#5 (giai đoạn mô phỏng, sau `ticks_loaded`) — vẫn Open

Fix ở §5 chỉ chạm giai đoạn **nạp** tick. Freeze #4 (5,3s, `08:24:04`) và #5 (5,5s, `08:24:14`)
xảy ra **sau** `handler_ticks_loaded` (`08:23:40`) — tức trong lúc `_simulate()` đang chạy vòng
lặp per-tick thật (`engine.on_forming_bar_tick`/`on_tick`, 2.592.000 lần). Việc chuyển sang
stream **có thể** giúp một phần (không còn giữ nguyên list 2,59 triệu tick trong RAM suốt lúc mô
phỏng, chỉ còn chunk 1000 dòng tại một thời điểm) — **đã đo thêm sau fix ở §5, kết quả: giúp
một phần, không hết hẳn.**

Đo lại `_simulate()` thật (qua `handler.execute()`) với 1.500.000 tick tổng hợp, chiến lược thật
`EmaCrossoverStrategy` (không phải đúng `ema_trend_confirm_pullback` — chiến lược đó cần params/
setup phức tạp hơn không dựng lại được trong phiên này), cùng cách đo heartbeat 50ms như §5:

| Pha | Thời gian | Gap lớn nhất | Gap >1s | Gap >0.5s |
| :--- | :---: | :---: | :---: | :---: |
| Mô phỏng (`_simulate()`, sau fix streaming) | 70,5s | **0,718s** | 0 | 2 |

So với pha nạp tick cũ (`get_klines()`, §5): **0 gap >1s** (so với 4 trước fix) — nhẹ hơn hẳn,
đúng như dự đoán streaming giúp một phần (không còn giữ 1 list 2,59 triệu tick cố định trong RAM
suốt lúc mô phỏng). Nhưng **vẫn còn 2 gap >0,5s**, tức pha mô phỏng tự nó có áp lực GIL/alloc
thật, dù chưa từng chạm ngưỡng watchdog 5s trong phép đo này (0,72s cao nhất, xa dưới ngưỡng).
**Không giải thích được** mức 5,3s/5,5s freeze #4/#5 báo cáo gốc — chênh lệch quá lớn (0,72s đo
được vs 5,3s+ báo cáo) để coi là cùng hiện tượng đã đo trúng, dù cùng cơ chế loại (GIL/alloc
pressure từ vòng lặp per-tick). Khả năng freeze #4/#5 thật nặng hơn vì: (a) `ema_trend_confirm_pullback`
nặng hơn `EmaCrossoverStrategy` tổng hợp ở đây, (b) có UI thật (chart repaint, DevBoard panel)
cạnh tranh GIL mà phép đo headless này không có, hoặc (c) một cơ chế khác hẳn (chart re-render
sau `simulation_complete`) như nghi vấn cũ. Việc còn thiếu, không đổi: tái hiện `--debug` trên
app thật ở đúng range/chiến lược đó, đọc log quanh mốc `08:24:04`-`08:24:28`.
