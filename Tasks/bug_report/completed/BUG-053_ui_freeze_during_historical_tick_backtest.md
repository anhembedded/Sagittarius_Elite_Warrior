# BUG-053 — UI đơ nhiều lần (5.1s → 69.1s) trong lúc chạy Historical Tick Backtest

**Reported date:** 2026-08-26
**Severity:** 🔴 **P1** — UI đơ tới 69 giây, người dùng không thao tác được gì
**Status:** ✅ **Fixed 2026-08-26** — root-caused (đo được, không phải suy luận),
tái hiện bằng probe, regression test đỏ-đúng-lý-do trước fix, xanh sau, và đo lại
bằng **bằng chứng dương tính** (đỉnh trễ heartbeat 4,02s → 0,18s).

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

## 4. Root cause

**Cơ chế: heap vài triệu object → mỗi lần GC gen-2 mất vài giây → GC giữ GIL →
Qt main thread không chạy nổi cả slot heartbeat của chính nó.**

`RunHistoricalTickBacktestCommandHandler.execute()` nạp **toàn bộ** range tick
bằng một lời gọi duy nhất:

```python
ticks = self._repository.get_klines(...)   # src/.../run_historical_tick_backtest/handler.py
self._log_trace("handler_ticks_loaded", count=len(ticks))
```

`SQLAlchemyMarketDataRepository.get_klines()` chạy `query.all()` rồi
list-comprehension sang `MarketData`, nên ở đỉnh điểm **mỗi tick tồn tại 2 lần**:
một `KlineModel` (ORM) và một `MarketData` (dataclass, kèm 2 `datetime`). Với
2.592.000 tick là hàng chục triệu object sống cùng lúc. Chi phí một lần quét
gen-2 của CPython tỉ lệ với **tổng số object đang được GC theo dõi**, và
**GC chạy trong khi giữ GIL** — nên suốt lần quét đó main thread không thực thi
được một bytecode Python nào.

Điều này giải thích trọn vẹn cả 4 quan sát ở §2:

| Quan sát §2 | Giải thích |
| :--- | :--- |
| #1 chỉ đơ trong `RunHistoricalTickBacktestCommand` | Chỉ đường tick mới nạp cả range; đây là handler duy nhất còn gọi `get_klines()` cho dữ liệu lớn |
| #2 Static backtest **không** đơ dù 48.131 nến | Đường Static đã chuyển sang `count_klines()`/`stream_klines()` từ [`BUG-025`](../completed/BUG-025_unbuffered_full_materialization_sync_and_backtest_data_paths.md) — heap không phình |
| #3 4/5 stack dump dừng ở `app.exec()` | **Bản dump không hỏng — nó đúng.** `UIWatchdog._handle_freeze()` gọi `traceback.format_stack()` trên frame Python của main thread; main thread lúc đó nằm trong C++ của Qt và đang **chờ GIL**, nên nó thật sự *không có* frame Python nào sâu hơn. "Stack rỗng" chính là bằng chứng: main thread không bị kẹt trong code của app, nó bị bỏ đói GIL |
| Thời lượng đơ tăng theo số tick (5,1s ở 604.800 → 69,1s ở 2.592.000) | Heap càng lớn, mỗi lần quét gen-2 càng lâu |

### Bằng chứng đo được (không phải suy luận)

Probe dựng đúng hình dạng production — Qt event loop trên main thread với một
`QTimer` 100ms đóng vai heartbeat, handler thật chạy trên thread nền, DB SQLite
thật 2.592.000 tick 1s:

| Cấu hình | Đỉnh trễ heartbeat | Số lần trễ >1s | Wall |
| :--- | :---: | :---: | :---: |
| **A. Trước fix, GC bật** | **4,02s** | 6 | 159,2s |
| **B. Trước fix, `gc.disable()` trên thread nền** | 0,80s | 0 | 131,2s |
| **C. Sau fix, GC bật** | **0,18s** | 0 | 106,3s |

Chuỗi các lần trễ ở cấu hình A tăng **đơn điệu** đúng như một heap đang phình:

```
gap 1.08s at t+42.7s
gap 1.43s at t+47.9s
gap 1.80s at t+55.2s
gap 2.16s at t+63.8s
gap 2.68s at t+75.4s
gap 4.02s at t+90.9s
```

A → B là phép thử quyết định: **chỉ tắt GC**, không đụng gì khác, mọi lần trễ
nhiều giây biến mất. Đó là bằng chứng trực tiếp rằng thủ phạm là pha GC, không
phải "thread nền ăn CPU".

Con số ở máy này thấp hơn máy người báo (4,02s so với 69,1s) vì probe chạy
`QCoreApplication` offscreen, không gánh cả cây widget + wayland + DPR 2 như
app thật; cơ chế thì giống hệt, chỉ khác hệ số.

## 5. Fix

Chuyển đường tick sang **đúng contract mà `BUG-025` đã dựng cho đường Static** —
`count_klines()` để biết tổng, `stream_klines()` để tiêu thụ:

- `handler.execute()`: `get_klines()` → `count_klines()` + `stream_klines()`.
  `handler_ticks_loaded` giờ lấy số từ `count_klines()` (giữ nguyên tên action
  để log lịch sử vẫn so sánh được, y như `handler_klines_loaded` của Static).
- `handler._simulate()`: nhận `Iterator[MarketData]` + `total_ticks: int` thay
  cho `list`. `len(ticks)` → tham số; `ticks[-1]` → biến `last_tick` cập nhật
  trong vòng lặp (iterator không index ngược được, và đọc lại range chỉ để lấy
  tick cuối thì tái lập đúng cái vừa bỏ).

Không đụng logic mô phỏng: thứ tự tick, ranh giới bar, `_commit_bar`, throttle
tiến độ đều giữ nguyên — 10/10 test hành vi sẵn có của handler vẫn xanh.

**Tại sao đủ:** không còn lúc nào cả range cùng sống, nên heap không bao giờ
phình tới ngưỡng làm một lần quét gen-2 kéo dài nhiều giây. Đo lại ở cấu hình C
với GC **vẫn bật**: đỉnh trễ 0,18s — tốt hơn cả lúc tắt GC ở B, và wall giảm
159,2s → 106,3s (−33%).

## 6. Regression test

`tests/unit/application/use_cases/test_run_historical_tick_backtest.py`

- `test_ticks_are_streamed_never_all_held_alive_at_once` — dùng `weakref.WeakSet`
  đếm **số tick object sống cùng lúc** ở giữa lúc handler đang chạy, chặn trần 16
  trên 600 tick. Đây là bất biến gây ra bug, không phải "đã gọi hàm nào".
- `_configure_repo_with_ticks()` (helper dùng chung cho cả file) gắn
  `repo.get_klines.side_effect = AssertionError(...)`, nên đường materialize cũ
  **không thể** đi qua file test này nữa.

Đỏ trước fix, đúng lý do:

```
AssertionError: BUG-053: the historical-tick path must stream via count_klines()/
stream_klines(); materializing the whole range with get_klines() is what starved
the Qt main thread.
```

Xanh sau fix: 10 passed.

`tests/integration/application/test_backtest_with_broker_simulation.py` cũng
được cập nhật mock sang `count_klines()`/`stream_klines()` — theo interface, không
nới lỏng assertion nào.

## 7. Việc còn mở, tách khỏi bug này

- Quan sát §2 #4 (dòng `recovered` ghi timestamp sớm hơn 10ms so với chính dòng
  `DETECTED` nó phục hồi) **chưa điều tra**. Nằm trong `UIWatchdog` của
  `sagittarius_engine`, không phải repo này; không ảnh hưởng tới fix ở trên. Nếu
  xác nhận là lỗi thật thì mở hồ sơ riêng ở repo engine.
- `UIWatchdog._handle_freeze()` chỉ dump stack Python của main thread. Như §4
  giải thích, với lớp bug bỏ-đói-GIL thì dump đó **đúng nhưng vô dụng cho việc
  quy trách nhiệm** — muốn lần sau chỉ thẳng được thủ phạm thì watchdog cần dump
  **mọi** thread (`sys._current_frames()` đã có sẵn tất cả). Cũng là việc của repo
  engine.
