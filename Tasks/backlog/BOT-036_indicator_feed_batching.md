# Nhiệm vụ: Gộp tín hiệu (Batching) khi replay lịch sử cho indicator script

> **Đọc hết file này trước khi code.** Task này **đã được phân tích và chốt thiết kế** — không cần
> đề xuất lại kiến trúc. Có 1 test **chắc chắn sẽ vỡ** (§6.1) và 3 cạm bẫy đã biết (§6) — đọc kỹ
> trước khi sửa, đừng phát hiện giữa chừng rồi tự ý đổi thiết kế.
>
> Phạm vi: **chỉ 1 file production** (`indicator_script_runner.py`) + 1 file test. **Không đụng**
> `dashboard_presenter.py`, `ChartCard`, pyqtgraph, hay bất kỳ script indicator nào.
>
> Mọi số hiệu dòng trong file này đã được verify tại thời điểm viết task. Nếu lệch, tìm theo tên
> hàm thay vì tin số dòng.

## 1. Mục tiêu (Objective)

`IndicatorScriptRunner.feed_all()` hiện phát Qt signal **mỗi nến × mỗi script × 4 kênh output**.
Với N nến, mảng dữ liệu dài dần theo từng lần phát → chi phí truyền tải tích luỹ **O(N²)**, làm
nghẽn event loop của UI (giật/đơ khi load nhiều nến, đặc biệt khi bật nhiều chỉ báo).

Mục tiêu: khi **replay lịch sử**, tính toán im lặng rồi phát **đúng 1 lần cho mỗi kênh** ở cuối →
đưa về **O(N)**. Khi **nến live real-time**, giữ nguyên hành vi phát ngay lập tức.

**Không thay đổi bất kỳ hành vi nào người dùng nhìn thấy** — chart vẽ ra phải giống hệt trước,
chỉ nhanh hơn.

## 2. Hiện trạng đã verify (đọc code thật, không suy đoán)

File: `src/presentation/ui/screens/dashboard/indicator_script_runner.py`

`feed()` (`:156`) phát 4 kênh, mỗi nến:

| Dòng | Lệnh emit | Có copy mảng không? |
|---|---|---|
| `:162` | `_emit_line` | **Không** — `record()` (`:67`) trả thẳng list sống trong `active.series` |
| `:165` | `_emit_region` | **Có** — `list(active.region_tracker.spans)` mỗi nến |
| `:168` | `_emit_info` | Không (nhưng bị **gán mới** mỗi bar nên vô hại) |
| `:182` | `_emit_markers` | **Có** — `list(active.markers)` mỗi nến |

`feed_all()` (`:184`) chỉ là `for candle in candles: self.feed(candle)`.

**3 caller của `feed_all` — chú ý caller thứ 3:**

| Caller | Thread | Ghi chú |
|---|---|---|
| `dashboard_presenter.py:797` trong `_run_load_history` (`:754`) | BACKGROUND | queued connection |
| `dashboard_presenter.py:916` trong `_run_sync_and_start` (`:870`) | BACKGROUND | queued connection |
| **`dashboard_presenter.py:635` trong `_on_history_prepended` (`:614`)** | **MAIN** (`@Slot`) | **direct connection** |

`_on_history_prepended` là đường load-more-on-scroll (`BOT-035`). Nó chạy `feed_all` **ngay trên
main thread**, nên mỗi emit gọi **đồng bộ** thẳng vào `draw()` → `card.update_indicator_data()` →
pyqtgraph `setData()`. Tức UI bị ép **render lại N lần liên tiếp trong 1 slot** — không chỉ là
"ngập hàng đợi". Tệ hơn: nó refeed **toàn bộ** lịch sử tích luỹ mỗi lần scroll (bắt buộc, vì
`BaseIndicatorScript` không có `reset()`), nên scroll càng nhiều lần thì N càng phình.
**Đây là đường hưởng lợi nhiều nhất từ task này.**

Caller của `feed()` (không phải `feed_all`): `dashboard_presenter.py:744` trong
`_on_ui_chart_update` (`:707`, `@Slot`, MAIN) — chỉ gọi khi `is_closed`.
**Đường này phải giữ nguyên emit ngay.**

## 3. Quyết định đã chốt — KHÔNG re-litigate

1. **Chỉ làm batching.** Không vector hoá NumPy, không multiprocessing (lý do §9).
2. **Không đổi thư viện biểu đồ.** pyqtgraph thừa sức render hàng triệu điểm nếu được đưa nguyên
   mảng 1 lần. Vấn đề nằm ở tần suất emit, không phải renderer.
3. **Không đổi chữ ký công khai** của `feed_all()`. `feed()` chỉ **thêm** 1 tham số
   keyword-only có default → mọi call site hiện tại không cần sửa.
4. **`_flush()` là method riêng**, không nhét inline vào `feed_all()` (SRP + test được độc lập).

## 4. RULES — bắt buộc tuân thủ (quy ước dự án)

| # | Rule | Nguồn |
|---|---|---|
| **R1** | `domain/` **không** import PySide6/pyqtgraph/sagittarius_engine. *(Task này không đụng `domain/`, nhưng đừng "tiện tay" sửa script indicator.)* | Guard test có sẵn |
| **R2** | **Threading contract**: worker nền chỉ được gọi `some_signal.emit(...)`. Mọi mutation ViewModel/`QAbstractItemModel` chỉ xảy ra trong method `@Slot` main thread. `IndicatorScriptRunner` **không biết gì về Qt** — nó chỉ gọi callback `emit_*` được inject; **giữ nguyên tính chất này**, đừng import Qt vào file đó. | `Docs/Diagrams/ui_architecture.md` §8 + docstring class (`:89`) |
| **R3** | **1 concern = 1 file / 1 method.** Tách `_flush()` riêng thay vì phình `feed_all()`. Lý do vận hành: nhiều task AI chạy song song, file/method nhỏ giảm conflict. | Quy ước dự án |
| **R4** | Dùng `./.venv/Scripts/python.exe` (từ repo root `Sagittarius_ForkBoy`), **KHÔNG** dùng `python` trần. | `BOT-032` §3 R9 |
| **R5** | **Ưu tiên object thật hơn mock** ở chỗ là pure state (script/indicator thật). Mock chỉ dành cho dependency ngoài thật sự (`IConfig`, `IDispatcher`, `IThreadManager`). | `ui_architecture.md` §10 |
| **R6** | **KHÔNG** `qtbot.waitSignal()` trên signal có thể bắn nhiều lần liên tiếp từ background thread (`ui_script_region_signal`, `ui_indicator_data_signal`...). Dùng signal bắn đúng 1 lần (`ui_history_load_finished_signal`). Đây là nguyên nhân 1 crash thật (Windows access violation) đã tốn nhiều giờ debug. | `BOT-034` §9, docstring `test_dev_board_indicators.py` |
| **R7** | **KHÔNG chạy cả thư mục** `tests/integration/presentation/ui/` bằng 1 lệnh pytest — có crash **pre-existing** (không phải do bạn gây ra) sau ~26 test/fixture cycle trong cùng 1 process. Chạy theo nhóm file. | `BOT-035` §6 |
| **R8** | Docstring kiểu `@brief` / `@details` / `@param`, giải thích **tại sao** chứ không chỉ **cái gì**. Comment phải nêu lý do quyết định, để lần sau không ai vô tình đảo ngược. | Toàn bộ codebase |
| **R9** | `ruff check` **và** `ruff format --check` phải sạch trên mọi file đã sửa. | CI |
| **R10** | Giữ nguyên comment/docstring giải thích lý do đã có sẵn. Nếu 1 docstring vẫn đúng sau khi đổi code, **đừng xoá** — sửa cho khớp. | Quy ước dự án |

## 5. Thiết kế chi tiết

### 5.1. `feed()` — thêm `emit` keyword-only

```python
def feed(self, candle: MarketData, *, emit: bool = True) -> None:
    """
    @brief Runs one bar through every active script and reports what it produced.
    @param emit When False, computes and accumulates exactly as normal but stays
    silent — the caller then owes a `_flush()` once it has fed everything. Only
    `feed_all()` passes False; the live-tick path (DashboardPresenter's
    `_on_ui_chart_update`) keeps the default True so a real-time bar still
    reaches the chart the moment it closes.
    """
    timestamp = float(candle.close_time.timestamp())
    for key, active in self.active.items():
        for line_name, line in active.script.compute(candle).items():
            x_data, y_data = active.record(line_name, timestamp, line.value)
            if emit:
                self._emit_line(qualified_line_name(key, line_name), x_data, y_data)

        active.region_tracker.record(timestamp, active.script.drain_region())
        if emit:
            self._emit_region(key, list(active.region_tracker.spans))

        active.latest_info = active.script.drain_info()
        if emit:
            self._emit_info(key, active.latest_info)

        new_markers = active.script.drain_markers()
        if new_markers:
            active.markers.extend(
                (
                    timestamp,
                    marker.value,
                    marker.text,
                    marker.color,
                    marker.direction,
                )
                for marker in new_markers
            )
            if emit:
                self._emit_markers(key, list(active.markers))
```

⚠️ **Chỉ bọc `if emit:` quanh 4 lệnh `self._emit_*`.** Mọi lệnh `record()` /
`region_tracker.record()` / `drain_info()` / `drain_markers()` / `markers.extend()` **phải chạy vô
điều kiện** — chúng là mutation state, bỏ qua sẽ làm sai kết quả. `drain_*()` đặc biệt nguy hiểm:
nó **xoá** buffer bên trong script, bỏ 1 lần gọi là state dồn sai sang bar sau.

### 5.2. `_flush()` — method MỚI

```python
def _flush(self, key: str, active: ActiveScript) -> None:
    """
    @brief Emits one snapshot per output channel for a script fed silently
    via `feed(..., emit=False)`.
    @details Mirrors exactly what `feed()` would have emitted on its LAST bar —
    same payload shapes, just once instead of once per bar. A separate method
    (not inlined into `feed_all`) so it can be tested on its own and so
    `feed_all` stays readable.
    """
    for line_name, (x_data, y_data) in active.series.items():
        self._emit_line(qualified_line_name(key, line_name), x_data, y_data)

    self._emit_region(key, list(active.region_tracker.spans))
    self._emit_info(key, active.latest_info)

    # Same guard feed() applies: a script that never produced a marker must
    # not suddenly receive an empty-list emission it never used to get.
    if active.markers:
        self._emit_markers(key, list(active.markers))
```

### 5.3. `feed_all()` — feed im lặng rồi flush

```python
def feed_all(self, candles: Iterable[MarketData]) -> None:
    """
    @brief Replays a whole history.
    @details BOT-036: emits once per output channel at the END instead of once
    per bar. With N bars the old per-bar emit re-sent an ever-growing series
    every single bar (O(N^2) of data crossing the callback boundary); the chart
    only ever needed the final, complete series. `_on_history_prepended` makes
    this especially costly — it replays the whole accumulated history on the
    MAIN thread on every scroll-back, so each emit was a synchronous pyqtgraph
    re-render.
    """
    fed_any = False
    for candle in candles:
        self.feed(candle, emit=False)
        fed_any = True

    if not fed_any:
        return

    for key, active in self.active.items():
        self._flush(key, active)
```

## 6. CẠM BẪY đã biết — đọc trước khi code

### 6.1. 🔴 1 test CHẮC CHẮN vỡ — phải viết lại, KHÔNG được xoá

`tests/unit/presentation/ui/screens/test_indicator_script_runner.py:179`:

```python
def test_each_emission_carries_the_full_series_so_far(runner, emitted):
    """ChartCard.update_indicator_data() replaces the curve's data rather than
    appending, so a partial series would truncate the drawn line."""
    runner.rebuild(["ema_ribbon"])
    runner.feed_all(make_candle(100.0 + index, index) for index in range(25))
    ema20 = [(x, y) for name, x, y in emitted if name == "ema_ribbon:EMA 20"]
    assert len(ema20[-1][0]) == len(ema20)      # vỡ: N == 1
    assert len(ema20[-1][0]) > len(ema20[0][0]) # vỡ: cùng 1 object
```

**Docstring của nó vẫn ĐÚNG và vẫn phải giữ ý nghĩa**: `update_indicator_data()` **thay thế** chứ
không append → lần emit duy nhất bắt buộc phải mang **full series**. Viết lại để pin đúng invariant
đó (gợi ý ở §7), **đừng xoá test**.

### 6.2. 🟠 `candles` là `Iterable`, có thể là generator

Test hiện tại truyền **generator expression**: `feed_all(make_candle(...) for index in range(25))`.
Nên **không được** `if not candles:` hay `len(candles)` — sẽ sai hoặc nổ. Dùng cờ `fed_any` như
§5.3.

### 6.3. 🟠 Markers: giữ nguyên guard, tránh emit list rỗng

`feed()` chỉ emit markers `if new_markers:`. `_flush()` phải `if active.markers:` — nếu không,
script không có marker nào sẽ nhận 1 emit list rỗng mà trước đây không có → đổi hành vi ngầm.

### 6.4. ⚪ `record()` trả list SỐNG (pre-existing, KHÔNG sửa trong task này)

`ActiveScript.record()` (`:67`) trả thẳng list trong `active.series`, không copy. Sau `_flush`,
nến live tiếp theo sẽ `.append()` vào **đúng list mà UI đang giữ**. Đây là chuyện **đã tồn tại từ
trước**, không phải do batching gây ra, và pyqtgraph `setData()` copy vào numpy nên thực tế an
toàn. **Ghi nhận, không sửa** trong task này (ngoài phạm vi; nếu muốn sửa thì mở task riêng).

## 7. Test gate

File: `tests/unit/presentation/ui/screens/test_indicator_script_runner.py`
*(fixture `emitted` (`:52`) nhận qua `emit_line=lambda name, x, y: emitted.append((name, list(x),
list(y)))` (`:85`) — đã copy nên test thấy snapshot, không bị alias theo list sống.)*

**Sửa 1 test:**
```python
def test_the_batched_emission_carries_the_full_series(runner, emitted):
    """ChartCard.update_indicator_data() replaces the curve's data rather than
    appending, so a partial series would truncate the drawn line. BOT-036 made
    feed_all() emit once at the end instead of once per bar — that single
    emission must therefore carry every warmed-up point."""
    runner.rebuild(["ema_ribbon"])

    runner.feed_all(make_candle(100.0 + index, index) for index in range(25))

    ema20 = [(x, y) for name, x, y in emitted if name == "ema_ribbon:EMA 20"]
    assert len(ema20) == 1
    x_data, y_data = ema20[0]
    assert len(x_data) == len(y_data)
    assert len(x_data) > 1   # a real series, not a lone point
```

**Thêm 3 test mới:**
```python
@pytest.mark.parametrize("candle_count", [50, 500])
def test_feed_all_emits_each_line_exactly_once(runner, emitted, candle_count):
    """BOT-036 regression guard: emissions must be O(1) per line, not O(N) per
    bar. Reintroducing a per-bar emit inside feed_all() fails this immediately,
    at any history size."""
    runner.rebuild(["ema_ribbon"])

    runner.feed_all(make_candle(100.0 + i, i) for i in range(candle_count))

    names = [name for name, _, _ in emitted]
    assert len(names) == len(set(names))


def test_a_live_bar_still_emits_immediately(runner, emitted):
    """feed()'s default emit=True is what DashboardPresenter._on_ui_chart_update
    relies on — batching history must not silently mute the real-time path."""
    runner.rebuild(["ema_ribbon"])
    runner.feed_all(make_candle(100.0 + i, i) for i in range(30))
    before = len(emitted)

    runner.feed(make_candle(200.0, 30))

    assert len(emitted) > before


def test_feed_all_with_no_candles_emits_nothing(runner, emitted):
    """_on_history_prepended can legitimately call feed_all([]) when the DB has
    no older data — that must stay silent, exactly as before BOT-036."""
    runner.rebuild(["ema_ribbon"])

    runner.feed_all([])

    assert emitted == []
```

**Kiểm tra lại (nhiều khả năng vẫn pass, nhưng phải chạy chứ đừng đoán):**
`test_bars_with_no_new_marker_do_not_re_emit` (`:365`) — có đếm emit count.

⚠️ Số điểm sau warm-up của EMA(20) trên 25 bar: **đo bằng cách chạy thật**, đừng hardcode con số
đoán. Test ở trên cố ý chỉ assert `> 1` để không phụ thuộc chi tiết warm-up.

## 8. Verification

```bash
# Từ repo root (Sagittarius_ForkBoy)

# 1. Unit — gate chính. Baseline TRƯỚC khi sửa: 420 passed
PYTHONPATH=. ./.venv/Scripts/python.exe -m pytest Binace_Bot/tests/unit -q \
  --ignore=Binace_Bot/tests/unit/domain/entities/test_market_data.py

# 2. Integration — chạy theo NHÓM (xem R7, đừng chạy cả thư mục 1 lệnh)
PYTHONPATH=. ./.venv/Scripts/python.exe -m pytest \
  Binace_Bot/tests/integration/presentation/ui/test_dev_board_indicators.py \
  Binace_Bot/tests/integration/presentation/ui/test_dev_board_custom_scripts.py \
  Binace_Bot/tests/integration/presentation/ui/test_dev_board_load_more.py -q

# 3. Lint (2 file đã sửa)
./.venv/Scripts/python.exe -m ruff check \
  Binace_Bot/src/presentation/ui/screens/dashboard/indicator_script_runner.py \
  Binace_Bot/tests/unit/presentation/ui/screens/test_indicator_script_runner.py
./.venv/Scripts/python.exe -m ruff format --check \
  Binace_Bot/src/presentation/ui/screens/dashboard/indicator_script_runner.py \
  Binace_Bot/tests/unit/presentation/ui/screens/test_indicator_script_runner.py
```

**Manual (chạy app thật):**
1. Bật 4 EMA (20/50/100/200) → Load History → UI không khựng.
2. **Scroll trái liên tục 5-10 lần** để kích hoạt load-more nhiều lần → đây mới là kịch bản tệ nhất
   (§2), quan trọng hơn Load History 1 lần.
3. Nến live vẫn nảy bình thường → chứng minh `emit=True` mặc định không bị batching phá.

**Đo số liệu**: `scripts/benchmark.py` (đã có sẵn, **hiện chưa commit** — đang untracked) chạy
trước/sau để có con số đối chứng.

## 9. Ngoài phạm vi — đã cân nhắc và LOẠI

- **Vector hoá NumPy**: `BaseIndicatorScript.compute(candle)` là API **incremental theo từng nến**
  — đó là toàn bộ contract của hệ thống scripting kiểu Pine Script (`BOT-032`). Vector hoá =
  **thiết kế lại API viết script**, không phải "sửa 1 dòng". Thêm nữa `BOT-020` đã **cố ý** dùng
  **một code path chung** cho batch và incremental để 2 chế độ không bao giờ lệch kết quả — vector
  hoá tạo ra 2 đường tính song song, đúng cái rủi ro mà thiết kế cũ né. Luồng live tick về bản chất
  **phải** incremental. → Nếu thật sự cần: **task riêng có design + review**.
- **Multiprocessing**: gần như chắc chắn **chậm hơn**. Sau batching, 4 EMA trên 10k nến chỉ tốn
  ~0.1s; pickle 10.000 object `MarketData` qua process boundary + spawn process trên Windows tốn
  nhiều hơn thế. → **Loại**, không phải hoãn.
- **Sửa aliasing của `record()`** (§6.4): pre-existing, an toàn trên thực tế, ngoài phạm vi.

## 10. Phụ thuộc (Dependencies)

- `BOT-032` ✅ — `IndicatorScriptRunner`/`BaseIndicatorScript` là sản phẩm của task này.
- `BOT-035` ✅ — `_on_history_prepended` (đường main-thread hưởng lợi nhiều nhất) đến từ đây.
- Không phụ thuộc task nào đang chạy. Chỉ đụng 2 file, rủi ro conflict song song thấp.
