# Nhiệm vụ: Concrete Strategy Foundation — `BaseStrategy` + EMA Crossover (domain-only)

> Thuộc Epic [BOT-006 — Backtest Engine](../backlog/BOT-006_backtest_engine_execution.md), Phase 0.5 (chèn giữa Phase 0 và Phase 1). Phụ thuộc `BOT-020` ✅.

## 1. Mục tiêu (Objective)

Có **ít nhất 1 `IStrategy` cụ thể chạy được** trong `domain/strategies/`, cộng 1
lớp nền (`BaseStrategy`) gom sẵn phần lặp lại (theo dõi lịch sử giá trị
indicator để phát hiện cắt lên/xuống, dựng `Signal`) để các strategy sau viết
ít code hơn — **không đụng** vào `IStrategy`/`StrategyContext`/`StrategyEngine`
đã có và đã test (172 dòng test đang pass). Đây là nền tảng bắt buộc cho
`BOT-021` (Static Backtest): không có ít nhất 1 strategy thật thì không có gì
để backtest.

Task này **thay thế hoàn toàn** bản BOT-026 cũ ("Dev Board — Strategy signals
& markers"). Phần UI/marker/Dev Board của bản cũ đã tách sang
[BOT-039](../backlog/BOT-039_dev_board_strategy_toggle_and_markers.md) (P3, làm sau khi
có UI Backtest thật).

## 2. Mô tả (Description)

`IStrategy` là 1 Protocol có đúng 1 method: `evaluate(context: StrategyContext)
-> Signal` (`src/domain/strategies/i_strategy.py`). `StrategyEngine`
(`src/application/services/strategy_engine.py`) sở hữu việc tính toán
indicator: nó tự `update()` từng `IIndicator`, chỉ gọi `strategy.evaluate()`
khi **mọi** indicator đã "ready" (`all_ready`), và đảm bảo
`run_batch()` ≡ nhiều lần `on_tick()` liên tiếp (cả hai đi qua đúng 1
`_process_one`). Vì lý do này, **strategy nhận giá trị indicator đã tính sẵn
dưới dạng scalar** (`context.indicators: Mapping[str, IndicatorValue]`) —
strategy không tự tính indicator, không giữ tham chiếu tới `IIndicator`.

Điều đó có nghĩa strategy **không thể** dùng `self.ema(12)` kiểu
`BaseIndicatorScript` (class đó tự sở hữu `IIndicator` và tự `update()` —
đúng vai trò cho indicator study, sai vai trò cho strategy, vốn phải nhận input
đã tính sẵn từ `StrategyEngine` để đảm bảo bất biến batch≡incremental không bị
strategy tự phá qua state riêng không kiểm soát được). Cái strategy **thiếu**
để phát hiện "vừa cắt lên" là **lịch sử 1 bar trước** của mỗi giá trị indicator
— `StrategyContext` chỉ đưa giá trị bar hiện tại, không đưa `[1]`. Đây chính
là phần `BaseStrategy` cần cung cấp: tự giữ 1 `Series` nội bộ theo tên (mirror
cơ chế `Series`/`crossed_above`/`crossed_below` đã có sẵn ở
`domain/scripting/`, dùng lại nguyên, không viết lại).

`Docs/Diagrams/ui_architecture.md:465-476` đã ghi sẵn ý định
"`domain/scripting/` được tách riêng để dùng lại cho strategy trong tương
lai" — task này hiện thực hoá đúng ý đó, ở đúng tầng (`domain/strategies/`,
không phải một `BaseScript` chung với indicator — 2 khái niệm khác nhau: script
tự tính + tự vẽ, strategy chỉ ra quyết định từ input đã tính sẵn).

## 3. Các bước thực hiện (Action Items)

- [ ] `src/domain/strategies/base_strategy.py` — `BaseStrategy(ABC)`:
  - `__init__()`: khởi tạo `self._series: dict[str, Series] = {}` rỗng.
  - `evaluate(self, context: StrategyContext) -> Signal` (**concrete**, không
    abstract) — implement đúng chữ ký `IStrategy` cần (Protocol là structural,
    `BaseStrategy` không cần khai `implements IStrategy` tường minh, chỉ cần
    khớp method). Việc nó làm: gọi `self.decide(context)` (abstract, subclass
    override) để lấy `(SignalAction, reason: str)`, rồi dựng và trả về
    `Signal(symbol=context.candle.symbol, action=action, reason=reason,
    price=context.candle.close_price, time=context.candle.close_time)`.
  - `decide(self, context: StrategyContext) -> tuple[SignalAction, str]`
    (abstract) — subclass override, chứa logic thật.
  - `series(self, key: str, history: int = DEFAULT_HISTORY) -> Series` —
    get-or-create, dùng `self._series.setdefault(key, Series(history))`.
    Subclass tự gọi `self.series(KEY).push(value)` mỗi bar trước khi so sánh
    (không tự động push — `decide()` biết giá trị nào cần track, `BaseStrategy`
    không đoán).
  - `buy(self, reason: str) -> tuple[SignalAction, str]`, `sell(self, reason:
    str) -> tuple[SignalAction, str]`, `hold(self, reason: str = _HOLD_REASON)
    -> tuple[SignalAction, str]` — helper 1 dòng trả `(SignalAction.BUY/SELL/
    HOLD, reason)`, chỉ để `decide()` đọc như văn xuôi
    (`return self.buy("ema fast crossed above slow")`).
  - `_HOLD_REASON` là **module-level constant** (không f-string dựng lại mỗi
    bar — hot loop chạy hàng nghìn bar khi backtest).

- [ ] `src/domain/strategies/ema_crossover_strategy.py` — `EmaCrossoverStrategy
  (BaseStrategy)`:
  - Class constants `FAST_KEY = "ema_fast"`, `SLOW_KEY = "ema_slow"` — đây là
    tên key mà `context.indicators` phải có; strategy không tự đặt tên chỉ
    tiêu thụ, nhưng **hằng số nằm ở strategy** vì strategy là bên biết mình
    cần "nhanh" và "chậm" là gì, factory (bước dưới) chỉ đọc lại hằng số này
    khi build `StrategyEngine`, không hard-code chuỗi ở 2 nơi.
  - `__init__(self, fast_period: int = 12, slow_period: int = 26)` — lưu lại
    period chỉ để hiển thị tên/log (`f"EMA Crossover {fast_period}/
    {slow_period}"`), **không** tự tạo `EMA` instance (đó là việc của factory
    khi build `indicators` dict cho `StrategyEngine`).
  - `decide()`: đọc `fast = context.indicators[self.FAST_KEY]`,
    `slow = context.indicators[self.SLOW_KEY]`; push cả hai vào
    `self.series(self.FAST_KEY)` / `self.series(self.SLOW_KEY)`; nếu
    `crossed_above(fast_series, slow_series)` → `self.buy(...)`; elif
    `crossed_below(...)` → `self.sell(...)`; else → `self.hold()`. Dùng lại
    `crossed_above`/`crossed_below` từ `domain/scripting/` — **không** viết
    lại logic cross.

- [ ] `src/domain/strategies/__init__.py` (hiện chưa tồn tại) — export
  `BaseStrategy`, `EmaCrossoverStrategy` (và `IStrategy`,
  `StrategyContext` nếu chưa export, để 1 nơi import cho consumer bên ngoài).

- [ ] `src/application/services/strategy_registry.py` — `StrategyRegistry`,
  **copy nguyên shape** của `IndicatorScriptRegistry`
  (`src/application/services/indicator_script_registry.py`): `register(key,
  strategy_cls)` (raise `ValueError` nếu key trùng), `create(key) ->
  BaseStrategy` (luôn trả instance mới — strategy có state qua `_series`,
  giống lý do indicator script luôn tạo mới), `available() -> Mapping[str,
  type[BaseStrategy]]` (trả bản copy). Không thêm Protocol/interface (đúng lý
  do `IndicatorScriptRegistry` không có: chỉ 1 implementation, không ai swap).

- [ ] `src/application/services/strategy_factory.py` (hoặc hàm trong
  `strategy_registry.py` nếu gọn hơn — tuỳ người viết) — `build_engine(
  registry: StrategyRegistry, key: str, event_bus: IEventBus) ->
  StrategyEngine`: `strategy = registry.create(key)`; build `indicators:
  dict[str, IIndicator]` bằng cách đọc `strategy.FAST_KEY`/`SLOW_KEY` (hoặc,
  nếu muốn tổng quát hơn cho strategy sau này có indicator set khác nhau, cho
  mỗi `BaseStrategy` subclass tự khai 1 method `build_indicators(self) ->
  dict[str, IIndicator]` — **khuyến nghị cách này**, vì nó giữ việc "strategy
  nào cần indicator gì" ở đúng 1 chỗ, factory chỉ gọi lại, không tự đoán theo
  tên class); trả `StrategyEngine(indicators=strategy.build_indicators(),
  strategy=strategy, event_bus=event_bus)`.

- [ ] Đăng ký DI trong `src/binance_bot_module.py` (cạnh chỗ đăng ký
  `IndicatorScriptRegistry`, ~dòng 110-142): tạo `StrategyRegistry`, gọi
  `registry.register("ema_crossover", EmaCrossoverStrategy)`, bind
  `StrategyRegistry` vào container.

- [ ] **Dọn `src/domain/indicator_scripts/ema_cross_script.py`** — xoá 2 dòng
  `self.mark("Buy", ...)` / `self.mark("Sell", ...)` (hiện ở dòng ~50-53).
  Indicator **không được** phát nhãn mang nghĩa quyết định giao dịch — đó là
  việc của Strategy, không phải Indicator (quyết định đã chốt với user). Giữ
  nguyên 2 dòng `self.plot(fast, ...)` / `self.plot(slow, ...)` — 2 đường EMA
  đổi màu theo xu hướng vẫn là output hợp lệ của 1 indicator. Hệ quả: chart
  Dev Board tạm thời **mất nhãn Buy/Sell** cho tới khi
  [BOT-039](../backlog/BOT-039_dev_board_strategy_toggle_and_markers.md) chạy Strategy
  thật — chấp nhận được, đã xác nhận với user.

- [ ] Unit test (`tests/unit/domain/strategies/` — thư mục mới):
  - `test_ema_crossover_strategy.py`:
    - **Golden signal list**: nạp 1 chuỗi giá tay (đủ để có ít nhất 1 lần cắt
      lên và 1 lần cắt xuống, ~30-40 giá trị EMA fast/slow tính sẵn hoặc từ
      giá đóng cửa zigzag đơn giản), chạy `EmaCrossoverStrategy` qua
      `StrategyEngine.run_batch()` với `EMA(3)`/`EMA(5)` (period nhỏ để chuỗi
      test ngắn), so khớp danh sách `Signal.action` từng bar với danh sách kỳ
      vọng viết tay trong test (không chỉ đếm số BUY/SELL).
    - `test_first_evaluated_bar_never_signals` — bar đầu tiên mà `all_ready`
      trở thành `True` **không bao giờ** phát BUY/SELL (vì `Series.previous`
      là `None` ở lần push đầu tiên → `crossed_above`/`crossed_below` False cả
      hai). Pin rõ ràng bằng tên test này, vì đây là hành vi dễ bị "sửa nhầm"
      sau này nếu ai đó nghĩ nó là bug.
    - `Signal.price`/`Signal.time` khớp đúng `candle.close_price`/
      `candle.close_time` của bar phát signal (không phải bar trước/sau).
    - **Batch ≡ incremental**: chạy cùng 1 chuỗi candle qua `run_batch()` 1
      lần và qua nhiều lần `on_tick()` liên tiếp (2 instance
      `EmaCrossoverStrategy`/`StrategyEngine` riêng biệt) → danh sách `Signal`
      thu được phải **giống hệt** nhau.
  - `test_strategy_registry.py`:
    - `register()` raise `ValueError` khi key trùng (mirror test có sẵn của
      `IndicatorScriptRegistry`).
    - `create()` trả **object độc lập** mỗi lần gọi: tạo strategy `a`, feed 30
      bar (đủ để `a._series` có lịch sử); tạo strategy `b` từ cùng key; xác
      nhận `b` chưa "biết" gì (bar đầu tiên feed vào `b` vẫn không phát signal
      do warm-up, chứng minh `b._series` rỗng, không kế thừa state từ `a`).
  - `test_key_alignment_guard.py` (hoặc gộp vào file factory) — với mỗi
    strategy đã đăng ký trong `StrategyRegistry`, xác nhận
    `set(strategy.build_indicators().keys())` khớp đúng tập key mà
    `decide()` cần (với `EmaCrossoverStrategy`: `{FAST_KEY, SLOW_KEY}`) — tránh
    lệch key âm thầm giữa 2 nơi khai báo.

## 4. Rủi ro / Lưu ý (Constraints & Risks)

- **Không đổi** `src/domain/strategies/i_strategy.py`,
  `src/domain/strategies/strategy_context.py`,
  `src/application/services/strategy_engine.py`, hay test suite hiện có của
  3 file này — diff ở 3 file này phải là **0 dòng**. Đây là bất biến quan
  trọng nhất của task (đã kiểm chứng, đã test, không được động vào).
- **Không** làm UI/QML/presenter/marker rendering ở task này — toàn bộ phần
  đó thuộc [BOT-039](../backlog/BOT-039_dev_board_strategy_toggle_and_markers.md).
- **Không** làm PnL/Trade/Equity/`PaperExchange` ở task này — thuộc
  [BOT-021](BOT-021_static_backtest_execution_engine.md).
- `BaseStrategy` **không** kế thừa hay dùng chung code với
  `BaseIndicatorScript` — 2 lớp phục vụ 2 vai trò khác nhau (indicator tự
  tính + tự vẽ nhiều loại output; strategy chỉ tiêu thụ input đã tính sẵn và
  ra đúng 1 quyết định mỗi bar). Gộp chung sẽ ép `StrategyEngine` phải nhường
  quyền tính indicator cho strategy tự làm — phá vỡ bất biến batch≡incremental
  mà `StrategyEngine` đang đảm bảo tập trung ở 1 chỗ.
- `EmaCrossoverStrategy` chỉ implement **long-only, 1 vị thế tại 1 thời điểm**
  (BUY khi cắt lên, SELL khi cắt xuống — SELL ở đây nghĩa là đóng long, không
  phải short). `PaperExchange` (BOT-021) là nơi quyết định SELL không có vị
  thế mở thì bỏ qua — strategy không cần biết mình đang có vị thế hay không
  (đúng đặc tả `IStrategy`: hàm thuần của `context`, không có state giao dịch).
