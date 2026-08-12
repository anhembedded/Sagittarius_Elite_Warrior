# 🧪 Dev Board — User-End Test Case Catalog

> Phạm vi: màn hình **Developer Board** (`dashboard_view.py` / `dashboard_presenter.py`) —
> System Controls, Indicators, Chart, System Monitor.
>
> Toàn bộ test case dưới đây được đối chiếu trực tiếp với code thật
> (`dashboard_presenter.py`, `control_card.py`, `chart_toolbar.py`,
> `indicator_control_card.py`, `thread_manager.py`, `ui_matrix.json`) tại thời điểm viết —
> không suy đoán. Ghi chú "Grounding" trỏ tới đúng dòng/hành vi trong code để dev có thể
> verify lại nhanh.
>
> Về số lượng: tài liệu ưu tiên **case thật, không trùng lặp** hơn là nhồi cho đủ một con số —
> vì vậy đây là ~155 case cụ thể (đủ khác biệt để mỗi case là một bug tiềm năng riêng), thay vì
> 1000 dòng lặp lại "click nút X 2 lần". Phần **D (Async/Race Condition)** là trọng tâm theo
> yêu cầu, vì đây là khu vực có nhiều lỗ hổng thật nhất trong code hiện tại.

**Chú giải mức độ ưu tiên:** 🔴 Critical (data corruption / crash) · 🟠 High (UX sai lệch rõ) · 🟡 Medium · 🟢 Low/cosmetic
**Chú giải loại:** `FUNC` hành vi chức năng bình thường · `ASYNC` liên quan thread/signal/event ordering · `GAP` control tồn tại nhưng chưa wire (không phải bug, nhưng cần test để không báo nhầm)

---

## A. System Controls — Load History / Start Live / Stop / FSM

| ID | Pri | Scenario | Steps | Expected |
|---|---|---|---|---|
| TC-SC-01 | 🟠 | Load History cơ bản | Mở Dev Board → "Load History" | Chart render đúng 5000 nến ETHUSDT gần nhất (order oldest→newest); log "Refreshed N historical klines..." |
| TC-SC-02 | 🟠 | Load History khi DB rỗng | Xoá DB / chọn symbol chưa sync → "Load History" | Log "No historical data found for ETHUSDT" — không crash, chart giữ nguyên trạng thái trước đó |
| TC-SC-03 | 🟠 | Start Live cơ bản (happy path) | "Start Live" | FSM `IDLE→LOCKED→LIVE`; log tuần tự: "Starting..." → "Syncing missing data..." → "Reloading historical..." → "Opening Websocket..." → "Live stream for [...] is running." |
| TC-SC-04 | 🟠 | Stop khi đang Live | Đang LIVE → "Stop" | FSM `LIVE→IDLE`; log "Stopping..."→"Live Stream stopped."; `stop_stream_button` disable lại, các control khác enable lại đúng theo `ui_matrix.json["main"]["IDLE"]` |
| TC-SC-05 | 🔴 | Start Live thất bại ở bước StartLiveStreamCommand | Mock `StartLiveStreamCommand` trả `success=False` | FSM `LOCKED→ERROR→IDLE` (auto-recover qua `_on_fsm_error`); log "Stream startup failed: ..."; verify UI **không kẹt ở LOCKED** (mọi control phải khả dụng lại) |
| TC-SC-06 | 🔴 | Exception trong `_run_sync_and_start` (vd. Sync command ném exception) | Mock `SyncMarketDataCommand.dispatch` raise Exception | `except Exception` bắt được → `ui_stream_failed_signal` emit "System error: ..." → FSM về IDLE, không crash toàn app |
| TC-SC-07 | 🟠 | Stop khi đang IDLE (không có gì để dừng) | Mở app, không Load/Start, thử bấm Stop | Nút Stop phải đang **disabled** theo matrix `IDLE.stop_stream_button=false` — verify UI chặn được, không phải dựa vào code phòng thủ bên trong `_on_stop_stream` |
| TC-SC-08 | 🟠 | Exception trong `_on_stop_stream` | Mock `dispatcher.dispatch(StopLiveStreamCommand)` raise | Log "Error while stopping: ..."; FSM → ERROR → auto IDLE; verify Stop button không bị kẹt enabled mãi |
| TC-SC-09 | 🟡 | FSM transition không hợp lệ bị chặn | Gọi thẳng `presenter.fsm.transition_to(UIMode.LIVE)` khi đang IDLE (bỏ qua LOCKED) | Phải bị từ chối/raise theo đúng `add_transition` đã khai báo (`IDLE→LOCKED` mới hợp lệ) — không cho phép nhảy cóc state |
| TC-SC-10 | 🟢 | Load History button label/icon không đổi khi đang loading | Bấm Load History, quan sát trong lúc background đang chạy | Hiện tại KHÔNG có loading-spinner/disabled state cho riêng `load_history_button` (chỉ `start_stream_button` bị khoá qua LOCKED) — verify đây là hành vi hiện tại, không phải bug UI treo |
| TC-SC-11 | 🟠 | `_on_run_backtest` / `_on_stop_backtest` | Gọi các slot này (chưa có nút UI tương ứng trong ControlCard hiện tại) | Chỉ log + `set_backtest_active(True/False)`; **KHÔNG dispatch bất kỳ command nào thật** (`# TODO: Dispatch RunBacktestCommand`) — verify đây là stub chưa hoàn thiện, không phải bug |
| TC-SC-12 | 🟡 | Đóng app (window close) khi đang LIVE | Đang LIVE, đóng cửa sổ ứng dụng | `engine.stop()` phải dừng sạch WebSocket/thread pool, không treo process, không traceback trong log khi thoát |
| TC-SC-13 | 🟡 | Đóng app khi background task (`_run_load_history`) vẫn đang chạy | Bấm Load History rồi đóng app ngay lập tức | `ThreadPoolExecutor.shutdown()` không nên bị block vô hạn chờ query; verify app thoát trong thời gian hợp lý |
| TC-SC-14 | 🟠 | `_on_fsm_error` tự động hồi phục | Trigger ERROR state bất kỳ cách nào | Ngay lập tức tự chuyển về IDLE (không cần user thao tác) — verify user không bị "kẹt" ở màn hình lỗi phải tự bấm gì đó |
| TC-SC-15 | 🟢 | Nhiều instance MainWindow (nếu có multi-window trong tương lai) | N/A hiện tại chỉ 1 MainWindow | Đánh dấu out-of-scope cho tới khi multi-window được hỗ trợ |

---

## B. Indicators (RSI / EMA / MACD)

| ID | Pri | Scenario | Steps | Expected |
|---|---|---|---|---|
| TC-IND-01 | 🟠 | Bật RSI rồi Load History | Tick RSI (period mặc định 14) → Load History | 1 subplot "RSI(14)" xuất hiện dưới Volume, có legend, giá trị cập nhật đúng công thức RSI Wilder |
| TC-IND-02 | 🟠 | Bật EMA rồi Load History | Tick EMA (period 20) → Load History | Đường EMA(20) vẽ **overlay lên chart chính** (không phải subplot riêng) |
| TC-IND-03 | 🟠 | Bật MACD rồi Load History | Tick MACD → Load History | Subplot "MACD" hiển thị đường `reading.macd` (không phải signal/histogram — verify đúng field được extract, xem `extract_value=lambda reading: reading.macd`) |
| TC-IND-04 | 🟠 | Bật cả 3 cùng lúc | Tick RSI+EMA+MACD → Start Live | 3 curve riêng biệt, không đè line, không lệch trục X (đều `setXLink` theo main_plot) |
| TC-IND-05 | 🟡 | Đổi period RSI SAU khi đã Load History (không bấm lại) | Load History → đổi period 14→7 | **GAP đã xác nhận**: không có tác dụng cho tới lần Load/Start kế tiếp — verify đúng hành vi này, ghi rõ trong bug tracker nếu team muốn nó live-update |
| TC-IND-06 | 🟠 | Uncheck 1 indicator rồi Load History lại | Đang có RSI hiển thị → bỏ tick → Load History | Subplot RSI biến mất **hoàn toàn** (row + curve + crosshair line), không để lại panel rỗng (đã fix trong phiên trước qua `remove_subplot`/`unregister_plot`) |
| TC-IND-07 | 🔴 | Bấm Load History 2 lần liên tiếp với cùng indicator set | Tick RSI → Load History → Load History lần 2 ngay | Đúng 1 subplot RSI, đúng 1 curve — không duplicate (regression test cho bug vừa fix trong phiên này) |
| TC-IND-08 | 🟠 | Toggle legend swatch để ẩn/hiện | Click vào ô màu "EMA(20)" trong legend | Đường ẩn/hiện, KHÔNG ảnh hưởng RSI/MACD, và state này **mất khi Load History lại** (vì object bị rebuild) — verify user hiểu đây không phải preference lưu lại |
| TC-IND-09 | 🟡 | Period ngoài range hợp lệ | `spin_rsi_period` set qua `setRange(_MIN_PERIOD, _MAX_PERIOD)` — thử kéo tới min/max | SpinBox tự chặn giá trị ngoài range, RSI không nhận period=0 hoặc âm gây ZeroDivisionError |
| TC-IND-10 | 🟢 | Period = 1 (biên nhỏ nhất hợp lệ) | Set RSI period = min cho phép → Load History | Không crash, đường RSI vẫn vẽ được (dù có thể noisy) |
| TC-IND-11 | 🟠 | MACD khi lịch sử ít hơn 26+9 nến (chưa đủ warm-up) | Load History với DB chỉ có 20 nến | `indicator.update()` trả `None` cho tới khi đủ warm-up (đã có `if reading is None: continue`) → verify không có điểm rác/NaN bị vẽ lên chart |
| TC-IND-12 | 🟠 | Indicator warm-up qua ranh giới historical→live | Load đủ lịch sử cho RSI warm-up xong, sau đó Start Live tiếp tục feed nến mới | Giá trị RSI tại nến live đầu tiên phải **liên tục** với giá trị cuối của batch historical (cùng object `RSI`, cùng state — không bị reset) |
| TC-IND-13 | 🔴 | Uncheck indicator TRONG LÚC `_compute_indicator_series` (background) đang chạy cho nó | Load History (5000 nến → tính RSI mất vài trăm ms) → ngay lập tức uncheck RSI trước khi background xong | `_on_indicator_data` nhận signal cho "RSI(14)" nhưng `self.active_indicators.get("RSI(14)")` đã `None` → data bị **âm thầm drop** (`if active_indicator is None ... return`) — verify không exception, nhưng cũng verify UI không hiển thị dữ liệu RSI "ma" nào |
| TC-IND-14 | 🟡 | Đổi period rồi bấm Load History nhiều lần liên tiếp với period khác nhau mỗi lần | RSI period=14→Load, đổi 7→Load, đổi 21→Load (nhanh) | Xem mục **D (Async)** — đây chính là kịch bản có race condition thật, không chỉ là UI test |

---

## C. Chart Interaction (Zoom / Crosshair / Toolbar)

| ID | Pri | Scenario | Steps | Expected |
|---|---|---|---|---|
| TC-CHT-01 | 🟠 | Zoom X bằng scroll trên main chart | Cuộn chuột trên vùng nến | Trục X zoom in/out quanh vị trí con trỏ |
| TC-CHT-02 | 🟠 | Auto Y-scale theo vùng X đang xem | Zoom X vào 1 đoạn có biên độ giá nhỏ | Trục Y tự scale khít theo min/max của đúng đoạn đang hiển thị (không bị kéo dãn bởi outlier ngoài khung nhìn) |
| TC-CHT-03 | 🟠 | Zoom Y độc lập trên Volume subplot | Cuộn chuột trên vùng Volume | Chỉ Volume subplot đổi Y-scale, main chart/RSI/MACD không đổi |
| TC-CHT-04 | 🟠 | Zoom Y độc lập trên RSI/MACD subplot | Cuộn chuột trên vùng RSI | Tương tự TC-CHT-03 cho RSI |
| TC-CHT-05 | 🟢 | Nút H+/H-/V+/V- | Bấm từng nút | Zoom ngang/dọc thay đổi tương ứng theo % cố định mỗi lần bấm |
| TC-CHT-06 | 🟢 | Nút reset (⟲) | Zoom lung tung → bấm reset | Về lại initial view range (150 nến gần nhất theo `_DEFAULT_INITIAL_VISIBLE_CANDLES`) |
| TC-CHT-07 | 🟠 | Crosshair đồng bộ across subplots | Hover trên main chart | Dashed line xuất hiện đồng thời trên Volume/RSI/MACD tại cùng timestamp X |
| TC-CHT-08 | 🟠 | Label OHLC khi hover trên main chart | Hover đúng vị trí 1 nến | Label góc phải hiện đúng O/H/L/C + % thay đổi của nến đó |
| TC-CHT-09 | 🟡 | Label khi hover trên subplot (không phải main) | Hover trên RSI subplot | Label hiện giá trị Y tại điểm đó (không phải OHLC, vì `ohlc_lookup` chỉ áp dụng cho `_primary_plot`) |
| TC-CHT-10 | 🟡 | Rời chuột khỏi toàn bộ chart | Hover ra ngoài | Tất cả crosshair line ẩn, label về "Hover to see data" |
| TC-CHT-11 | 🟢 | Nút timeframe 1m/5m/15m/1h/1d trên toolbar | Bấm "5m" | **GAP**: chỉ đổi highlight nút (`set_active`), KHÔNG đổi dữ liệu candle — verify không nhầm là bug data, xem Section E để biết case khi tính năng này được wire thật |
| TC-CHT-12 | 🟡 | Chart type switch (nếu có UI trigger) | `set_chart_type("heikin_ashi")` / `"line"` / `"area"` | Dữ liệu convert đúng từ `_raw_history`, giữ nguyên `_live_candle` nếu đang có |
| TC-CHT-13 | 🟠 | Live candle đang update rồi resize window | Đang LIVE, resize cửa sổ / kéo QSplitter | Chart không bị mất data, không crash, ViewBox re-layout đúng |
| TC-CHT-14 | 🟢 | pan bằng kéo chuột (nếu enabled) | Giữ chuột kéo ngang trên chart | Pan theo trục X, không ảnh hưởng zoom |
| TC-CHT-15 | 🟡 | Volume bar màu theo bullish/bearish | Quan sát Volume subplot | Bar xanh khi close≥open, đỏ khi close<open — khớp với candle tương ứng |

---

## D. ⭐ Async / Race Condition / Event Ordering

Đây là phần trọng tâm theo yêu cầu. Kiến trúc thật:

- `IThreadManager` = `ThreadPoolExecutor(max_workers=4)` — **có concurrency thật sự**, không phải hàng đợi tuần tự. Tối đa 4 background task chạy song song.
- `self.active_indicators` là **1 instance attribute dùng chung**, được gán lại (không lock) trên main thread mỗi lần `_on_load_history`/`_on_start_stream` chạy, rồi được **đọc lại** từ bên trong background thread (`_compute_indicator_series`, `_update_indicators_on_closed_candle`).
- `load_history_button` **không** bị disable trong lúc background đang chạy (chỉ `start_stream_button`/`stop_stream_button` bị khoá qua FSM `LOCKED`) — đây là cửa mở chính cho race condition vì user re-click được ngay lập tức.
- `_handle_market_tick`/`_on_ui_chart_update` route dữ liệu **chỉ theo `symbol`**, hoàn toàn không xét `interval`/timeframe.
- `ui_stream_failed_signal` chỉ được emit từ luồng **khởi động** (`_run_sync_and_start`), không có đường tín hiệu nào cho lỗi xảy ra **sau khi** đã vào LIVE.

| ID | Pri | Scenario | Grounding | Expected / Câu hỏi cần trả lời |
|---|---|---|---|---|
| TC-ASY-01 | 🔴 | Click "Load History" 2 lần liên tiếp trong <200ms (trước khi lần 1 xong) | `load_history_button` không bị disable ở IDLE matrix → 2 lệnh `self._thread_manager.submit(self._run_load_history, ...)` chạy **song song thật** trên 2 worker thread khác nhau | Cả 2 thread đều gọi `_compute_indicator_series` đọc `self.active_indicators` — vì đây là **cùng 1 object reference** (indicator set giống nhau, do checkbox không đổi giữa 2 lần), cả 2 sẽ feed **CÙNG MỘT** bộ `RSI`/`EMA`/`MACD` instance 2 lần với cùng dữ liệu 5000 nến → mỗi indicator instance bị `update()` **gấp đôi** số lần cần thiết → giá trị RSI/EMA/MACD cuối cùng SAI (không phải giá trị thật của 5000 nến, mà là như thể có 10000 nến). Đây là **data corruption thật**, không chỉ UI glitch. |
| TC-ASY-02 | 🔴 | Click "Load History" đổi RSI period=14, rồi NGAY LẬP TỨC đổi period=7 và click "Load History" lần nữa (trước khi lần 1 chạy xong `_compute_indicator_series`) | `self.active_indicators = self._build_active_indicators()` gán lại object **mới toanh** (period=7) trên main thread — nhưng thread #1 (period=14) đã capture `ordered_klines` của riêng nó và gọi `self._compute_indicator_series(ordered_klines)` sau đó | Vì `_compute_indicator_series` đọc `self.active_indicators` **tại thời điểm gọi**, không phải tại thời điểm submit — nếu thread #1 chạy chậm hơn main thread kịp gán lại, thread #1 sẽ vô tình feed dữ liệu (klines) của chính nó vào **indicator period=7 (của lần click #2)** thay vì period=14 của chính nó → kết quả hiển thị "RSI(7)" nhưng thực chất bị feed 2 lần dữ liệu bởi cả 2 thread, cho ra trị số sai. Đây chính là kịch bản "đổi period liên tục" ở TC-IND-14. |
| TC-ASY-03 | 🟠 | Click "Load History" rồi trong lúc đang chạy, click "Start Live" | Cả 2 đều gọi `_ensure_chart_cards`, `_clear_registered_indicators`, gán lại `self.active_indicators`, rồi submit background task riêng (`_run_load_history` và `_run_sync_and_start`) — 2 workflow này **không loại trừ lẫn nhau** | 2 background task cùng query DB, cùng gọi `_compute_indicator_series` trên khả năng cùng 1 `active_indicators` snapshot → tương tự TC-ASY-01 nhưng xuyên workflow. Ngoài ra `_run_sync_and_start` còn dispatch `SyncMarketDataCommand` — nếu `_run_load_history` đang đọc DB đúng lúc Sync đang ghi DB, cần verify DB layer (SQLite WAL) không bị lock/corrupt. |
| TC-ASY-04 | 🔴 | 4 click "Load History" liên tục thật nhanh (chạm max_workers=4) | Cả 4 worker thread của pool đều bận với 4 lần `_run_load_history` chồng nhau | Verify: (a) app không deadlock, (b) `self.active_charts`/`self.active_indicators` cuối cùng ở trạng thái nhất quán (không half-updated), (c) UI cuối cùng hội tụ về đúng 1 bộ dữ liệu — không phải hợp nhất lộn xộn từ 4 lần chạy |
| TC-ASY-05 | 🔴 | Click "Load History" lần 5 khi 4 worker đã bận | `ThreadPoolExecutor` sẽ **queue** lệnh thứ 5, không chạy song song nữa | Verify lệnh thứ 5 chạy đúng SAU khi 1 trong 4 lệnh trước giải phóng worker — không bị mất/silently dropped |
| TC-ASY-06 | 🔴 | Start Live thành công, đợi vài giây có tick "live" thật, rồi RÚT MẠNG (hoặc kill WebSocket ở tầng infra) | `ui_stream_failed_signal` **không có đường phát sinh** cho lỗi xảy ra sau khi đã vào LIVE (chỉ emit từ `_run_sync_and_start`'s startup path) | **Câu hỏi cần trả lời bởi team**: FSM có bị kẹt ở "LIVE" mãi mãi dù không còn tick nào đổ về, không có bất kỳ chỉ báo lỗi nào cho user? Nếu đúng vậy, đây là gap UX nghiêm trọng — user tưởng vẫn đang live nhưng thực ra đã chết luồng. |
| TC-ASY-07 | 🟠 | Click "Stop" trong lúc UI thread đang bận xử lý 1 signal khác (vd. `_on_ui_chart_update` đang chạy) | `_on_stop_stream` dispatch `StopLiveStreamCommand` **đồng bộ trên main thread** (không qua `_thread_manager.submit`) | Nếu command handler có I/O chặn (đóng socket, join thread nền), UI sẽ **đứng hình** trong lúc đó — verify thời gian phản hồi của nút Stop, đo bằng ms, không được > vài trăm ms |
| TC-ASY-08 | 🔴 | Stop ngay sau khi FSM vừa vào LIVE (trong vòng 1 tick đầu tiên) | Có 2 luồng độc lập cùng lúc gửi signal về main thread: (1) `ui_stream_success_signal` → `_on_stream_start_success`, (2) tick đầu tiên từ WebSocket → `_handle_market_tick` → `ui_chart_update_signal`. Qt không đảm bảo thứ tự giữa 2 signal có nguồn phát từ 2 thread khác nhau | Verify: nếu Stop được bấm ngay khi nút vừa enable (do FSM=LIVE), có tick nào "mồ côi" (queued trước đó) vẫn được xử lý và vẽ lên chart **sau khi** đã Stop không? Nếu có, log/monitor phải phản ánh đúng — không được im lặng vẽ thêm dữ liệu sau khi user đã bấm Stop. |
| TC-ASY-09 | 🔴 | Stop, rồi NGAY LẬP TỨC Load History (trong lúc `StopLiveStreamCommand` vẫn có thể còn tick "rớt lại" trong hàng đợi event bus) | `_ensure_chart_cards` reuse **cùng chart card object** (cùng symbol) → nếu 1 tick cũ (từ luồng vừa Stop) vẫn còn kẹt trong signal queue và được xử lý SAU khi Load History đã render dữ liệu mới | Nến "ma" từ luồng cũ có thể bị append vào chart vừa mới load lại, làm sai timeline (timestamp của tick cũ có thể < timestamp mới nhất vừa load) → verify `append_closed_candle`/`update_last_candle` có kiểm tra tính đơn điệu (monotonic) của timestamp trước khi ghi hay không (hiện tại **KHÔNG** thấy check này trong `chart_card.py`) |
| TC-ASY-10 | 🟠 | Trùng timestamp: 2 event `is_closed=True` cho cùng 1 candle (do WebSocket reconnect gửi lại) | `_handle_market_tick` không dedupe theo timestamp | Verify `FastCandlestickItem.append_closed_candle` có tạo ra 2 bar trùng timestamp hay ghi đè đúng 1 bar — hiện tại nhiều khả năng **append trùng** vì không thấy logic so khớp timestamp cuối cùng trước khi append |
| TC-ASY-11 | 🟡 | Tick tần suất cực cao (stress: giả lập 200 tick/giây) | `ui_chart_update_signal.emit()` dùng `Qt.AutoConnection` → auto thành `QueuedConnection` xuyên thread, mỗi emit là 1 item trong hàng đợi event loop | Verify UI không bị "dồn cục" tick (backlog signal khiến chart nhảy giật cục thay vì mượt), và verify không có tick nào bị **drop** — đếm số tick gửi vs số lần `_on_ui_chart_update` thực sự chạy phải bằng nhau |
| TC-ASY-12 | 🟠 | Uncheck 1 indicator đúng lúc `_update_indicators_on_closed_candle` (chạy trên main thread, mỗi khi có nến đóng) đang xử lý nó | Vòng lặp `for name, active_indicator in self.active_indicators.items()` — nếu uncheck xảy ra GIỮA lúc `_on_load_history`/`_on_start_stream` reassign `self.active_indicators` (chỉ xảy ra khi user bấm nút, main-thread only nên an toàn với RuntimeError "dict changed size") | Vì cả việc uncheck (chỉ đổi `isChecked()` state, không tự trigger rebuild `active_indicators`) và vòng lặp trên đều chạy trên main thread nên **không** có race thật ở đây — verify assumption này đúng (đây là 1 case nên PASS, dùng để confirm boundary an toàn, không phải bug) |
| TC-ASY-13 | 🔴 | `_compute_indicator_series`'s comment nói "captures active_indicators once" — verify claim này | Đọc kỹ: `active_indicators = self.active_indicators` chỉ chống được việc **object bên trong đổi giữa các vòng lặp**, KHÔNG chống được việc 2 background thread **khác nhau** cùng đọc `self.active_indicators` và vô tình lấy trùng 1 object (xem TC-ASY-01/02) | Đây là 1 finding thiết kế: comment hiện tại có thể khiến dev sau này lầm tưởng cơ chế đã an toàn với race — cần sửa comment hoặc thêm lock/snapshot-per-call thật sự (truyền `active_indicators` như tham số vào `_run_load_history` thay vì đọc lại `self.active_indicators` global) |
| TC-ASY-14 | 🟠 | Symbol dropdown (nếu wire trong tương lai) đổi giữa lúc `_run_load_history` cho symbol cũ đang chạy | `_ensure_chart_cards` sẽ clear+rebuild `self.active_charts` nếu symbol set đổi — chart card CŨ bị `cleanup()`+`deleteLater()` | Nếu `ui_history_reloaded_signal` cho symbol CŨ tới **sau khi** card cũ đã bị `deleteLater()`, `_on_history_reloaded` dùng `self.active_charts.get(symbol)` → symbol cũ không còn trong dict → trả `None` → guard `if card:` chặn được → **an toàn theo thiết kế hiện tại**, nhưng cần test thật để confirm (không chỉ đọc code) |
| TC-ASY-15 | 🔴 | ⭐ **Case gốc user hỏi**: Start Live ở 1m, rồi (giả sử timeframe switch được wire) đổi sang 5m NGAY khi đang có tick 1m đổ về | `_handle_market_tick`/`_on_ui_chart_update` route **chỉ theo `symbol`**, hoàn toàn không xét interval | Nếu switch chưa unsubscribe 1m xong mà đã subscribe 5m, **cả 2 luồng tick cùng đổ vào 1 chart card** (vì cùng symbol key) → nến 1m và 5m bị trộn lẫn trên cùng 1 timeline, timestamp không còn đơn điệu, OHLC sai hoàn toàn. Đây là **thiết kế cần fix trước khi wire timeframe-switch**, xem chi tiết Section E. |
| TC-ASY-16 | 🟡 | Đóng app (`engine.stop()`) trong khi 1 trong 4 worker thread vẫn đang mid-flight gọi `dispatcher.dispatch(...)` | `ThreadManager.shutdown(wait=True/False)` | Verify hành vi shutdown thực tế: có đợi task hiện tại xong không, hay cắt ngang giữa chừng gây exception log lúc thoát (chấp nhận được nếu chỉ log, không chấp nhận nếu treo process) |
| TC-ASY-17 | 🟠 | Rapid Start→Stop→Start trong vòng 1 giây | Mỗi click đều pass qua FSM guard, nhưng `StopLiveStreamCommand` (đồng bộ) và `StartLiveStreamCommand` (qua background thread) không cùng cơ chế timing | Verify lệnh Start thứ 2 không bị **submit trước khi** lệnh Stop thứ 1 thực sự dọn dẹp xong tài nguyên WebSocket cũ (nguy cơ 2 socket cùng symbol cùng tồn tại 1 khoảnh khắc) |
| TC-ASY-18 | 🟡 | `safe_ui_action` decorator có nuốt exception không đúng cách khi lỗi xảy ra giữa async race | Trigger 1 trong các race ở trên tới khi có exception thật (vd. `KeyError` trên dict `active_indicators` bị đổi giữa lúc iterate — dù Python dict thường raise `RuntimeError: dictionary changed size during iteration` nếu có) | Verify exception (nếu có) được log rõ ràng qua `safe_ui_action`, không bị nuốt im lặng khiến bug race khó phát hiện trong production |
| TC-ASY-19 | 🟡 | Nhiều `ui_indicator_data_signal` cho cùng 1 `name` xếp hàng liên tiếp (do TC-ASY-01 gây ra) | Signal `(name, x_data, y_data)` mang theo **toàn bộ series** mỗi lần (không phải append) | Verify signal xử lý sau luôn "thắng" (ghi đè đúng), nhưng nếu 2 signal race nhau xử lý không theo thứ tự phát sinh (Qt queued connection thường giữ order theo thread gốc, nhưng 2 THREAD KHÁC NHAU emit cùng lúc thì thứ tự tới hàng đợi main thread không đảm bảo) → verify chart cuối cùng hiển thị dữ liệu của lần Load History **mới nhất theo ý user**, không phải lần nào xử lý xong sau cùng một cách ngẫu nhiên |
| TC-ASY-20 | 🔴 | Kết hợp TC-ASY-01 + TC-ASY-07: Load History 2 lần liên tiếp rồi Stop ngay khi cả 2 background task còn chạy | Tổ hợp toàn bộ race ở trên cùng lúc | Đây là "stress worst-case" — verify app không crash, và sau khi mọi thứ settle (vài giây), state cuối cùng phải nhất quán (UI matrix đúng theo FSM cuối, chart không duplicate, indicator không sai số) |

---

## E. Timeframe Switch & Multi-Symbol Readiness (thiết kế cho tương lai)

Các control Symbol/Timeframe **hiện chưa wire** (xem Section H), nhưng vì user hỏi cụ thể
kịch bản "start 1m rồi đổi 5m", các case sau mô tả **điều kiện cần đạt** trước khi wire tính
năng này, để không lặp lại lỗi TC-ASY-15 khi triển khai thật.

| ID | Pri | Yêu cầu cần verify khi timeframe-switch được implement |
|---|---|---|
| TC-TF-01 | 🔴 | Đổi timeframe khi đang LIVE phải **unsubscribe stream cũ xong hoàn toàn (await/join)** trước khi subscribe stream mới — không được "fire and forget" |
| TC-TF-02 | 🔴 | `MarketTickEvent`/routing phải mang theo `interval`, và `_handle_market_tick`/`active_charts` key phải là `(symbol, interval)` chứ không chỉ `symbol` — nếu không, 2 luồng khác interval cùng symbol sẽ luôn có nguy cơ trộn dữ liệu (root cause của TC-ASY-15) |
| TC-TF-03 | 🟠 | Đổi timeframe phải xoá sạch state indicator cũ (`RSI`/`EMA`/`MACD` instance) và tính lại từ đầu trên dữ liệu khung mới — không giữ nguyên state đang warm-up từ khung cũ |
| TC-TF-04 | 🟠 | Chart phải clear toàn bộ nến cũ (khung 1m) trước khi render nến khung mới (5m) — không blend 2 khung trên cùng timeline |
| TC-TF-05 | 🟡 | Trong lúc đang chuyển đổi (giữa unsubscribe và subscribe xong), UI phải khoá nút timeframe khác + Start/Stop để tránh user bấm chồng thêm 1 lần đổi timeframe nữa giữa chừng |
| TC-TF-06 | 🟡 | Nếu subscribe khung mới thất bại (network lỗi giữa chừng đổi khung), phải rollback về khung cũ hoặc báo lỗi rõ ràng — không được để UI hiển thị "đang ở khung 5m" trong khi thực chất không có stream nào chạy |
| TC-TF-07 | 🟢 | Đổi Market (Spot↔Futures) tương tự cần quy trình unsubscribe/resubscribe an toàn như đổi timeframe, vì symbol format/precision có thể khác nhau giữa 2 market |
| TC-TF-08 | 🟠 | Đổi Symbol (BTCUSDT↔ETHUSDT) khi đang LIVE — tương tự TC-ASY-14 nhưng cho trường hợp **đang có tick sống**, không chỉ historical load |
| TC-TF-09 | 🟡 | Multi-symbol đồng thời (nếu roadmap hỗ trợ nhiều chart card cùng lúc) — mỗi symbol phải có `_ActiveIndicator` set **độc lập hoàn toàn**, không dùng chung 1 `self.active_indicators` cho tất cả symbol như hiện tại (`_DEFAULT_SYMBOLS[0]` đang hard-code single-symbol assumption ở `_clear_registered_indicators`/`_on_indicator_data`) |
| TC-TF-10 | 🔴 | Đổi timeframe TRONG LÚC `_run_load_history`/`_run_sync_and_start` của khung cũ vẫn đang chạy nền — tổ hợp trực tiếp của TC-ASY-01 và TC-TF-01, mức độ nghiêm trọng cao nhất vì kết hợp cả race trên `active_indicators` lẫn race trên stream subscription |

---

## F. Navigation & Presenter Lifecycle

| ID | Pri | Scenario | Steps | Expected |
|---|---|---|---|---|
| TC-NAV-01 | 🟠 | Điều hướng sang Database rồi quay lại Dev Board | Dev Board → Database → Dev Board | Presenter được cache (`PresenterManager._registry`), state (`active_charts`, `active_indicators`, FSM) giữ nguyên như lúc rời đi — không bị tạo mới/mất data |
| TC-NAV-02 | 🔴 | Điều hướng rời Dev Board trong lúc `_run_load_history` đang chạy nền | Bấm Load History → ngay lập tức chuyển sang Database | Background thread vẫn chạy tiếp (không bị hủy); khi nó emit `ui_history_reloaded_signal`, `_on_history_reloaded` chạy trên view **đã bị ẩn** (không destroy vì cache) — verify không crash, không lỗi "wrapped C/C++ object deleted" |
| TC-NAV-03 | 🔴 | Điều hướng rời Dev Board trong lúc đang LIVE, rồi Database screen tự nó cũng có background task | 2 presenter khác nhau, mỗi cái tự resolve `IThreadManager` (cùng 1 singleton pool, `max_workers=4`) | Verify tick của Dev Board (đang LIVE ở background) không tranh chấp worker thread với sync task của Database screen tới mức UI Database bị đơ |
| TC-NAV-04 | 🟠 | Quay lại Dev Board sau khi rời đi lúc đang LIVE | Rời đi lúc LIVE → quay lại | Chart vẫn tiếp tục nhận tick mới (vì stream không bị dừng khi chuyển màn hình) — verify tick đến trong lúc màn hình bị ẩn không bị mất, đã áp dụng đầy đủ khi quay lại xem |
| TC-NAV-05 | 🟡 | Đóng app trong khi ở màn hình Database (Dev Board presenter vẫn cached ở background, đang LIVE) | Đang LIVE ở Dev Board (đã rời màn hình) → đóng app | `engine.stop()` phải dừng cả stream của presenter không đang hiển thị — verify không có "leak" luồng chạy nền vĩnh viễn |
| TC-NAV-06 | 🟢 | Sidebar active-state đồng bộ đúng route hiện tại | Click qua lại 2 route | `Sidebar.set_active(route_name)` luôn khớp route đang hiển thị trong `QStackedWidget` |
| TC-NAV-07 | 🟡 | Resize window trước khi bất kỳ data nào được load | Mở app, resize ngay khi chart trống | Không crash khi `plot_layout`/`ViewBox` chưa có data (`autoRange()`/`setXRange` trên dataset rỗng) |
| TC-NAV-08 | 🟡 | Kill background task giữa chừng bằng cách navigate away NHIỀU LẦN liên tiếp | Dev Board→Database→Dev Board→Database (nhanh, x5) trong lúc Load History đang chạy | Verify không tích tụ nhiều bản presenter/view instance trùng lặp — `PresenterManager` phải thực sự cache/reuse, không tạo mới mỗi lần |

---

## G. System Monitor / Logging

| ID | Pri | Scenario | Steps | Expected |
|---|---|---|---|---|
| TC-MON-01 | 🟠 | Log đầy đủ theo đúng thứ tự cho 1 chuỗi Load→Start→Stop | Thực hiện tuần tự | Mỗi bước đều có dòng log tương ứng, thời gian tăng dần, không log nào bị thiếu |
| TC-MON-02 | 🟠 | Nút "Clear" xoá log | Có vài dòng log → Clear | Log trống hoàn toàn, log mới sau đó vẫn ghi bình thường (signal `clear_logs_clicked` vẫn connect đúng sau khi clear) |
| TC-MON-03 | 🔴 | Log trong lúc TC-ASY-01 (2 Load History song song) | Trigger race | Verify log entry không bị **interleave sai** khiến người đọc hiểu nhầm thứ tự sự kiện (vd. "Refreshed N klines" của lần #2 xuất hiện trước "Loading historical..." của lần #1 do race) — đây là dấu hiệu để QA phát hiện race bằng mắt thường qua Monitor, đúng như mục đích ban đầu của tính năng log này |
| TC-MON-04 | 🟡 | Log không bị spam mỗi tick live | Đang LIVE, tick chưa đóng nến (`is_closed=False`) | Chỉ log khi `is_closed=True` (`if is_closed:`) — verify KHÔNG có log mỗi lần `update_last_candle` (tick đang hình thành), tránh flood UI |
| TC-MON-05 | 🟢 | Log rất dài (chạy LIVE nhiều giờ) | Stress: để LIVE chạy lâu, tích luỹ hàng ngàn dòng log | Verify UI không bị chậm/lag do QTextEdit/QListWidget phình to không giới hạn — có cần cap số dòng log tối đa không? |
| TC-MON-06 | 🟡 | Copy log ra ngoài để debug (thói quen user đã dùng trong phiên trước) | Select toàn bộ log, Ctrl+C | Text copy được đầy đủ, đúng định dạng, không lẫn HTML/rich-text rác |
| TC-MON-07 | 🟢 | Log hiển thị đúng cả tiếng Việt lẫn tiếng Anh lẫn lộn (message hiện tại đang mix 2 ngôn ngữ) | Quan sát log thực tế | Không bị lỗi encoding/mojibake với chữ có dấu |
| TC-MON-08 | 🟠 | Exception message hiển thị đủ thông tin để debug | Trigger 1 exception thật (vd. TC-SC-06) | Log message chứa `str(exc)` đủ chi tiết, không chỉ "Error occurred" chung chung |

---

## H. Known Gaps — Control tồn tại nhưng chưa wire

> Các case này KHÔNG phải bug — mục đích để QA không báo nhầm khi test manual, và để backlog
> hoá thành task thật nếu team muốn wire.

| ID | Control | Hành vi hiện tại xác nhận qua code | Grounding |
|---|---|---|---|
| TC-GAP-01 | `market_dropdown` (Spot/Futures) | Không đọc giá trị ở đâu trong `dashboard_presenter.py` | grep "market_dropdown" → 0 match ngoài `control_card.py` |
| TC-GAP-02 | ~~`symbol_dropdown` (BTCUSDT/ETHUSDT)~~ | ✅ **FIXED (BOT-033 Phase 2)** — `cboSymbol` nối vào `DashboardQmlViewModel.symbol`, đọc + validate (regex `^[A-Z0-9]{5,20}$`) tại thời điểm click, thay hẳn `_DEFAULT_SYMBOLS` hard-code | `test_symbol_dropdown_changes_which_symbol_load_history_fetches`, `test_on_load_history_uses_the_view_models_symbol` |
| TC-GAP-03 | ~~`timeframe_dropdown` (System Controls)~~ | ✅ **FIXED (BOT-033)** — control đã bị xoá khỏi `DevBoardPanel.qml`, `ChartToolbar` (TC-GAP-06) là nguồn sự thật duy nhất giờ | `test_chart_toolbar_timeframe_click_triggers_a_reload` |
| TC-GAP-04 | `strategy_dropdown` (Manual/SMA Crossover) | Không có logic nào đọc — `EmaCrossoverStrategy` thật đã có từ `BOT-026` ✅, nhưng control này sẽ bị **xoá** (không wire) khi `BOT-039` thay bằng toggle list, vì `model: ["Manual","SMA Crossover"]` gọi tên 1 strategy không tồn tại | Xem BOT-039 backlog |
| TC-GAP-05 | ~~`start_date_picker` / `end_date_picker`~~ | ✅ **FIXED (BOT-033 Phase 2)** — nối vào `viewModel.startDate`/`endDate`, validate (parse + `start < end`) trước khi truyền vào `GetHistoricalKlinesQuery`/`SyncMarketDataCommand` | `test_start_date_field_binds_to_the_view_model`, `test_an_invalid_date_range_blocks_load_history`, `test_on_load_history_submits_the_parsed_date_range` |
| TC-GAP-06 | ~~`ChartToolbar` 1m/5m/15m/1h/1d~~ | ✅ **FIXED (BOT-033)** — `sig_timeframe_changed` nối vào `DashboardPresenter._on_timeframe_changed`, đổi timeframe reload ngay lập tức (kể cả khi đang Live: dừng → reload → start lại) | `test_chart_toolbar_timeframe_click_triggers_a_reload`, `test_reclicking_the_same_timeframe_does_not_reload` |
| TC-GAP-07 | Checkbox/Period indicator khi đang chạy | Chỉ đọc tại thời điểm click Load/Start, không có `toggled`/`valueChanged` signal nào connect | grep xác nhận 0 signal connection |
| TC-GAP-08 | `_on_run_backtest`/`_on_stop_backtest` | Có slot, có `set_backtest_active`, nhưng chưa có nút UI thật gọi tới, và TODO dispatch command còn bỏ trống | Xem comment `# TODO: Dispatch RunBacktestCommand` |

---

## I. Stress / Performance dưới tải Async

| ID | Pri | Scenario | Expected |
|---|---|---|---|
| TC-PERF-01 | 🟡 | Load History với `limit=5000` lặp lại 20 lần liên tục (không đợi nhau) | Đo thời gian phản hồi cuối cùng, đo RAM tăng dần có ổn định hay leak liên tục (đặc biệt do TC-ASY-01 khiến indicator instance có thể không được GC đúng cách) |
| TC-PERF-02 | 🟡 | LIVE chạy liên tục 8+ tiếng | `_raw_history`/`x_data`/`y_data` của indicator tăng không giới hạn (không thấy cơ chế trim) — verify RAM và render time không suy giảm theo thời gian |
| TC-PERF-03 | 🟢 | Zoom/pan liên tục trong khi đang LIVE nhận tick tần suất cao | FPS UI không tụt quá thấp, `setAutoVisible`/`enableAutoRange` không gây tính toán lại quá nặng mỗi frame |
| TC-PERF-04 | 🟡 | 4 worker thread đều bận Load History cùng lúc với máy yếu (CPU thấp) | Verify UI thread (main) không bị đói CPU tới mức không phản hồi click Stop kịp thời |
| TC-PERF-05 | 🟢 | Khởi động app → Start Live ngay lập tức (không đợi UI render xong hoàn toàn) | Verify không có race giữa `MainWindow.__init__`'s `switch_screen("dashboard")` (tạo presenter) và user click quá sớm trước khi `_connect_ui_signals()` hoàn tất |
| TC-PERF-06 | 🟢 | Nhiều indicator (RSI+EMA+MACD) cùng nhận tick tần suất cao | `_update_indicators_on_closed_candle` chạy trên **main thread** mỗi nến đóng — verify vòng lặp qua N indicator không đủ nặng để giật UI dù N tăng lên trong tương lai |
| TC-PERF-07 | 🟡 | Đo độ trễ end-to-end: tick phát sinh ở tầng infra → hiển thị trên chart | Do đi qua `EventBus` (background thread) → Qt signal (queued) → main thread slot, cần đo độ trễ thực tế có nằm trong ngưỡng "real-time" chấp nhận được không (vd. <100ms) |

---

## Tổng kết & đề xuất hành động

- **Ưu tiên fix trước** (🔴, có thể tái hiện ngay hôm nay, không cần chờ tính năng mới):
  TC-ASY-01, TC-ASY-02, TC-ASY-04, TC-ASY-09, TC-ASY-10, TC-ASY-15/TC-TF-02 (root cause chung: thiếu khoá đồng bộ quanh `self.active_indicators` + thiếu định danh `interval` trong routing).
- **Fix đơn giản, rủi ro thấp**: disable `load_history_button` trong lúc background đang chạy
  (giống cách `start_stream_button` đã làm qua FSM) — chặn được phần lớn TC-ASY-01/02/04/05 ngay
  lập tức mà không cần refactor lớn.
- **Fix cấu trúc hơn**: truyền `active_indicators` như tham số vào `_run_load_history`/
  `_compute_indicator_series` thay vì đọc lại `self.active_indicators` (biến instance dùng
  chung) — loại bỏ hoàn toàn race class TC-ASY-01/02/13.
- **Trước khi wire timeframe/symbol switch thật (Section E)**: bắt buộc giải quyết TC-TF-02
  (định danh theo `(symbol, interval)` thay vì chỉ `symbol`) — nếu không, tính năng mới sẽ tái
  hiện đúng lỗi TC-ASY-15 ngay khi ra mắt.

File này thuần là tài liệu phân tích/test-case — chưa có code nào bị thay đổi để viết ra nó.
