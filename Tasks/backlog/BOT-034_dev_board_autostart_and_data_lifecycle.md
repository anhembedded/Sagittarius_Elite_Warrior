# Nhiệm vụ: Dev Board — Timeframe thật, Auto-start Live, Render-window tách khỏi Fetch-amount

> **Đọc file này trước khi code.** Đây là task **tư vấn → đã chốt toàn bộ**, xem lại
> `Tasks/UserStory_Propose.md` (US-03/05/06/08) cho ngữ cảnh gốc. Đã qua 2 vòng hỏi-đáp với user
> (ý nghĩa auto-start/render-vs-fetch, rồi 4 câu hỏi kỹ thuật ở §2.1) — **không còn quyết định
> treo**, sẵn sàng implement.
>
> ⚠️ **Trùng số với task có sẵn — đã đổi từ BOT-033 sang BOT-034.** File này ban đầu tạo nhầm số
> `BOT-033` mà không kiểm tra `Tasks/in_progress/` trước — `BOT-033` đã có sẵn
> (`BOT-033_qml_user_actions.md`, một task khác đang chạy song song). §6 (timeframe) của file
> này **trùng phạm vi** với `BOT-033_qml_user_actions.md` Phase 2 ("Nối Chart toolbar với cùng
> timeframe selection") — §6 đã được implement và commit (nhầm dưới nhãn "BOT-033" trong message
> commit, không sửa lại lịch sử git) **trước khi** phát hiện ra collision này. Đã ghi chú chéo
> sang `BOT-033_qml_user_actions.md` để task đó không làm lại. Nếu bạn đang chạy song song
> `BOT-033_qml_user_actions.md`, hãy đọc kỹ §6 trước khi động vào `ChartToolbar`/`_on_timeframe_changed`.

## 1. Mục tiêu (Objective)
Đóng 3 gap: (a) timeframe selector trên Dev Board hiện chỉ là cosmetic (TC-GAP-03/06), (b) Load
History luôn fetch cứng `limit=5000` bất kể timeframe/indicator đang bật, không phân biệt "hiển
thị bao nhiêu" với "tải bao nhiêu", (c) không có nút "auto-start" — user luôn phải bấm Start Live
thủ công, và khi bấm mà mất mạng thì không có fallback nào.

## 2. Quyết định đã chốt với user (đọc trước khi code, đừng tự suy diễn lại)

1. **US-03 (auto-load 75 candle)**: 75 là **số nến RENDER trên màn hình**, không phải số nến
   FETCH từ DB/Binance. Số fetch phải **đủ cho indicator warmup + các ràng buộc khác** (nguyên
   văn user, không giải thích thêm "ràng buộc khác" là gì cụ thể — tự suy luận hợp lý: EMA(200)
   cần ít nhất 200 bar mới ra điểm đầu tiên, nến render mà thiếu indicator thì vô nghĩa). Xem §4.
2. **US-08 (auto-start)**: nghĩa là **live stream** (không phải chỉ auto-load lịch sử). Nếu sau
   1-2 giây không kết nối được, **fallback sang load lịch sử mới nhất**. User nói *"trong
   sagittarius có cái hỗ trợ event timeout rồi"* — **đã kiểm tra, KHÔNG tìm thấy** utility "wait
   for event with timeout" nào trong `sagittarius_engine` (đã grep toàn bộ `task_manager.py`,
   `scheduler.py`, `i_task_manager.py`, `ipc_queue_event_bus.py` — chỉ có timeout cho
   thread-join/queue-poll lúc shutdown, không phải thứ này cần). **Không chặn task lại vì lý do
   này** — thiết kế ở §5 dùng đúng building block đã có sẵn (`QTimer` + `MarketTickEvent` đã được
   Presenter subscribe từ trước) mà không cần thêm gì vào engine.

### 2.1. 4 câu hỏi mở — đã được user trả lời, KHÔNG còn là quyết định treo
| # | Câu hỏi | Trả lời user | Áp dụng ở |
|---|---|---|---|
| 1 | Fetch safety floor bao nhiêu? | **Đọc từ config, mặc định 75** (không hardcode 300) | §4 |
| 2 | Xoá hẳn nút Load Hist? | **Giữ lại** | §5 |
| 3 | Fallback xong có tự retry Start Live? | **Không — chờ user bấm lại** | §5 |
| 4 | Đổi timeframe giữa lúc đang Live? | **Cho đổi — dừng, load lại theo timeframe mới, start lại** | §6 |

## 3. RULES — bắt buộc tuân thủ (thừa hưởng từ BOT-032, áp dụng lại)
| # | Rule |
|---|---|
| R1 | `domain/` không import PySide6/pyqtgraph/sagittarius_engine. |
| R4 | Worker nền chỉ `.emit()` Qt signal — mutation ViewModel luôn ở `@Slot` main thread. |
| R8 | 1 concern = 1 file — xem phân chia file ở mỗi mục dưới để nhiều task chạy song song. |
| R9 | Dùng `../.venv/Scripts/python.exe`, KHÔNG dùng `python` trần (xem BOT-032 §3 R9 để biết lý do). |
| **R10 (mới)** | Task này **phụ thuộc BOT-032 Phase 6** cho phần "indicator warmup" (§4) — nếu Phase 6 (chuyển RSI/EMA/MACD thành script) CHƯA xong khi bắt đầu task này, làm §4 dựa trên `active_indicators` cũ (`_ActiveIndicator.indicator.period` nếu có) thay vì `_script_runner`, và để lại TODO rõ ràng để dọn lại sau khi Phase 6 xong — đừng chặn task này chờ Phase 6. |

---

## 4. Render-window (75) tách khỏi Fetch-amount (US-03)

### Hiện trạng
`dashboard_presenter.py`: `_DEFAULT_KLINE_LIMIT = 5000`, dùng thẳng làm `limit` cho
`GetHistoricalKlinesQuery` — không có khái niệm "render window" riêng. `ChartCard._set_initial_view_range()`
đã có sẵn logic tương tự (giới hạn *view* ban đầu xuống `_DEFAULT_INITIAL_VISIBLE_CANDLES = 150`)
nhưng đó là zoom-level, KHÔNG làm giảm dữ liệu đã tải — 5000 nến vẫn nằm trong bộ nhớ.

### Thiết kế
Tách 2 khái niệm rõ ràng, **không đụng `ChartCard`** (nó đã đúng việc của nó — chỉ zoom view,
không quyết định fetch bao nhiêu):

**Quyết định đã chốt**: safety floor **không hardcode** — đọc từ `IConfig` qua `self.config`
(property có sẵn trên `BasePresenter`, xem cách `settings_presenter.py._load_from_config` dùng
`self.config.get_all()` / `IConfig.get(key, default, cast)`), mặc định **75** nếu config không có
key này (tức là mặc định floor == render window, không có "đệm an toàn" thừa trừ khi user tự
config cao hơn). Thêm key mới `DEV_BOARD_MIN_FETCH_CANDLES` vào `src/config/user_config.json`
(cùng nhóm với `DEFAULT_SYNC_DAYS` — cả hai đều là "user tự chỉnh lượng dữ liệu tải").

```python
# dashboard_presenter.py — hằng số mới
_RENDER_WINDOW_CANDLES = 75          # đúng theo US-03 — KHÔNG thay _DEFAULT_INITIAL_VISIBLE_CANDLES
                                       # của ChartCard (đó là zoom-level, đây là fetch-level; xem dưới)
_MIN_FETCH_CANDLES_CONFIG_KEY = "DEV_BOARD_MIN_FETCH_CANDLES"
_DEFAULT_MIN_FETCH_CANDLES = 75       # fallback nếu config không có key trên

def _compute_fetch_limit(self) -> int:
    """
    @brief Bao nhiêu nến cần TẢI, không phải bao nhiêu nến RENDER.
    @details max(75 render window, warmup lớn nhất trong số script đang bật, floor từ config).
    Đọc `self._enabled_script_keys()` + tra warmup qua registry — KHÔNG instantiate script chỉ để
    hỏi warmup (tốn), dùng class attribute tĩnh (xem BaseIndicatorScript.min_warmup_bars bên dưới).
    """
    slowest = max(
        (
            self._script_registry.available()[key].min_warmup_bars
            for key in self._enabled_script_keys()
            if key in self._script_registry.available()
        ),
        default=0,
    )
    floor = self.config.get(
        _MIN_FETCH_CANDLES_CONFIG_KEY, _DEFAULT_MIN_FETCH_CANDLES, cast=int
    )
    return max(_RENDER_WINDOW_CANDLES, slowest, floor)
```

⚠️ **Lưu ý nhỏ trước khi code**: `dashboard_presenter.py.__init__` hiện resolve
`IndicatorScriptRegistry` vào biến cục bộ `script_registry` (không phải `self._script_registry`)
— `_compute_fetch_limit()` ở trên cần registry, nên đổi biến cục bộ đó thành instance attribute
trước (1 dòng, không rủi ro).

**API mới cần thêm vào `BaseIndicatorScript`** (domain layer, file `base_indicator_script.py` —
thuộc phạm vi BOT-032, nhưng chỉ 1 dòng, không cần chờ hết Phase 6 mới thêm được):
```python
class BaseIndicatorScript(ABC):
    min_warmup_bars: int = 0   # MỚI — script author tự khai báo (vd. EMA(200) -> 200).
                                # KHÔNG tự tính bằng cách chạy thử — script có thể compose nhiều
                                # indicator khác period nhau, chỉ tác giả biết con số đúng.
```
Mỗi script mẫu hiện có cần khai báo lại: `ema_ribbon` → 200 (EMA 200 là chậm nhất), `macd_full` →
~35 (26 slow + 9 signal), `ema_cross` → 26, `dev_showcase` → 200 (EMA slowest trong đó). Guard
test mới: mọi subclass `BaseIndicatorScript` phải có `min_warmup_bars > 0` nếu dùng bất kỳ
indicator nào có warmup (tránh quên khai báo) — cân nhắc, có thể chỉ warning log thay vì fail
cứng nếu thấy quá chặt.

`_on_load_history`/`_run_load_history`/`_run_sync_and_start`: thay `_DEFAULT_KLINE_LIMIT` bằng
`self._compute_fetch_limit()` gọi tại đúng thời điểm click (giữ đúng hợp đồng "không hồi tố" của
TC-GAP-07 — đổi script bật/tắt sau khi đã Load không ảnh hưởng ngược).

`_set_initial_view_range` bên `ChartCard` **không cần sửa** — nó tự động hoạt động đúng vì giờ dữ
liệu tải về đã gần khớp render window rồi (trước đây phải zoom từ 5000 xuống 150, giờ zoom từ vd.
300 xuống 75 — cùng cơ chế, chỉ input nhỏ hơn). Có thể cân nhắc đổi
`_DEFAULT_INITIAL_VISIBLE_CANDLES` từ 150 xuống 75 cho khớp US-03, **hỏi user trước khi đổi** vì
đây là hành vi zoom mặc định ảnh hưởng UX trực tiếp, không phải chi tiết kỹ thuật.

---

## 5. Auto-start Live Stream với fallback (US-08)

### Hiện trạng quan trọng (đã verify, không phải suy đoán)
- `StartLiveStreamCommandHandler.execute()` → `BinanceWebsocketService.start_stream()` trả `True`
  ngay khi **task được spawn** (`task_manager.spawn(...)`), KHÔNG đợi kết nối WebSocket thật sự
  thành công. `ui_stream_success_signal` vì vậy fire gần như ngay lập tức bất kể sau đó kết nối
  Binance có thật sự thành công hay không — **không dùng được làm tín hiệu "đã kết nối".**
- `_run_stream()` (trong `binance_websocket_service.py`) khi gặp `OSError` (mất mạng) chỉ log +
  `sleep(5)` rồi retry vô hạn — không emit event/signal nào ra ngoài báo "đang retry".
- **Tín hiệu đáng tin cậy nhất sẵn có**: `DashboardPresenter` đã subscribe
  `self.event_bus.on(MarketTickEvent, self._handle_market_tick)` — tick đầu tiên nhận được CHÍNH
  LÀ bằng chứng kết nối thật đã thành công. Đây là building block dùng để giải quyết yêu cầu
  "1-2 giây không kết nối được thì fallback", không cần thêm event mới vào engine.

### Thiết kế — file mới `screens/dashboard/autostart_controller.py` (theo R8, tách khỏi presenter)
```python
class AutoStartController:
    """
    @brief Khi Dev Board mở, tự bấm Start Live; nếu không có MarketTickEvent nào trong
    `fallback_seconds`, tự chuyển sang Load History thay vì treo màn hình chờ.
    @details KHÔNG dừng luồng Start Live đang chạy nền khi fallback — nếu Binance kết nối
    muộn (vd. mạng chậm chứ không phải mất mạng), tick vẫn tới và chart vẫn tự cập nhật lên
    live bình thường, chỉ là user không phải nhìn màn hình trống trong lúc chờ.
    """
    def __init__(
        self,
        start_stream: Callable[[], None],       # presenter._on_start_stream
        load_history: Callable[[], None],       # presenter._on_load_history
        make_timer: Callable[[int, Callable], QTimer],   # inject để test không cần đợi thật
        fallback_seconds: int = 2,
    ) -> None: ...
    def begin(self) -> None:
        """Gọi 1 lần khi Dev Board vừa mở (view.load_qml xong)."""
    def on_market_tick(self) -> None:
        """Gọi từ _handle_market_tick — huỷ timer fallback nếu còn đang chờ."""
```
`dashboard_presenter.__init__` (cuối, sau `_connect_engine_events()`): tạo
`self._autostart = AutoStartController(...)`, gọi `self._autostart.begin()`. `_handle_market_tick`
gọi thêm `self._autostart.on_market_tick()` ở đầu hàm (idempotent — gọi nhiều lần sau khi đã huỷ
timer không sao).

⚠️ **Không dùng `time.sleep`/`threading.Timer` trong Presenter** (main thread) — dùng
`QtCore.QTimer.singleShot` hoặc instance `QTimer` thật để không block UI, và để `qtbot` test được
qua `qtbot.wait`.

### Quyết định đã chốt (§2.1)
1. **Nút Load Hist**: giữ lại. `AutoStartController` chỉ tự bấm lúc Dev Board *vừa mở* — không
   thay thế, không disable nút thủ công.
2. **Sau khi fallback**: không tự retry Start Live — dừng lại, chờ user chủ động bấm "Start Live"
   lần nữa. `AutoStartController.begin()` chỉ chạy đúng 1 lần cho mỗi lần Dev Board được mở
   (không lặp lại nếu fallback đã xảy ra).

---

## 6. Timeframe selector thật (US-05 + US-06)  *(ĐÃ XONG)*

### Hiện trạng
2 nơi chọn timeframe cùng tồn tại, cả 2 đều cosmetic:
- `cboTimeframe` (ComboBox, System Controls card, `DevBoardPanel.qml`) — không đọc ở đâu.
- `ChartCard.toolbar` (`ChartToolbar`, đã có `sig_timeframe_changed = QtCore.Signal(str)`, đúng
  design "dumb component, không tự fetch" — chỉ chưa được connect, TC-GAP-06).

### Quyết định thiết kế: giữ `ChartToolbar`, bỏ `cboTimeframe`
`ChartToolbar` đã đúng vị trí UX (trên chart, cạnh chart type switcher) và đã đúng kiến trúc (Qt
signal sẵn sàng nối) — chỉ cần **nối dây**, không cần "tách thành component riêng" như US-05 chữ
nguyên văn đề xuất (đã có rồi). `cboTimeframe` nên bỏ khỏi `DevBoardPanel.qml` để tránh 2 nguồn sự
thật (nếu user bấm "5m" trên toolbar nhưng `cboTimeframe` vẫn hiện "1m" thì gây hiểu lầm).

### Việc cần làm
1. `dashboard_presenter.py`: nối `card.toolbar.sig_timeframe_changed.connect(self._on_timeframe_changed)`
   (đâu đó gần `_ensure_chart_cards`, nơi `ChartCard` được tạo — chỉ cần nối 1 lần/card).
2. `_on_timeframe_changed(self, timeframe: str) -> None`: đổi `_DEFAULT_INTERVAL_STR` từ hằng số
   module-level thành instance attribute `self._active_interval`, cập nhật rồi gọi lại đúng luồng
   Load History hiện tại (đọc lại giá trị này thay vì hằng số ở mọi chỗ đang dùng
   `_DEFAULT_INTERVAL_STR`). **Đổi timeframe giữa chừng lúc đang LIVE**: đã chốt (§2.1) — **cho
   đổi được**: dừng stream cũ (`_on_stop_stream` hoặc gọi thẳng logic của nó), cập nhật
   `self._active_interval`, rồi chạy lại đúng luồng `_run_sync_and_start` (sync → reload history
   theo timeframe mới → start stream lại) — tái dùng nguyên luồng Start Live đã có, không viết
   luồng riêng cho trường hợp "đổi timeframe khi đang Live".
3. Xoá `cboTimeframe` (và `cboSymbol`/`cboStrategy` nếu cũng quyết định bỏ luôn — ngoài phạm vi
   task này trừ khi user muốn gộp, xem TC-GAP-01/02/04).
4. Domain đã đủ: `TimeFrame` enum (`domain/value_objects/timeframe.py`) đã có nhiều mốc hơn 5 cái
   hard-code trong `ChartToolbar.DEFAULT_TIMEFRAMES` — mở rộng danh sách nút cũng dễ, không phải
   việc của task này trừ khi user yêu cầu thêm.

### Test gate
`tests/unit/presentation/ui/screens/test_dashboard_presenter.py`: test timeframe signal → đúng
interval được dùng ở lần Load History/Start Live kế tiếp (mirror style TC-GAP-07 test).
`tests/integration/presentation/ui/test_dev_board_known_gaps.py::test_chart_toolbar_...` (đang note
"chưa connect" — xem lại test này, có thể cần đổi từ "known gap" thành "đã fix").

---

## 7. Phụ thuộc & thứ tự đề xuất
1. ~~Làm §6 (timeframe) trước~~ — **đã xong**.
2. Làm §4 (render-window/fetch) tiếp — cần `min_warmup_bars` trên script, `BOT-032` Phase 6 (RSI/
   EMA/MACD → script) **đã xong** nên không còn blocker.
3. Làm §5 (auto-start) sau cùng — phụ thuộc §6 (interval nào để auto-start, đã xong) gián tiếp,
   và là phần rủi ro UX cao nhất (đổi hành vi mặc định khi mở màn hình mỗi lần vào Dev Board).

## 8. Phụ thuộc (Dependencies)
- `BOT-032` ✅ (toàn bộ, kể cả Phase 6) — `IndicatorScriptRegistry`, `min_warmup_bars` cắm vào đây.
- Không phụ thuộc `BOT-026` (strategy) — task này chỉ động tới indicator + timeframe + stream
  lifecycle.
- ⚠️ `BOT-033_qml_user_actions.md` (task khác, đang chạy song song) — Phase 2 của task đó cũng
  định nối `Symbol`/`Start date`/`End date` với Presenter, phạm vi **không trùng** §4/§5 của file
  này (fetch-amount/auto-start), chỉ trùng đúng phần timeframe (§6, đã xong — xem cảnh báo đầu
  file). Đọc task đó trước khi làm §4/§5 để tránh xung đột nếu nó cũng động tới
  `_on_load_history`/`_on_start_stream`.
