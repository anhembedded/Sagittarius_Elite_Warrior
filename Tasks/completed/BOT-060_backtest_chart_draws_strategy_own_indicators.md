# Nhiệm vụ: Chart Canvas vẽ đúng indicator của Strategy đang backtest (thay vì luôn cố định `ema_ribbon`)

> Thuộc Epic [BOT-040 — Backtest Screen Full Feature Set](../backlog/BOT-040_backtest_screen_full_feature_epic.md), Nhóm D (nối tiếp `BOT-056`). Phụ thuộc `BOT-046` ✅, `BOT-047` ✅, `BOT-056` ✅.

## 1. Mục tiêu (Objective)

User phát hiện qua ảnh chụp thật (`Tasks/bug_report/completed/BUG-002.md`): marker
Buy/Sell trên biểu đồ Backtest không nằm ở chỗ các đường EMA cắt nhau — vì
đường đang vẽ **không phải** đường mà strategy dùng để ra quyết định. Toggle
"4 EMA" hiện hard-code luôn vẽ script `ema_ribbon` (EMA 20/50/100/200,
`_CHART_EMA_SCRIPT_KEY` ở `backtest_presenter.py`), bất kể strategy đang
chọn là gì. `EmaCrossoverStrategy` mặc định dùng EMA 12/26 (`fast_period`/
`slow_period`, đổi được qua modal "Thông số Bot" — `BOT-047`) — hoàn toàn
khác 4 đường đang hiển thị, nên không thể verify bằng mắt vì sao strategy
Buy/Sell tại đúng cây nến đó.

Gap này **đã được ghi chú trước** ngay lúc viết `BOT-056` §2.2: *"EMA của
indicator script không nhất thiết cùng period với EMA mà strategy đang
backtest — nếu lệch dễ gây hiểu nhầm... đồng bộ nếu làm được sau `BOT-046`"*.
Lúc đó `BOT-046` chưa xong nên đành tạm dùng `ema_ribbon` làm proxy. Giờ
`BOT-046`/`BOT-047` đã xong — mọi strategy đều có `build_indicators()` (tên +
kỳ hạn thật) truy vấn được — nên sửa đúng gốc đã khả thi.

## 2. Mô tả (Description)

`BaseStrategy.build_indicators()` (`domain/strategies/base_strategy.py`) trả
về `dict[str, IIndicator[IndicatorValue]]` — đúng tập indicator strategy
dùng để `decide()`, với period/tham số đã resolve theo `strategy_params`
hiện tại (`BOT-047`). `IIndicator.update(close_price) -> value | None` là
stateful/streaming (`domain/indicators/i_indicator.py`) — feed lần lượt giá
đóng cửa từng nến sẽ tái tạo đúng chuỗi giá trị mà `StrategyEngine` đã dùng
khi chạy backtest thật (không cần đụng `strategy_engine.py`/`i_strategy.py`
— bất biến "diff = 0 dòng" của `BOT-026` giữ nguyên, vì đây là một lần chạy
lại **độc lập**, chỉ để vẽ, không phải lấy kết quả từ engine).

`IndicatorValue = float | MACDValue` (`strategy_context.py`) — `EMA.update()`
trả `float` (vẽ được thẳng), nhưng 1 indicator như `MACD` trả về
`MACDValue(macd, signal, histogram)` (dataclass 3 field) — cần tách thành 3
đường riêng chứ không vẽ được thẳng 1 giá trị.

**Không tái dùng `IndicatorScriptRunner`** (`presentation/ui/screens/
dashboard/indicator_script_runner.py`) — class đó ăn khớp chặt với
`BaseIndicatorScript` (`script.compute()`/`.line_colors()`/`.drain_*()`),
strategy không có API này (`build_indicators()` chỉ *mô tả* indicator, không
tự vẽ gì). Cần 1 hàm tính toán thuần Python riêng, nhỏ, đủ dùng.

## 3. Các bước thực hiện (Action Items)

- [ ] File mới `src/presentation/ui/screens/backtest/strategy_indicator_lines.py`
  (thuần Python, không phụ thuộc Qt — cùng phong cách `bot_params_form.py`):
  - `compute_strategy_indicator_lines(strategy: BaseStrategy, klines:
    Iterable[MarketData]) -> dict[str, tuple[list[float], list[float]]]` —
    với mỗi indicator trong `strategy.build_indicators()`, feed
    `candle.close_price` qua `.update()` cho từng nến, bỏ qua giá trị `None`
    (đang warm-up), dùng `candle.close_time.timestamp()` làm trục x. Giá trị
    `float` → 1 đường tên đúng key indicator; giá trị dataclass (như
    `MACDValue`) → tách theo `dataclasses.fields()`, tên đường
    `f"{key}_{field.name}"`.
  - `assign_strategy_line_colors(line_names: Sequence[str]) -> dict[str,
    str]` — gán màu theo thứ tự xuất hiện, cycle qua bảng màu cố định (tái
    dùng đúng 4 màu `ema_ribbon` đã dùng làm 4 màu đầu — `#e74c3c`/`#e67e22`/
    `#00bcd4`/`#3498db` — để nhìn quen mắt, cộng thêm vài màu dự phòng cho
    strategy nhiều hơn 4 đường).
- [ ] `backtest_presenter.py`: xoá `_CHART_EMA_SCRIPT_KEY`/`_chart_script_runner`
  (`IndicatorScriptRunner`) khỏi màn Backtest — không còn dùng cho mục đích
  này nữa. Thay bằng: trong `_fetch_and_emit_chart_data` (background thread,
  đã có sẵn `config`/`mapped_klines`), dựng strategy thật qua
  `self._strategy_registry.available().get(config.strategy_key)` +
  `config.strategy_params` (construct-and-discard, giống cách `BOT-047`
  validate — không phải instance dùng để chạy backtest, chỉ để tính lại
  đường vẽ), gọi `compute_strategy_indicator_lines`, emit qua signal mới
  `_chartStrategyLineSignal = Signal(str, str, list, list)` (tên đường, màu,
  x, y) — 1 lần/đường sau khi tính xong toàn bộ (không emit theo từng nến,
  giữ đúng bài học hiệu năng O(N²) đã sửa ở `BOT-036`).
  - Slot main-thread mới `_on_chart_strategy_line`: `card.add_overlay_indicator
    (name, color)` nếu đường chưa đăng ký, rồi `card.update_indicator_data
    (name, x, y)` — mirror đúng cách `IndicatorScriptRunner.draw()` làm,
    không cần qua class đó.
  - `_start_backtest_run`: thay `self._chart_script_runner.clear_from_chart
    (card)` bằng xoá các đường đã đăng ký của lần chạy trước
    (`card.remove_indicator(name)` cho từng tên trong tập đang track).
  - `_on_ema_toggled`/`sig_ema_toggled`: đổi để bật/tắt hiển thị đúng tập
    đường **hiện đang vẽ** (không còn cố định theo `_CHART_EMA_SCRIPT_KEY`).
  - Strategy không khai báo indicator nào (`build_indicators()` rỗng — về lý
    thuyết không strategy nào hiện tại làm vậy, nhưng không được crash) →
    không có đường nào để vẽ, checkbox coi như không có gì bật/tắt.
- [ ] `chart_controls.py`: đổi label checkbox "4 EMA" → tên phản ánh đúng ý
  nghĩa mới (không còn cố định 4 đường EMA — số đường phụ thuộc strategy).
  Object name (`chkChartEma`) và tên method (`is_ema_checked`/
  `set_ema_enabled`) giữ nguyên được — đổi tên không bắt buộc, chỉ đổi text
  hiển thị, tránh phá vỡ test không cần thiết.
- [ ] Cập nhật `tests/unit/presentation/ui/screens/test_backtest_presenter.py`:
  các test đang giả định `_chart_script_runner`/`ema_ribbon` (khoảng dòng
  244-250, 1056-1136) chuyển sang test hành vi mới; thêm test riêng cho
  `strategy_indicator_lines.py` (indicator trả `float` thẳng, indicator trả
  dataclass tách nhiều đường, bỏ qua warm-up `None`, màu gán ổn định theo
  thứ tự).
- [ ] Rà `tests/sanity/test_backtest_screen_di_sanity.py` — nếu có sanity
  check nào giả định `ema_ribbon` phải đăng ký cho màn Backtest hoạt động,
  cập nhật/loại bỏ theo đúng thay đổi này.

## 4. Rủi ro / Lưu ý (Constraints & Risks)

- **Không đụng** `i_strategy.py`/`strategy_context.py`/`strategy_engine.py`/
  `test_strategy_engine.py` — bất biến "diff = 0 dòng" (`BOT-026`) giữ
  nguyên. Việc tính lại indicator ở đây là một lần chạy **hoàn toàn tách
  biệt** khỏi `StrategyEngine` thật (chỉ đọc `build_indicators()` + tự feed
  giá đóng cửa), không phải sửa engine để nó "trả thêm" chuỗi indicator.
- Dựng strategy 2 lần cho 1 lần backtest (1 lần thật qua `build_engine()` ở
  handler, 1 lần construct-and-discard ở đây để lấy `build_indicators()`) —
  chấp nhận được, cùng pattern "construct-and-discard" `BOT-047` đã dùng để
  validate; không có cách nào lấy lại instance đã dùng trong
  `RunStaticBacktestCommandHandler` mà không xuyên tầng use-case → presentation.
- `MACDValue`/dataclass nhiều field: chưa có strategy thật nào dùng `MACD`
  hôm nay (chỉ `EmaCrossoverStrategy`, dùng 2×`EMA`), nên nhánh này chưa có
  test end-to-end bằng 1 strategy thật — test bằng 1 test-double strategy
  khai báo indicator giả trả dataclass, để không phải chờ có strategy MACD
  thật mới lộ bug.
- Đây là biểu đồ **Equity/OHLC price-scale overlay** — giữ nguyên hành vi
  ẩn/disable khi chuyển sang chế độ Equity-solo (`set_ema_enabled`/
  `_on_chart_mode_changed`), không đổi logic đó.
