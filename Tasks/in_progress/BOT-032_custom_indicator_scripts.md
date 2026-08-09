# Nhiệm vụ: Custom Indicator Scripts (kiểu Pine Script, thuần Python)

> **Đọc file này trước khi code.** Phase 0-5 đã xong và đã chốt kiến trúc — đừng thiết kế
> lại, hãy extend theo đúng khuôn đã có. Mục §3 (RULES) là bắt buộc. **Phase 6 (§9) đã được
> chốt làm** (đảo ngược quyết định "để sau" ban đầu — xem lý do đầu mục §9) — đây là phần việc
> còn lại duy nhất của task này, và là phần lớn/rủi ro nhất (xoá code hardcode đang chạy tốt).

## 1. Mục tiêu (Objective)
Cho phép **tự viết indicator** bằng 1 class Python thường — cảm giác giống TradingView Pine
Script (`study()`/`plot()`/`plotshape()`/`a[1]`) nhưng **không tạo DSL mới**. Mục tiêu cuối là
custom indicator **và** custom strategy; task này **chỉ làm indicator**, thiết kế để ngỏ cho
strategy.

## 2. User story gốc (nguyên văn ý người dùng)
1. Viết indicator như 1 class: khai báo building block (`ema(12)`...), rồi `plot()` từng đường
   với màu — không cần học Pine Script.
2. **Phải kiểm tra được: các indicator cắt nhau, cắt giá, trên/dưới nhau.**
3. Ví dụ thật người dùng đưa (Pine, HMA cross):
   ```pine
   a = hma(src, length)
   b = hma3(src, length)
   c = b > a ? color.lime : color.red        // màu đổi theo từng bar
   p1 = plot(a, color=c) ; p2 = plot(b, color=c)
   fill(p1, p2, color=c)                      // tô giữa 2 đường
   crossdn = a > b and a[1] < b[1]            // cần lịch sử bar trước
   plotshape(crossup ? a : na, style=shape.labelup, text="Buy", ...)
   ```
4. **Không tự động vẽ marker** — chỉ vẽ khi script yêu cầu.
5. "Làm indicator trước nhưng design mở cho strategy."

## 3. RULES — bắt buộc tuân thủ

| # | Rule | Lý do |
|---|---|---|
| R1 | `domain/` **không** import `PySide6`, `pyqtgraph`, `sagittarius_engine`. Màu là `str` hex, không phải `QColor`. | Script phải dùng được từ CLI/backtest, không chỉ desktop UI. **Có guard test enforce.** |
| R2 | Script **không** giữ tham chiếu tới chart/widget/IO. `plot()`/`mark()` chỉ ghi buffer; `compute()` drain ra. | Giữ script pure → test bằng gọi hàm đọc kết quả, và batch/live không thể lệch nhau. |
| R3 | Đăng ký script **tường minh** trong `binance_bot_module.py::register()`. **Không auto-scan thư mục.** | Greppable, review được. **Guard test bắt** nếu tạo script mà quên register. |
| R4 | Worker nền **chỉ** `.emit()` Qt signal. Mọi mutation ViewModel/model nằm trong `@Slot` main thread. | Hợp đồng threading toàn app, không được phá. |
| R5 | Thêm indicator toán học mới → đặt trong `domain/indicators/`, implement `IIndicator`. **Không** viết lại toán trong script. | Script chỉ *compose*, không *implement* indicator. |
| R6 | Đổi lựa chọn script chỉ có tác dụng ở lần Load History/Start Live **kế tiếp** (không hồi tố). | Giữ đúng hợp đồng RSI/EMA/MACD hiện có (TC-GAP-07). |
| R7 | Tên curve trên chart phải namespace: `f"{script_key}:{line_name}"`. | Tránh đụng tên với RSI/EMA/MACD cũ (tên trần) và giữa 2 script với nhau. |
| R8 | **1 concern = 1 file.** Thêm việc mới vào 1 class đang lớn (Presenter/ViewModel) thì **tách collaborator ra file riêng** rồi delegate, đừng nối thêm method. | SRP + **nhiều task AI chạy song song không đụng cùng file**. Đã áp dụng: script logic nằm ở `indicator_script_runner.py`, presenter chỉ gọi. |
| R9 | **Dùng `../.venv/Scripts/python.exe`**, KHÔNG dùng `python` trần. | `python` trần trên máy này là interpreter khác, ruff 0.16.1, báo ~305 lỗi ảo trên code vốn sạch. Venv có ruff 0.15.20 = đúng cái CI dùng. **Tôi đã dính bẫy này.** |

## 4. Đã xong — API hiện có (ĐỪNG thiết kế lại)

### `domain/scripting/series.py` — primitive dùng chung cho cả indicator lẫn strategy
```python
class Series:                       # index kiểu Pine: [0]=bar này, [1]=bar trước
    push(value: float | None) -> float | None
    __getitem__(offset: int) -> float | None   # quá lịch sử -> None (không raise)
    current / previous
DEFAULT_HISTORY = 16                # ring buffer, KHÔNG lưu vô hạn như Pine

crossed_above(a, b) -> bool         # = a > b and a[1] < b[1]; warmup -> False
crossed_below(a, b) -> bool
crossed(a, b) -> bool
is_above(a, b) / is_below(a, b)     # None-safe, dùng bar hiện tại
constant_series(value) -> Series    # để cắt mức hằng (RSI 70)
series_of(values) -> Series         # test helper, oldest-first

class Streak:                       # đếm số bar liên tiếp 1 điều kiện đúng
    update(condition: bool) -> int  # False -> reset về 0, True -> +1, trả count mới
    .current -> int
```
Đặt ở `domain/scripting/` (không phải `indicator_scripts/`) **có chủ đích**: golden cross
chính là trigger mua → `BaseStrategyScript` sau này dùng lại nguyên si, không phải move file.

### `domain/indicator_scripts/base_indicator_script.py`
```python
@dataclass(frozen=True)
class PlottedLine:  value: float; color: str          # màu THEO TỪNG BAR
@dataclass(frozen=True)
class PlottedMarker: value: float; text: str; color: str; direction: str  # "up"/"down"
@dataclass(frozen=True)
class PlottedRegion: color: str; opacity: float = 0.15   # = Pine bgcolor()
@dataclass(frozen=True)
class InfoField: label: str; value; color: str | None = None  # = Pine table.cell()

class IndicatorHandle(Generic[T]):
    __call__(value) -> T | None      # a1(close) — advance 1 bar
    __getitem__(offset) -> float|None  # a1[1] — bar trước
    .series -> Series
    # LƯU Ý: indicator trả non-float (MACD -> MACDValue) thì [n] = None.
    #        Muốn history của .macd thì tự push vào self.series().

class BaseIndicatorScript(ABC):
    title: str; overlay: bool; history: int = 16      # class attribute
    # Series giá tự cập nhật TRƯỚC mỗi execute():
    self.open / self.high / self.low / self.close / self.volume
    # khai báo trong setup():
    self.ema(p) / self.wma(p) / self.rsi(p) / self.macd(f,s,sig) -> IndicatorHandle
    self.series() -> Series          # cho giá trị tự tính (spread = fast - slow)
    self.level(70.0) -> Series       # mức hằng để cắt
    self.streak() -> Streak          # đếm bar liên tiếp thoả điều kiện
    # so sánh trong execute() — nhận IndicatorHandle HOẶC Series, None-safe:
    self.crossed_above(a, b) / crossed_below / crossed / is_above / is_below
    # output trong execute():
    self.plot(value|None, name, color)                  # None = Pine `na`
    self.mark(value|None, text, color, direction="up")  # = plotshape
    self.shade(color, opacity=0.15)                      # = Pine bgcolor(); không gọi = không tint bar này
    self.info(label, value, color=None)                  # = Pine table.cell(); gọi lại mỗi bar, chỉ bar cuối được hiển thị
    # framework gọi (script author KHÔNG gọi):
    compute(candle) -> Mapping[str, PlottedLine]
    drain_markers() -> list[PlottedMarker]
    drain_region() -> PlottedRegion | None   # None = bar này không tint
    drain_info() -> list[InfoField]
    line_colors() -> Mapping[str, str]
    @abstractmethod setup() / execute(candle)
```

**Instance attribute thường (không cần API riêng)** = Pine's `var`: `self.x = 0` trong
`setup()` rồi mutate trong `execute()` đã đủ để giữ state qua các bar — `dev_indicator_script.py`
kỹ thuật #15 dùng đúng cách này (`self.confirmed_side`, `self.last_direction_up`).

### `application/services/indicator_script_registry.py`
`register(key, cls)` (trùng key → `ValueError`), `create(key, params=None)` (**`params` chừa
sẵn cho Phase 5, hiện ignore — đừng đổi signature**), `available()` (trả copy).

### Script mẫu đã có (dùng làm khuôn)
| key | file | minh hoạ điều gì |
|---|---|---|
| `ema_ribbon` | `ema_ribbon_script.py` | overlay, 4 đường, ví dụ đơn giản nhất |
| `macd_full` | `macd_full_script.py` | `overlay=False` (subplot), tách 1 reading ra 3 đường |
| `ema_cross` | `ema_cross_script.py` | **cross + màu động + marker Buy/Sell** — khuôn cho user story |
| `dev_showcase` | `dev_indicator_script.py` | **REFERENCE — dùng cái này để copy.** Đủ 15 kỹ thuật: khai báo ema/wma/rsi/macd, Series tự tính, level hằng, đọc OHLCV, `[1]`, màu theo bar, `na`, cross indicator×indicator / ×giá / ×hằng số, tách MACDValue, marker có label, **background tint (`shade`), status panel (`info`), streak counter (`streak`)**. Docstring có bảng map sang cú pháp Pine tương ứng. Là showcase, KHÔNG phải study dùng thật — copy kỹ thuật cần rồi xoá phần thừa. |

### Indicator toán học
`domain/indicators/`: `EMA`, `RSI`, `MACD`, **`WMA` (mới thêm ở task này)**.
Helper khai báo tương ứng trong script: `self.ema/wma/rsi/macd`.

### Test đã có (354 test toàn repo pass, không tính `test_market_data.py` — lỗi import có sẵn
### từ trước task này, không liên quan)
`tests/unit/domain/scripting/test_series.py`, `tests/unit/domain/indicator_scripts/*`,
`tests/unit/application/services/test_indicator_script_registry.py`,
`tests/unit/domain/test_indicator_script_conventions.py` (guard R1 + R3).

---

## 5. Phase 2 — Presenter tính + vẽ line lên chart  *(ĐÃ XONG, kể cả background tint + status panel)*

Logic script **không** nằm trong `dashboard_presenter.py` mà ở file riêng
`screens/dashboard/indicator_script_runner.py` (theo R8):

```python
LINE_SEPARATOR = ":"                       # "ema_ribbon:EMA 20"
qualified_line_name(key, line) -> str
split_line_name(qualified) -> tuple|None   # None = curve của indicator built-in

@dataclass ActiveScript: script, overlay, region_tracker, registered_lines: set,
                          series: dict, latest_info: list[InfoField],
                          markers: list[MarkerPoint]   # markers CỘNG DỒN cả run, khác latest_info
    record(line, ts, value) -> (x_data, y_data)   # trả nguyên series tích luỹ

class IndicatorScriptRunner:
    __init__(registry, emit_line, emit_region, emit_info, emit_markers, on_error,
              bar_width_seconds=60.0)          # KHÔNG biết Qt
    rebuild(enabled_keys)          # instance mới mỗi lần (indicator không có reset())
    clear_from_chart(card)         # xoá cả curve, region, info panel, marker của mọi script active
    feed(candle) / feed_all(candles)   # gọi được từ CẢ 2 thread — chỉ emit qua callback
    draw(card, qualified, x, y) -> bool     # False = không phải script line -> caller tự xử lý
    draw_region(card, key, spans)  # không trả bool — region/info/marker không có built-in fallback
    draw_info(card, key, fields)
    draw_markers(card, key, markers)
```

**File mới** `screens/dashboard/script_region_tracker.py` — gộp các bar được `shade()` liên tiếp
cùng màu/opacity thành 1 span thay vì vẽ 1 `LinearRegionItem` mỗi bar (rất tốn):
```python
RegionSpan = tuple[float, float, str, float]     # (start_x, end_x, color, opacity)
class ScriptRegionTracker:
    __init__(bar_width_seconds: float)
    record(timestamp, region: PlottedRegion | None)   # None = bar này không tint -> ngắt span
    .spans -> list[RegionSpan]
    clear()
```

`dashboard_presenter.py` chỉ còn: tạo runner trong `__init__` (nối `emit_line`/`emit_region`/
`emit_info` vào 3 signal `ui_indicator_data_signal`/`ui_script_region_signal`/
`ui_script_info_signal`), `_enabled_script_keys()`, `_rebuild_scripts()`, và gọi
`feed_all`/`feed`/`draw`/`draw_region`/`draw_info` ở đúng chỗ (2 slot mới:
`_on_script_region_data`, `_on_script_info_data`). Runner **không import PySide6** → test được
không cần Qt.

Chart rendering (`components/chart_card/`) — thêm mới, không sửa logic curve có sẵn:
- `plot_layout.py`: `script_info_label` (label thứ 2 ở `row=0, col=1`); `main_plot` và mọi
  `add_subplot()` đổi sang `colspan=2` để cột mới không làm hẹp chart (có test guard riêng).
- `indicator_manager.py`: `set_script_regions(key, spans)` / `clear_script_regions(key)` (vẽ
  `pg.LinearRegionItem`, luôn trên `main_plot` bất kể `overlay` của script sở hữu) và
  `set_script_info(key, fields)` / `clear_script_info(key)` (gộp field của mọi script đang bật
  thành 1 khối HTML trong `script_info_label`).
- `chart_card.py`: 4 method delegate 1 dòng sang `indicators.*`.

Test: `tests/unit/presentation/ui/screens/test_indicator_script_runner.py`,
`tests/unit/presentation/ui/screens/test_script_region_tracker.py`,
`tests/unit/presentation/ui/components/test_chart_card.py` (thêm 12 test region/info + 1 test
guard colspan), + test delegation trong `test_dashboard_presenter.py`.

Verify thật trong app: `tests/integration/presentation/ui/test_dev_board_custom_scripts.py` boot
toàn bộ app qua DI container thật (`main_window`/`navigate` fixture), không chỉ offscreen script
lẻ — xem §9 để biết vì sao chỉ chờ được `ui_script_region_signal` chứ không phải
`ui_indicator_data_signal` khi test với `conftest.MOCK_KLINE_COUNT=5`.

## 6. Phase 3 — UI bật/tắt script  *(ĐÃ XONG)*

**File mới** `screens/dashboard/indicator_script_list_model.py` — `QAbstractListModel`, shape
giống `log_list_model.py`:
```python
class IndicatorScriptListModel(QAbstractListModel):
    KeyRole; TitleRole; EnabledRole
    set_available(scripts: Mapping[str, type[BaseIndicatorScript]])  # đọc .title qua getattr(cls,
        # "title", key) — KHÔNG instantiate script chỉ để liệt kê. Giữ enabled state cho key còn
        # sống, xoá cho key biến mất (không leak enabled_keys sau khi 1 script bị unregister).
    @Slot(int, bool) setEnabled(row, value) -> None   # gọi từ QML, emit dataChanged + enabledKeysChanged
    @property enabled_keys -> list[str]   # thứ tự đăng ký, KHÔNG phải thứ tự bấm
```

`dashboard_view_model.py`: `self._script_model = IndicatorScriptListModel(self)` +
`scriptModel`/`script_model` accessor pair (giống `logModel`/`log_model`).

`dashboard_presenter.py`: `self._view_model.script_model.set_available(script_registry.available())`
gọi 1 lần trong `__init__` (ViewModel không tự resolve container — Presenter vẫn là nơi duy nhất
chạm DI). `_enabled_script_keys()` đổi 1 dòng: trả `self._view_model.script_model.enabled_keys`.

`DevBoardPanel.qml` — thêm vào card INDICATORS, sau checkbox MACD:
```qml
SectionLabel { text: "CUSTOM SCRIPTS"; visible: scriptRepeater.count > 0 }
Repeater {
    id: scriptRepeater
    model: viewModel.scriptModel
    RowLayout {
        Layout.fillWidth: true
        required property var model
        required property int index
        StyledCheck {
            // ⚠️ KHÔNG dùng `model`/`index` trần bên trong StyledCheck — nó
            // resolve theo scope CỦA STYLEDCHECK (không có), không phải của
            // RowLayout cha. Phải qua `parent.model`/`parent.index` vì
            // StyledCheck là CON của RowLayout (Repeater's delegate root).
            objectName: "chkScript_" + parent.model.key
            text: parent.model.title
            checked: parent.model.enabled
            onToggled: viewModel.scriptModel.setEnabled(parent.index, checked)
        }
        Item { Layout.fillWidth: true }
    }
}
```
Khác Repeater ở `DatabaseScreen.qml` (array JS **tĩnh**) đúng như dự tính — danh sách này đến từ
`IndicatorScriptRegistry.available()` lúc runtime, thêm 1 script mới vào `binance_bot_module.py`
là tự hiện trong UI, không cần sửa QML.

⚠️ **Cạm bẫy đã dính khi verify**: `CheckBox.toggle()` (gọi từ Python qua
`QMetaObject.invokeMethod`) chỉ đổi `checked`, **KHÔNG emit `toggled()`** — signal đó chỉ bắn khi
người dùng bấm thật (chuột/phím). Test tích hợp vì vậy set thẳng qua ViewModel
(`view._view_model.script_model.setEnabled(row, True)`), đúng y hệt cách
`test_dev_board_indicators.py` set `view._view_model.rsiEnabled = True` thay vì giả lập click —
repo này **chưa có tiền lệ** test click chuột lên 1 QML control (chỉ có `qtbot.mouseClick` cho
QtWidgets button thật ở `test_dev_board_known_gaps.py`), nên không tự bịa cách mới ở đây.

**Test gate đã chạy** (không phải "click qua `qml_item`" như dự tính ban đầu — xem cạm bẫy trên):
- `tests/unit/presentation/ui/screens/test_indicator_script_list_model.py` (10 test, thuần Python).
- `tests/integration/presentation/ui/test_dev_board_custom_scripts.py` (3 test, boot app thật):
  Repeater render đúng 1 checkbox/script với đúng `text`/`objectName` (đọc qua
  `qml_item`/`walk_qml_items` — delegate của Repeater **không phải** QObject child, `findChild()`
  luôn trả `None`); bật script qua ViewModel rồi Load History → script chạy thật
  (`presenter._script_runner.active`); tắt lại → dừng ở lần Load kế tiếp (TC-GAP-07 parity).
- Screenshot offscreen xác nhận checklist render đúng vị trí (dưới MACD, trong cùng card
  INDICATORS, cùng style checkbox).

---

## 7. Phase 4 — Chart nâng cao: marker / màu động / fill  *(1 trong 3 mục CHƯA LÀM)*

Domain đã sinh đủ dữ liệu (`PlottedMarker`, `PlottedLine.color` theo từng bar, `PlottedRegion`,
`InfoField`) nhưng chart chưa vẽ hết. `PlottedRegion`/`InfoField` **đã xong** (xem §5) — bảng
dưới đây chỉ còn marker + màu động + fill.

| Cần | Hiện trạng | Gợi ý |
|---|---|---|
| **Background tint** (`bgcolor`) | ✅ **XONG** — `set_script_regions`/`ScriptRegionTracker`, xem §5. | — |
| **Status panel** (`table.cell`) | ✅ **XONG** — `set_script_info`/`script_info_label`, xem §5. | — |
| **Marker Buy/Sell có label** (`plotshape`) | ✅ **XONG** — `MarkerLayer` (file mới) + `set_script_markers`/`clear_script_markers`, xem §5b. | — |
| **Màu đổi theo bar** (`c = b > a ? lime : red`) | ❌ **CHỦ ĐỘNG KHÔNG LÀM trong task này** — xem lý do bên dưới. | pyqtgraph không đổi màu giữa chừng 1 curve; cần tách thành nhiều `PlotDataItem` segment mỗi khi màu đổi, tái viết `IndicatorManager._apply_window`/`refresh_window`/legend — code **dùng chung với RSI/EMA/MACD**, rủi ro cao nếu làm vội. Domain đã sẵn sàng (`PlottedLine.color` đổi mỗi bar, `dev_showcase`/`ema_cross` kỹ thuật #6 đã minh hoạ) — chỉ còn phần render. Đề xuất tách task riêng, có review kỹ trước khi đụng `IndicatorManager`. |
| **`fill(p1, p2)`** | ❌ **CHỦ ĐỘNG KHÔNG LÀM** — ưu tiên thấp nhất, `pg.FillBetweenItem`, làm sau cùng nếu cần. | — |

**Quyết định đã chốt** (không hỏi lại — 2 mục trên rủi ro cao / giá trị thấp so với công sức, xem
lý do ở bảng): chỉ làm marker trong task này. Nếu cần màu-động-theo-bar hoặc fill, tách task
riêng để review kiến trúc `IndicatorManager` trước khi đụng vào (ảnh hưởng cả RSI/EMA/MACD).

### 7b. Marker — chi tiết đã làm

**File mới** `components/chart_card/marker_layer.py`:
```python
MarkerPoint = tuple[float, float, str, str, str]   # (x, y, text, color, direction)
class MarkerLayer:
    __init__(plot: pg.PlotItem)      # LUÔN main_plot — cùng lý do region luôn vẽ trên main_plot
    set_markers(key, markers: list[MarkerPoint])   # full teardown/rebuild, không incremental
    clear(key)
    clear_all()
```
`IndicatorManager.set_script_markers(key, markers)` / `clear_script_markers(key)` delegate sang
`MarkerLayer`; `ChartCard` có 2 method delegate 1 dòng tương ứng.

`IndicatorScriptRunner`: `ActiveScript.markers: list[MarkerPoint]` **cộng dồn cả run** (khác
`latest_info` — chỉ giữ bar gần nhất), vì marker là sự kiện lịch sử phải ở lại đúng bar đã xảy ra.
`__init__` nhận thêm `emit_markers: Callable[[str, list[MarkerPoint]], None]`. `feed()` chỉ gọi
`emit_markers` khi bar đó **có** marker mới (không re-emit list không đổi mỗi bar, khác region/info
luôn emit mỗi bar). `draw_markers(card, key, markers)` — không trả bool, giống `draw_region`/`draw_info`.
`clear_from_chart()` gọi thêm `card.clear_script_markers(key)`.

`dashboard_presenter.py`: thêm `ui_script_marker_signal = Signal(str, list)`, nối
`emit_markers=self.ui_script_marker_signal.emit`, slot `_on_script_marker_data`.

---

## 8. Phase 5 — Docs + full CI  *(ĐÃ XONG)*
- `Docs/Diagrams/ui_architecture.md` §11 (mới): cách viết 1 script mới (3 bước: tạo file →
  `register()` → tự hiện trong UI), bảng map output primitive → chart result, mermaid luồng
  `execute() → plot()/mark()/shade()/info() → buffer → compute() → Runner → signal → chart`, và
  phần "để ngỏ cho Strategy" tóm tắt lại §10 của file này cho người đọc chỉ mở doc kiến trúc.
- Full suite qua `../.venv/Scripts/python.exe -m pytest` (không dùng `ci-local.ps1 -Full` trực
  tiếp — coverage gate của nó không liên quan tới việc verify riêng task này): 373 unit test +
  6 sanity test + 44 integration test (43 pass, 1 flaky có sẵn từ trước — xem cảnh báo dưới),
  `ruff check`/`ruff format --check` sạch.
- ⚠️ **1 integration test có sẵn từ trước, KHÔNG liên quan BOT-032, đang flaky trên máy này**:
  `test_dev_board_indicators.py::test_repeated_load_history_does_not_duplicate_indicators` timeout
  chờ `ui_history_reloaded_signal` ở lần Load History thứ 2-3 trong 3 lần bấm liên tiếp. Đã
  **bisect xác nhận** bằng cách checkout code ở commit ngay trước Phase 3 của task này rồi chạy
  lại — vẫn fail y hệt → **không phải regression từ BOT-032**. Nguyên nhân nhiều khả năng: budget
  2000ms cho 3 vòng round-trip qua `ThreadPoolExecutor` thật (test cố tình không mock thread pool
  — xem docstring `conftest.py`) quá sát, và máy chạy nhiều tiến trình Python/Qt liên tục trong
  phiên làm việc này làm chậm lịch thread OS. Không sửa trong task này (ngoài phạm vi BOT-032) —
  nếu gặp lại, thử tăng `timeout=2000` lên cao hơn hoặc chạy riêng lẻ thay vì cả suite.

## 9. Phase 6 — chuyển RSI/EMA/MACD hardcode thành script  *(ĐÃ CHỐT LÀM — quyết định mới, xem dưới)*

> ⚠️ **Đảo ngược quyết định trước đó.** User đã từng chốt "update 3 cái đó sau" (để Phase 6 làm
> sau). Quyết định mới (phiên sau): *"US-07 có nghĩa là bây giờ không có indicator nào là hardcode
> trong engine hết, tất cả phải load từ indicator script."* Tức là Phase 6 **không còn optional**
> — `_ActiveIndicator`/`_build_active_indicators`/RSI/EMA/MACD hardcode trong
> `dashboard_presenter.py` phải bị xoá hẳn, không giữ song song với hệ thống script nữa.

### 9.1. Quyết định kỹ thuật: KHÔNG dùng `params` runtime — dùng nhiều script cố định period

**Blocker cũ**: RSI/EMA hiện có spinbox cho phép gõ period tuỳ ý (2-200) — script hiện tại
zero-arg, muốn giữ spinbox thì cần cơ chế "params" (kiểu Pine `input()`) + render spinbox động
trong QML. Nhưng user **đã chốt trong chính phiên viết BOT-032**: *"khong cần chức năng rutime
input đâu"* (không cần config runtime). Hai quyết định này mâu thuẫn nếu cố giữ spinbox.

**Cách giải quyết** (khớp với chính cách US-07 đề xuất — mỗi period là 1 file riêng, không phải
1 script nhận tham số): bỏ hẳn spinbox, thay bằng **nhiều script cố định period**, mỗi cái tự
đứng — đúng pattern `ema_20/50/100/200` mà `ema_ribbon_script.py` đã minh hoạ (chỉ khác là tách
ra 4 script riêng thay vì 1 script vẽ cả 4 đường, để mỗi cái bật/tắt độc lập được):

| Script mới | Thay thế | File |
|---|---|---|
| `rsi_14` | `RSI(14)` hardcode | `domain/indicator_scripts/rsi_14_script.py` (mới) |
| `ema_20` / `ema_50` / `ema_100` / `ema_200` | `EMA(period)` hardcode với spinbox | 4 file mới, mỗi file 1 EMA — **không phải** tái dùng `ema_ribbon_script.py` (script đó cố tình vẽ cả 4 chung 1 lần, không tách bật/tắt riêng được) |
| `macd_full` | `MACD()` hardcode | **đã có sẵn**, chỉ cần đặt `default_enabled` |

⚠️ **Đánh đổi cần user biết** (không tự quyết âm thầm): sau khi làm Phase 6, RSI/EMA **không còn
gõ được period tuỳ ý (2-200) như trước** — chỉ chọn được trong các period cố định đã đăng ký sẵn.
Muốn thêm period khác (vd. EMA 34) → thêm 1 file script mới, không phải gõ số vào ô input.

### 9.2. `default_enabled` — khái niệm mới cần thêm

Hiện tại **mọi** script đăng ký đều mặc định tắt (`IndicatorScriptListModel._enabled` rỗng lúc
khởi tạo — xem test `test_no_scripts_run_until_the_ui_enables_one`). RSI(14)/EMA(20)/MACD hiện có
sẵn từ trước cho user dùng ngay không cần bật gì — hành vi này **phải giữ nguyên** sau khi
chuyển thành script, nên cần 1 khái niệm mới:

```python
class BaseIndicatorScript(ABC):
    title: str
    overlay: bool
    default_enabled: bool = False   # MỚI — script này tự bật sẵn lần đầu app chạy

class IndicatorScriptListModel(QAbstractListModel):
    def set_available(self, scripts: Mapping[str, type[BaseIndicatorScript]]) -> None:
        # MỚI: key có default_enabled=True VÀ chưa từng bị user đổi trạng thái tay
        # → thêm vào self._enabled ngay lần load đầu.
        ...
```
⚠️ Chỉ áp dụng lúc **lần đầu** danh sách được nạp (app khởi động) — không được ép user bật lại 1
script họ đã chủ động tắt, nếu `set_available()` được gọi lại (vd. registry đổi) giữa chừng.

### 9.3. Xoá — file/chỗ cần dọn trong `dashboard_presenter.py`
`_ActiveIndicator` (dataclass), `_build_active_indicators()`, `_ensure_indicator_registered()`,
`_compute_indicator_series()`, phần RSI/EMA/MACD trong `_update_indicators_on_closed_candle()`,
`_clear_registered_indicators()`, hằng số `_RSI_COLOR`/`_EMA_COLOR`/`_MACD_COLOR`,
`_INDICATOR_KIND_OVERLAY`/`_INDICATOR_KIND_SUBPLOT`, import `EMA`/`MACD`/`RSI` trực tiếp (script
vẫn compose 3 class này bên trong domain, chỉ Presenter không còn gọi thẳng).
`self.active_indicators: dict[str, _ActiveIndicator]` biến mất — mọi thứ đi qua
`self._script_runner` (đã có sẵn từ Phase 2).

### 9.4. Xoá — `dashboard_view_model.py`
`rsiEnabled`/`rsiPeriod`/`emaEnabled`/`emaPeriod`/`macdEnabled` (+ signal `rsiChanged`/
`emaChanged`/`macdChanged`) — toàn bộ đã thay bằng `scriptModel`/`IndicatorScriptListModel` có
sẵn từ Phase 3.

### 9.5. Xoá — `DevBoardPanel.qml`
3 `RowLayout` cho RSI/EMA (checkbox + `PeriodSpin`) và `StyledCheck` MACD trong card INDICATORS —
Repeater "CUSTOM SCRIPTS" (Phase 3) đã đủ để hiển thị mọi script kể cả RSI(14)/EMA(20/50/100/200)/
MACD mới. Có thể đổi tên section từ "CUSTOM SCRIPTS" thành chỉ "INDICATORS" luôn (không còn 2 loại
song song để phân biệt) — cân nhắc lúc làm, không bắt buộc.

### 9.6. Test cần sửa/xoá
`test_dashboard_presenter.py` có nhiều test dựa trên `_build_active_indicators`/`_ActiveIndicator`
(`test_build_active_indicators_*`, `test_on_load_history_builds_active_indicators_*`,
`test_compute_indicator_series_*`, `test_update_indicators_on_closed_candle_*`) — xoá, thay bằng
test tương đương qua `_script_runner` (đã có khuôn ở các test `test_script_lines_are_routed_to_the_runner_*`).
`test_dev_board_indicators.py` (integration) toàn bộ dựa vào `view._view_model.rsiEnabled = True`
kiểu cũ — phải viết lại dùng `view._view_model.script_model.setEnabled(row, True)`.

### 9.7. Gate
Guard test R1/R3 (BOT-032) đã bắt buộc mọi script phải đăng ký — tự động áp dụng cho 6 script mới.
Sau khi xong, chạy lại toàn bộ `test_dev_board_known_gaps.py`/`test_dev_board_indicators.py` để
đảm bảo không có hành vi cũ nào (màu, tên curve `RSI(14)` không đổi thành `rsi_14:...` — **cân
nhắc: giữ curve name legacy `RSI(14)` cho 6 script default hay chấp nhận đổi sang
`rsi_14:RSI` namespaced?** Đổi tên ảnh hưởng bất kỳ test/tool nào đang match tên cũ — kiểm tra kỹ
trước khi merge).

## 10. Để ngỏ cho Strategy (không xây bây giờ)
- `domain/scripting/` (Series + cross) dùng lại nguyên si cho `BaseStrategyScript`.
- `BaseIndicatorScript` (`setup()` khai báo / `execute()` tính / `compute()` là ranh giới pure)
  là khuôn để copy; chỉ khác `execute()` sinh `Signal` thay vì plot.
- `IndicatorScriptRegistry` copy thành `StrategyScriptRegistry`. **Cố ý không** tạo generic
  `ScriptRegistry[T]` bây giờ (chưa có consumer thứ 2 — đúng tiền lệ YAGNI của repo khi từ chối
  `IIndicator.reset()`). Gộp sau là refactor thuần.
- ⚠️ **Đừng giả định UI tái dùng được**: `StrategyEngine.__init__` nhận đúng **1** strategy
  (không phải list) → UI chọn strategy là combo single-select, không phải list checkbox.

## 11. Phụ thuộc (Dependencies)
- `BOT-020` ✅ — `IIndicator`/`EMA`/`RSI`/`MACD`/`StrategyEngine`.
- `BOT-030` ✅ — `DashboardQmlViewModel`/`DevBoardPanel.qml`/`LogListModel` là nơi Phase 3 cắm vào.
- `BOT-026` (backlog) — **giao nhau ở API marker**, xem Phase 4. Nên phối hợp, đừng làm trùng.
