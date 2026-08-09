# Nhiệm vụ: Custom Indicator Scripts (kiểu Pine Script, thuần Python)

> **Đọc file này trước khi code.** Phase 0-1 đã xong và đã chốt kiến trúc — đừng thiết kế
> lại, hãy extend theo đúng khuôn đã có. Mục §3 (RULES) là bắt buộc.

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
                          series: dict, latest_info: list[InfoField]
    record(line, ts, value) -> (x_data, y_data)   # trả nguyên series tích luỹ

class IndicatorScriptRunner:
    __init__(registry, emit_line, emit_region, emit_info, on_error,
              bar_width_seconds=60.0)          # KHÔNG biết Qt
    rebuild(enabled_keys)          # instance mới mỗi lần (indicator không có reset())
    clear_from_chart(card)         # xoá cả curve, region, info panel của mọi script active
    feed(candle) / feed_all(candles)   # gọi được từ CẢ 2 thread — chỉ emit qua callback
    draw(card, qualified, x, y) -> bool     # False = không phải script line -> caller tự xử lý
    draw_region(card, key, spans)  # không trả bool — region/info không có built-in fallback
    draw_info(card, key, fields)
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

**Còn thiếu của Phase 2** (để model khác làm): test tích hợp thật trên Dev Board qua UI thật
(bật script → Load History → assert curve/tint/panel) chạy trong app thật, không chỉ offscreen
script — xem `scripts/run-ui.ps1 -Dev` ở mục Verification cuối file.

## 6. Phase 3 — UI bật/tắt script  *(CHƯA LÀM)*

> **File ownership** (để chạy song song không conflict): task này chỉ tạo mới
> `indicator_script_list_model.py` và sửa `dashboard_view_model.py` + `DevBoardPanel.qml`.
> **Không đụng** `indicator_script_runner.py`, `script_region_tracker.py`,
> `dashboard_presenter.py`, hay bất kỳ file nào trong `chart_card/` — tất cả đã xong ở §5.
> `dashboard_presenter.py` chỉ đổi đúng 1 dòng: `_enabled_script_keys()` trả
> `self._view_model.script_model.enabled_keys`.

1. **File mới** `screens/dashboard/indicator_script_list_model.py` — `QAbstractListModel`,
   copy shape từ `screens/_qml_shared/log_list_model.py`:
   roles `key`/`title`/`enabled`; `set_available(scripts)` (beginResetModel/…/endResetModel);
   `@Slot(int, bool) setEnabled(row, value)` + `dataChanged`; `@property enabled_keys`.
2. `dashboard_view_model.py`: `self._script_model = IndicatorScriptListModel(self)` +
   `@Property(QObject, constant=True) scriptModel` + `@property script_model`
   (cặp accessor giống `logModel`/`log_model` đang có).
3. Presenter đổ danh sách: `self._view_model.script_model.set_available(registry.available())`.
   **ViewModel không tự resolve container** (giữ tính chất "ViewModel không có DI dependency").
4. `DevBoardPanel.qml` — thêm vào card INDICATORS:
   ```qml
   SectionLabel { text: "CUSTOM SCRIPTS" }
   Repeater {
       model: viewModel.scriptModel
       RowLayout {
           Layout.fillWidth: true
           required property var model
           required property int index
           StyledCheck {
               objectName: "chkScript_" + model.key
               text: model.title
               checked: model.enabled
               onToggled: viewModel.scriptModel.setEnabled(index, checked)
           }
       }
   }
   ```
   ⚠️ Khác Repeater ở `DatabaseScreen.qml` (array JS **tĩnh**) — ở đây **bắt buộc**
   `QAbstractListModel` thật vì danh sách đến từ registry lúc runtime và `enabled` đổi được.

**Test gate**: click `chkScript_ema_cross` qua fixture `qml_item(...)`
⚠️ **delegate của Repeater KHÔNG phải QObject child → `findChild()` trả None**, bắt buộc dùng
`qml_item`/`walk_qml_items`. **+ screenshot.**

---

## 7. Phase 4 — Chart nâng cao: marker / màu động / fill  *(1 trong 3 mục CHƯA LÀM)*

Domain đã sinh đủ dữ liệu (`PlottedMarker`, `PlottedLine.color` theo từng bar, `PlottedRegion`,
`InfoField`) nhưng chart chưa vẽ hết. `PlottedRegion`/`InfoField` **đã xong** (xem §5) — bảng
dưới đây chỉ còn marker + màu động + fill.

| Cần | Hiện trạng | Gợi ý |
|---|---|---|
| **Background tint** (`bgcolor`) | ✅ **XONG** — `set_script_regions`/`ScriptRegionTracker`, xem §5. | — |
| **Status panel** (`table.cell`) | ✅ **XONG** — `set_script_info`/`script_info_label`, xem §5. | — |
| **Marker Buy/Sell có label** (`plotshape`) | ❌ không có. `drain_markers()` đã có ở domain nhưng `IndicatorScriptRunner.feed()` có TODO chưa gọi tới. | `pg.ScatterPlotItem` + `pg.TextItem`. **Trùng phạm vi `BOT-026`** (marker Buy/Sell cho strategy) → **làm 1 API dùng chung, đừng làm 2 lần**. Đề xuất: `ChartCard.add_markers(name, points, color)` / `clear_markers(name)`. |
| **Màu đổi theo bar** (`c = b > a ? lime : red`) | ❌ 1 pen/curve | pyqtgraph không đổi màu giữa chừng 1 curve. 2 cách: (a) tách thành nhiều segment mỗi khi màu đổi, (b) `pg.PlotCurveItem` với `pen=None` + vẽ tay. **(a) đơn giản hơn, đề xuất (a).** |
| **`fill(p1, p2)`** | ❌ không có | `pg.FillBetweenItem`. Ưu tiên thấp nhất — làm sau cùng, hoặc bỏ nếu tốn. |

**Quyết định phạm vi cần hỏi user trước khi làm phần còn lại của Phase 4** (đừng tự quyết): làm
cả 3, hay chỉ marker (thứ user nêu đích danh trong story)?

---

## 8. Phase 5 — Docs + full CI  *(CHƯA LÀM)*
- Thêm mục vào `Docs/Diagrams/ui_architecture.md`: cách viết 1 script mới (3 bước: tạo file →
  `register()` → tự hiện trong UI), kèm mermaid luồng
  `execute() → plot()/mark() → buffer → compute() → signal → chart`.
- `ci-local.ps1 -Full` xanh.

## 9. Phase 6 — chuyển RSI/EMA/MACD hardcode thành script  *(để sau, có thể tách task)*
User đã chốt "update 3 cái đó sau". **Blocker đã biết**: script hiện zero-arg, còn RSI/EMA có
spinbox period → cần dùng `params` đã chừa sẵn ở `create(key, params=None)`, cộng cách khai báo
param trong script (kiểu Pine `input()`) và render spinbox động trong QML. **Không phải đổi
signature** khi làm, đó là lý do `params` có từ Phase 0.

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
