# Nhiệm vụ: Dev Board — Tự tải thêm dữ liệu cũ khi kéo/scroll ra rìa trái chart (US-04)  *(ĐÃ XONG — Phase 1)*

> **Đọc file này trước khi code.** 3 câu hỏi mở ở §2.1 **đã được user chốt** — sẵn sàng implement,
> Phase 1 KHÔNG bao gồm auto-sync-from-Binance khi DB thiếu dữ liệu (để Phase 2, task riêng).
> Nguồn gốc: `Tasks/UserStory_Propose.md` US-04, đã đánh giá sơ bộ trong phiên tư vấn ban đầu (xem
> ROADMAP/BOT-034 — US-04 bị hoãn có chủ đích ra khỏi `BOT-034` vì lớn hơn 3 story còn lại cộng lại).

## 9. Đã build gì thực tế (khác skeleton ở §4 chỗ nào, và tại sao)

**`ChartCard.prepend_historical_data()`/`prepend_historical_volume()`** — tách thành **2 method**
riêng (không gộp 1 method như skeleton ở §4.1 đề xuất), vì code thật đã có sẵn
`render_historical_data()`/`render_historical_volume()` là 2 method riêng (candle và volume KHÔNG
bao giờ đi chung 1 lệnh — `_on_history_reloaded` gọi cả 2 tuần tự) — giữ đúng cấu trúc song song đó
thay vì phát minh 1 API mới trộn 2 việc. `VolumeItem.as_tuples()` (không phải `_as_tuples()` như
skeleton gọi tạm) — public, vì `ChartCard`/tests cần gọi từ ngoài.

**`prepend_historical_data()` không tự windowed lại volume** — chỉ gọi `_sync_indicator_window()`
(indicator curves); `prepend_historical_volume()` tự gọi `volume.refresh_window()` riêng — theo
đúng nguyên tắc "mỗi method chỉ lo phần dữ liệu của chính nó", giống `render_historical_data`/
`render_historical_volume` không đụng vào nhau.

**`EdgeScrollDetector`** — file riêng trong `components/chart_card/` (không phải nhét vào
`ViewportController` — quyết định lúc code, đúng như skeleton cho phép tự chọn). Nhận
`get_raw_history: Callable[[], list[OhlcCandle]]` thay vì 2 callback riêng (oldest_timestamp +
bar_width) — tự tính cả 2 từ `history[0]`/`history[1]`, ít tham số hơn, ChartCard chỉ cần truyền 1
lambda `lambda: self._raw_history`. Ngưỡng mặc định 20 bar đọc thẳng từ code, không qua config (US-04
không yêu cầu user chỉnh được ngưỡng này, khác `CHART_CARD_MIN_FETCH_CANDLES`/
`DEV_BOARD_AUTOSTART_FALLBACK_SECONDS` — 2 cái đó CẦN chỉnh được từ test, cái này thì không).

**`ChartCard.sig_near_left_edge = Signal(str)`** — mang `self.symbol`, KHÔNG phải
`EdgeScrollDetector` tự emit trực tiếp ra ngoài (nó chỉ có `Signal()` không tham số, không biết
symbol của card nào) — `ChartCard` relay: `edge_scroll_detector.sig_near_left_edge.connect(lambda:
self.sig_near_left_edge.emit(self.symbol))`. Giữ `EdgeScrollDetector` không biết gì về "symbol"
(reusable, test độc lập không cần dàn dựng cả `ChartCard`).

**`HistoryPaginationController`** — khớp gần như 100% với skeleton, không đổi gì đáng kể. Follow-up
sau khi lên app thật: chỉ có in-flight guard là không đủ — 1 lần scroll/kéo liên tục hay 1 cú lướt
trackpad quán tính bắn ra rất nhiều `sigRangeChangedManually` rời rạc, hễ fetch trước xong là fetch
kế tiếp bắn ngay (log "Loaded N older klines" lặp ~1 giây/lần trong lúc user còn đang cuộn). Thêm
`cooldown_seconds` (mặc định 1.5s, `time.monotonic()`, tính riêng theo từng symbol) — gộp cả chùm
sự kiện gần rìa thành đúng 1 fetch/cửa sổ thay vì 1 fetch/sự kiện.

**Đổi tên config key + thêm key mới** (theo yêu cầu user, sau khi lên app thật): `75` ở quyết định
§2.1 #2 ban đầu là hardcode (`_LOAD_MORE_BATCH_CANDLES` const), giờ đọc từ config key
`CHART_CARD_LOAD_MORE_BATCH_CANDLES` (default vẫn `75`, KHÔNG đổi hành vi mặc định, vẫn KHÔNG đồng
bộ theo `_compute_fetch_limit()` — quyết định gốc không đổi, chỉ thêm chỗ cho user chỉnh). Đồng thời
key floor của Load History (`DEV_BOARD_MIN_FETCH_CANDLES`, từ `BOT-034`) đổi tên thành
`CHART_CARD_MIN_FETCH_CANDLES` — lý do: cả 2 key đều là hành vi fetch của `ChartCard`/`ChartCard`
component, không đặc thù riêng cho màn Dev Board (khác `DEV_BOARD_AUTOSTART_FALLBACK_SECONDS`, cái
đó thật sự là hành vi riêng của luồng auto-start trên Dev Board nên giữ nguyên tên). Giá trị người
dùng đã set thủ công (`2000`) được giữ nguyên qua rename, không reset về default.

**`_raw_klines_by_symbol: dict[str, list[MarketData]]`** — cái DUY NHẤT skeleton ở §4.4 đánh giá
SAI: viết "`feed_all(candles_cũ + candles_đang_có)`" như thể presenter sẵn có cả 2 phần dưới dạng
`MarketData` — **thực tế không phải vậy**. `ChartCard._raw_history` chỉ giữ tuple đã map
`(t,o,h,l,c)` cho MỤC ĐÍCH VẼ CHART, không đủ để feed lại `IndicatorScriptRunner` (cần `MarketData`
đầy đủ). Phải thêm cache riêng `self._raw_klines_by_symbol`, ghi đè (không append) mỗi lần
`_run_load_history`/`_run_sync_and_start` chạy (interval đổi thì cache cũ tự bị thay), VÀ **phải
cập nhật thêm trong `_on_ui_chart_update`'s tick-đóng-nến branch** (nến live-tick — nếu không, sau
1 lần rebuild do load-more, các nến đến từ live stream kể từ lần Load History/Start Live gần nhất
sẽ biến mất khỏi mọi script cho tới khi có tick mới). Đây là phần tốn nhiều suy nghĩ nhất trong
toàn bộ task — không có trong skeleton ban đầu vì lúc viết task chưa xét tới trường hợp "vừa đang
Live vừa load-more".

**Bộ lọc trùng dữ liệu** — dùng `close_time` (không phải `open_time`) để so sánh, vì
`_map_klines`/`_map_volume` (code thật) build timestamp của chart từ `close_time`, không phải
`open_time` như suy đoán ban đầu trong §2.1. Lọc client-side sau khi fetch
(`k.close_time.timestamp() < before_timestamp`), không dựa vào riêng `end_time` filter của
repository (inclusive `<=`, sẽ trả lại đúng nến biên đã có).

**Test**: 4 unit (ChartCard) + 3 unit (EdgeScrollDetector) + 5 unit (HistoryPaginationController) +
11 unit (DashboardPresenter) + 4 integration = 27 test mới, tất cả pass. Suite tổng: 419 unit + 33
integration.

## 1. Mục tiêu (Objective)

Hôm nay: Load History luôn tải đúng 1 lần theo `_compute_fetch_limit()` (BOT-034 §4), chart hiển
thị đúng batch đó, không có gì xảy ra khi user kéo/scroll ra ngoài rìa trái (chỗ hết dữ liệu) —
chart chỉ đơn giản trống. Mục tiêu: khi user kéo tới gần rìa trái của dữ liệu đã tải, tự động tải
thêm 1 batch nến cũ hơn và nối vào đầu chart, **không phá vỡ vị trí zoom/pan hiện tại của user**,
**không tạo dữ liệu trùng**, và **các indicator script đang chạy vẫn tiếp tục hoạt động đúng**.

## 2. Hiện trạng đã verify (không phải suy đoán — đọc code trực tiếp trước khi viết file này)

### 2.1. Tầng Query/Repository — ĐÃ SẴN SÀNG, không cần sửa gì

`GetHistoricalKlinesQuery` (`src/application/use_cases/queries/get_historical_klines/query.py`):
```python
@dataclass(frozen=True)
class GetHistoricalKlinesQuery:
    symbol: str
    interval: str
    limit: int = 1000
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    order_by_desc: bool = False
```
`handler.py` truyền thẳng cả 6 field vào `IMarketDataRepository.get_klines(...)`;
`SqlAlchemyMarketDataRepository.get_klines` đã filter `KlineModel.open_time <= end_time` khi có
`end_time`. Nghĩa là **"tải N nến cũ hơn nến cũ nhất đang có" đã làm được ngay hôm nay**, không cần
sửa query/handler/repository:
```python
GetHistoricalKlinesQuery(
    symbol=symbol, interval=interval_str, limit=75,
    end_time=<open_time của nến cũ nhất đang render>, order_by_desc=True,
)
```
— **giống hệt pattern `_run_load_history` đã dùng cho lần tải đầu tiên** (desc rồi reverse), chỉ
khác tham số `end_time`.

### 2.2. `ChartCard` (`src/presentation/ui/components/chart_card/chart_card.py`) — cần thêm 1 method mới

- `_raw_history: list[OhlcCandle]` với `OhlcCandle = tuple[float, float, float, float, float]` =
  `(timestamp, open, high, low, close)`, sắp xếp tăng dần theo timestamp.
- `render_historical_data(self, data: list[OhlcCandle]) -> None` (dòng 97) — **thay toàn bộ**:
  ```python
  def render_historical_data(self, data: list[OhlcCandle]) -> None:
      self._raw_history = list(data)
      self._live_candle = None
      if self.chart_type_renderer.chart_type == CANDLESTICK:
          self.candlestick.generate_picture(self._raw_history)
      else:
          self._render_chart_type()
      self._set_initial_view_range(data)          # ⚠️ reset zoom về mặc định
      if data:
          last_t, open_p, _, _, close_p = data[-1]
          self.price_line.update_price(close_p, close_p >= open_p)
          self.viewport.notify_new_data(last_t)   # ⚠️ auto-follow về nến MỚI NHẤT
  ```
  **Không dùng được thẳng cho "load more"** — cả `_set_initial_view_range` (reset zoom) và
  `viewport.notify_new_data` (nhảy về nến mới nhất) đều SAI ngữ cảnh khi ta đang PREPEND dữ liệu
  CŨ trong lúc user đang nhìn đúng chỗ đó (không phải nến mới nhất).
- Volume tương tự: `VolumeItem.render_historical(self, data: list[tuple[float, float, bool]])`
  (`volume_renderer.py`) — cũng thay toàn bộ `_timestamps/_heights/_colors` rồi `_apply()`.
- **Chưa có method nào prepend vào đầu `_raw_history`** — cần viết mới.

### 2.3. `ViewportController` — chưa có hook "gần hết dữ liệu bên trái"

Đã grep toàn bộ package `chart_card/` — chỉ có 2 signal liên quan tới range:
`plot.vb.sigRangeChangedManually` (bất kỳ pan/zoom nào, `ViewportController._on_user_panned` dùng
để tắt auto-follow) và `plot.vb.sigXRangeChanged` (bất kỳ range change nào, `ChartCard` dùng để
re-window volume/indicator). **Không có signal nào báo "user đã kéo tới gần rìa trái dữ liệu đã
tải"** — phải tự thêm.

### 2.4. `IndicatorScriptRunner`/`BaseIndicatorScript` — KHÔNG có đường "feed lùi"

`BaseIndicatorScript` (`domain/indicator_scripts/base_indicator_script.py`) chỉ có
`compute(self, candle) -> Mapping[str, PlottedLine]`, **không có `reset()`**.
`IndicatorScriptRunner.rebuild()` (`screens/dashboard/indicator_script_runner.py`) luôn tạo instance
MỚI vì lý do này (đã ghi rõ trong docstring: "indicators carry warm-up state and have no reset()").
`feed()`/`feed_all()` chỉ APPEND về phía sau (`ActiveScript.record()` luôn `.append()`).

**Hệ quả bắt buộc phải chấp nhận**: nếu prepend nến cũ vào 1 script ĐàNG chạy (đã warm-up), state
nội bộ (vd. EMA trung bình trượt) sẽ SAI vì tính thiếu các nến cũ hơn từ đầu. **Cách duy nhất đúng
hôm nay**: sau khi prepend, gọi lại `_script_runner.rebuild(enabled_keys)` +
`feed_all(nến_cũ + nến_đang_có)` — tức là **chạy lại toàn bộ script từ đầu trên toàn bộ dữ liệu đã
tải (cũ hơn cộng dồn)**, không phải "feed thêm phần mới". Tốn hơn 1 lần tải ban đầu (nhiều nến hơn),
nhưng đúng — không có cách rẻ hơn với kiến trúc hiện tại.

⚠️ **AC gốc của US-04** ghi "indicator state được giữ nguyên" — hiểu đúng nghĩa: **user KHÔNG thấy
indicator biến mất/reset trên màn hình** (curve vẫn liền mạch, giá trị đúng), KHÔNG phải nghĩa đen
"giữ nguyên object Python cũ". Full rebuild+refeed đạt đúng mục tiêu observable này.

### 2.5. `CancellationToken` — dùng lại đúng pattern BOT-034 đã lập

`self._cancellation_token: CancellationToken` (khởi tạo 1 lần ở `__init__`, cancel+phát mới ở
`_on_stop_stream`) — task nền mới PHẢI nhận token này làm tham số cuối, check
`token.is_cancelled()` trước khi chạm vào chart, giống hệt `_run_load_history`.

## 3. RULES — bắt buộc tuân thủ

| # | Rule |
|---|---|
| R1 | `domain/` không import PySide6/pyqtgraph/sagittarius_engine. |
| R4 | Worker nền chỉ `.emit()` Qt signal — mutation ViewModel/ChartCard luôn ở `@Slot` main thread. |
| R8 | 1 concern = 1 file (xem §5 — trigger detection, fetch orchestration, chart prepend là 3 file khác nhau). |
| R9 | Dùng `../.venv/Scripts/python.exe`, KHÔNG dùng `python` trần. |
| R10 | KHÔNG cancel task nền khi user đổi tab/navigate away (theo đúng quyết định đã chốt ở `BOT-034` §5) — chỉ cancel khi user bấm Stop hoặc app/test thoát, dùng lại `CancellationToken` có sẵn trên presenter, không tạo cơ chế cancel mới. |
| R11 | Không sửa `render_historical_data`/`_set_initial_view_range` hiện có — chúng đúng cho lần tải ĐẦU TIÊN, viết method MỚI riêng cho prepend thay vì nhét thêm `if` vào chỗ cũ. |

## 4. Kiến trúc đề xuất (skeleton — khung sườn, không phải implementation đầy đủ)

### 4.1. `ChartCard.prepend_historical_data()` — file `chart_card.py`, thêm method mới

```python
def prepend_historical_data(
    self, candles: list[OhlcCandle], volume: list[tuple[float, float, bool]]
) -> None:
    """
    @brief Nối thêm nến CŨ HƠN vào đầu dữ liệu đang có — không phá vỡ zoom/pan hiện tại
    của user, khác hẳn render_historical_data() (dùng cho lần tải đầu, luôn reset view).
    @param candles Oldest-first, PHẢI toàn bộ có timestamp < self._raw_history[0][0] (caller
    chịu trách nhiệm lọc trùng trước khi gọi — xem HistoryPaginationController).
    """
    if not candles or not self._raw_history:
        return
    self._raw_history = candles + self._raw_history
    if self.chart_type_renderer.chart_type == CANDLESTICK:
        self.candlestick.generate_picture(self._raw_history)
    else:
        self._render_chart_type()
    self.volume.render_historical(volume + self.volume._as_tuples())  # xem ghi chú dưới
    # KHÔNG gọi _set_initial_view_range / viewport.notify_new_data — xem §2.2.
```
⚠️ `VolumeItem` hiện không có method "lấy lại toàn bộ dữ liệu đang có dưới dạng tuple" — cần thêm 1
property/method nhỏ trên `VolumeItem` (hoặc đơn giản hơn: `DashboardPresenter`/
`HistoryPaginationController` tự giữ song song danh sách volume tương ứng với `_raw_history`, không
cần hỏi ngược `VolumeItem`). Quyết định cách nào đơn giản hơn khi code — không phải quyết định
UX, để tự chọn.

### 4.2. Trigger detection — file MỚI `screens/dashboard/../components/chart_card/edge_scroll_detector.py` (hoặc method nhỏ ngay trong `ViewportController` nếu đủ ngắn — tự quyết định lúc code, không phải quyết định kiến trúc lớn)

Theo dõi `plot.vb.sigRangeChangedManually` (đã có), so `x_min` của range mới với
`self._raw_history[0][0]` (timestamp nến cũ nhất). Nếu `x_min` cách rìa trái ít hơn N nến (ngưỡng —
xem §2.1 câu hỏi mở), emit 1 signal mới, vd. `ChartCard.sig_near_left_edge = Signal()`.
**Phải debounce/throttle** — user kéo liên tục sẽ bắn signal này rất nhiều lần trong lúc 1 lần tải
trước đó còn đang chạy; xem `HistoryPaginationController` bên dưới để biết ai chịu trách nhiệm
chặn trùng (không nên chặn ở tầng detection — tách đúng trách nhiệm, detection chỉ "báo", không
"quyết định có nên tải hay không").

### 4.3. `HistoryPaginationController` — file MỚI `screens/dashboard/history_pagination_controller.py`

Theo đúng pattern `AutoStartController` (BOT-034 §5) — 1 collaborator riêng, không nhét thêm method
vào `DashboardPresenter` (đã khá lớn):
```python
class HistoryPaginationController(QObject):
    """
    @brief Khi ChartCard báo user kéo gần hết dữ liệu bên trái, tải thêm 1 batch nến cũ hơn
    và nối vào chart — không chặn UI, không tải chồng khi 1 lần tải trước còn đang chạy.
    """
    def __init__(
        self,
        fetch_older: Callable[[str, float], None],  # presenter method, xem §4.4
        parent: QObject | None = None,
    ) -> None: ...

    def on_near_left_edge(self, symbol: str, oldest_timestamp: float) -> None:
        """Nối với ChartCard.sig_near_left_edge. No-op nếu đã có 1 lần tải đang chạy
        cho đúng symbol này (self._in_flight: set[str])."""

    def on_load_more_finished(self, symbol: str) -> None:
        """Gọi từ presenter sau khi prepend xong — mở khoá lại cho symbol đó."""
```

### 4.4. `DashboardPresenter` — method nền mới, theo đúng convention `_run_load_history`

```python
def _run_load_more_history(
    self, symbol: str, interval_str: str, before_timestamp: float, limit: int,
    token: CancellationToken,
) -> None:
    """Nền: GetHistoricalKlinesQuery(end_time=<before_timestamp>, order_by_desc=True, limit=limit),
    reverse, emit ui_history_prepended_signal(symbol, mapped_data, volume_data) — signal MỚI,
    KHÔNG tái dùng ui_history_reloaded_signal (semantics khác: "prepend" chứ không phải "replace")."""
```
`_on_history_prepended` (main-thread `@Slot`): gọi `card.prepend_historical_data(...)`, rồi
`self._rebuild_scripts()` + `self._script_runner.feed_all(candles_cũ + candles_đang_có)` (xem §2.4
— toàn bộ, không phải chỉ phần mới), rồi báo `HistoryPaginationController.on_load_more_finished`.

## 5. Chia file cho song song (R8)

| File | Việc |
|---|---|
| `chart_card.py` | `prepend_historical_data()` |
| `volume_renderer.py` | method/property hỗ trợ lấy lại data hiện có (nếu chọn hướng đó ở §4.1) |
| `viewport_controller.py` hoặc file mới `edge_scroll_detector.py` | detect gần rìa trái, emit signal |
| `history_pagination_controller.py` (MỚI) | orchestration, chặn tải chồng |
| `dashboard_presenter.py` | `_run_load_more_history`, `_on_history_prepended`, wiring `HistoryPaginationController` ở `__init__` (giống `AutoStartController`) |

## 2.1. Quyết định (user chốt: dùng đúng 3 đề xuất ban đầu, code luôn — không hỏi lại)

| # | Câu hỏi | Quyết định |
|---|---|---|
| 1 | Ngưỡng "gần rìa trái" | **20 nến** còn lại tính từ rìa trái thì trigger. |
| 2 | Số nến tải mỗi lần | **Cố định 75** (đúng nghĩa đen AC, không đồng bộ theo `_compute_fetch_limit()`). |
| 3 | DB thiếu dữ liệu cũ hơn | **Phase 1: KHÔNG tự sync** — chỉ hiển thị bấy nhiêu nến tìm được (có thể 0) + log "No older data found". Sync-from-Binance để Phase 2, task riêng. |

## 6. Test gate

- Unit: `HistoryPaginationController` — no-op khi đã có 1 lần tải đang chạy cho symbol đó; gọi
  đúng `fetch_older` với `before_timestamp` = timestamp nến cũ nhất; mở khoá lại sau
  `on_load_more_finished`.
- Unit: `ChartCard.prepend_historical_data` — `_raw_history` được nối đúng thứ tự (cũ trước, không
  duplicate), không gọi `_set_initial_view_range`/`viewport.notify_new_data`.
- Integration: kéo chart gần rìa trái (giả lập bằng gọi thẳng `sig_near_left_edge.emit()`, không
  cần drag chuột thật) → xác nhận `_raw_history` tăng đúng số nến, `_script_runner.active` vẫn còn
  đúng các key đang bật (không bị rớt do rebuild).
- Integration: kéo gần rìa trái 2 lần liên tiếp trước khi lần đầu kịp xong → chỉ đúng 1 lần
  `GetHistoricalKlinesQuery` được dispatch cho symbol đó (không tải chồng).

**Kết quả**: 4 file mới + 5 file sửa, 27 test mới (4 ChartCard + 3 EdgeScrollDetector + 5
HistoryPaginationController + 11 DashboardPresenter unit, + 4 integration), tất cả pass. Suite
tổng: 419 unit + 33 integration (đếm file, không chạy hết 1 lượt được — xem cảnh báo dưới).

⚠️ **Known issue — KHÔNG phải do BOT-035, đã verify bằng bisection**: chạy TOÀN BỘ
`tests/integration/presentation/ui/` trong 1 lần (`pytest tests/integration/presentation/ui/`)
có xác suất cao bị crash (Windows access violation thật, không phải hang) sau khoảng **~26 lượt
test/fixture cycle** tích luỹ trong CÙNG 1 process — không liên quan tới nội dung cụ thể của các
test đó. Đã verify: tái hiện GIỐNG HỆT (dừng ở đúng vị trí tương đối) khi chạy 26 test bất kỳ dẫn
tới `test_sanity_dev_board_full_feature_walkthrough`, **có và không có** 4 test mới của BOT-035 —
tức là lỗi này đã tồn tại từ trước BOT-035, chỉ là chưa ai chạy đủ số lượng test liên tiếp để chạm
ngưỡng. Crash trace cho thấy: 1 background thread đang giữa chừng khởi tạo `unittest.mock.MagicMock()`
(bên trong `mock_dispatch` closure của `conftest.py`) đúng lúc main thread đang chạy 1 chu kỳ
garbage-collection — khớp với cùng 1 lớp lỗi (PySide6/shiboken C++ object lifetime không được bảo
vệ đủ khi nhiều background thread + nhiều chu kỳ tạo/huỷ QWidget cộng dồn trong 1 process test dài)
đã gặp và sửa một phần ở `BOT-034` §9 (đã sửa 3 nguyên nhân riêng biệt lúc đó — đây là biến thể thứ
4, cần điều tra riêng, không chặn việc merge BOT-035). **Chạy theo từng file/nhóm nhỏ hơn (như CI
hiện tại đang làm qua nhiều job, hoặc `pytest <file1> <file2> ...` từng phần) không gặp vấn đề này**
— chỉ xảy ra khi dồn TẤT CẢ 33 test integration UI vào 1 lệnh `pytest` duy nhất.

## 7. Phụ thuộc (Dependencies)

- `BOT-034` ✅ (toàn bộ) — `_compute_fetch_limit`, `CancellationToken` pattern, `AutoStartController`
  làm khuôn cho `HistoryPaginationController`.
- Không phụ thuộc `BOT-033` (task song song) — không đụng tới Symbol/Date range/Market/Strategy.
