# Nhiệm vụ: Indicator & Strategy Engine (Core) — Phase 0

> Thuộc Epic [BOT-006 — Backtest Engine](../backlog/BOT-006_backtest_engine_execution.md), Phase 0 (Nền tảng dùng chung).

## 1. Mục tiêu (Objective)
Xây dựng lõi tính chỉ báo kỹ thuật + đánh giá chiến lược, dùng chung cho cả **Backtest** (Phase 1/2 của epic này) và **Live Trading** (`BOT-008`) — tránh xây 2 bộ Indicator/Strategy khác nhau cho 2 tính năng vốn cần cùng 1 logic.

## 2. Mô tả (Description)
Lõi tính toán thuần (pure logic), không phụ thuộc UI, I/O hay Binance API, chạy được ở 2 chế độ:
- **Batch**: nhận toàn bộ mảng nến, trả về danh sách tín hiệu — dùng cho Static Backtest (`BOT-021`).
- **Incremental**: nhận từng nến/tick một, tự cập nhật state nội bộ, trả về tín hiệu (nếu có) — dùng cho Dynamic Backtest (`BOT-023`) và Live Trading (`BOT-008`). *(Ghi chú 2026-08-18: `BOT-023` sau đó đã bị huỷ; consumer của chế độ incremental nay là `BOT-076` — Realtime Backtest — và `BOT-008`.)*

## 3. Các bước thực hiện (Action Items)
- [x] `IIndicator` protocol + cài đặt `RSI`, `EMA`, `MACD` (pure function/class, có thể unit test độc lập với dữ liệu đã biết trước kết quả).
- [x] `IStrategy` protocol: `evaluate(context) -> Signal` (Signal gồm action Buy/Sell/Hold, lý do, giá, thời điểm).
- [x] `StrategyEngine` hỗ trợ 2 chế độ chạy:
  - [x] `run_batch(klines: list[MarketData]) -> list[Signal]`.
  - [x] `on_tick(candle: MarketData) -> Signal | None` (giữ state giữa các lần gọi).
- [x] `SignalGeneratedEvent(symbol, action, reason, price, time)` phát qua `IEventBus` mỗi khi có tín hiệu mới (cả 2 chế độ).
- [x] Unit test: từng indicator so khớp giá trị với công thức chuẩn (dùng bộ dữ liệu tham chiếu cố định); `StrategyEngine` cho kết quả **giống nhau** giữa batch và incremental trên cùng 1 bộ dữ liệu (đây là bài test đối chiếu quan trọng — nếu 2 chế độ lệch nhau nghĩa là có bug).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đây là nền tảng dùng chung — khi triển khai `BOT-008`, action item "Thiết kế `IIndicator`..." của task đó nên **tái sử dụng module này** thay vì làm lại từ đầu. Nên làm `BOT-020` trước hoặc song song với bước đầu của `BOT-008`.
- Không gọi bất kỳ I/O nào (DB, network) trong `StrategyEngine`/indicator — giữ pure để test nhanh và dễ đối chiếu batch/incremental.

## 5. Ghi chú hoàn thành (Completion Notes)

**Vị trí layer:** `IIndicator`/`RSI`/`EMA`/`MACD`/`IStrategy`/`Signal`/`SignalAction`/`SignalGeneratedEvent` đặt trong `src/domain/` (2 package mới: `domain/indicators/`, `domain/strategies/`) — dù mọi `Protocol`/`ABC` khác trong repo đều nằm ở `application/ports/`. Lý do: các lớp này là pure computation, zero I/O, đúng tinh thần "lõi" mà task này mô tả; chỉ `StrategyEngine` (cần `IEventBus` để phát side-effect) nằm ở `src/application/services/` (thư mục mới). Đã thảo luận và xác nhận với user trước khi triển khai.

**Cơ chế đảm bảo batch == incremental:** Mỗi indicator (`RSI`/`EMA`/`MACD`) là 1 state machine với 1 điểm mutation duy nhất — `update(value) -> T | None`. `StrategyEngine.run_batch()` chỉ là "gọi lại đúng `on_tick` trên 1 engine mới khởi tạo, trong vòng lặp" — không phải 2 implementation song song — nên 2 chế độ **không thể** lệch nhau về mặt cấu trúc, không chỉ nhờ test. Test đối chiếu (`test_batch_and_incremental_produce_identical_signals`) dùng 2 instance `StrategyEngine` hoàn toàn tách biệt (mỗi bên tự có `RSI`/`Mock event bus` riêng) để loại trừ khả năng pass giả do state dùng chung.

**Hold không sinh Signal/Event:** `on_tick()`/`run_batch()` trả về `None` cả khi indicator đang warm-up **lẫn** khi strategy quyết định Hold — chỉ trả `Signal` thật khi có hành động Buy/Sell. `SignalGeneratedEvent` vì vậy chỉ phát khi có Signal thật, giữ đúng yêu cầu "mỗi khi có tín hiệu mới" mà không spam event mỗi tick Hold. Đây là quyết định đã thảo luận với user (phương án được chọn thay vì luôn trả Signal kể cả Hold).

**`Signal` có thêm field `symbol`** (task gốc chỉ liệt kê action/reason/price/time cho `Signal`) — cần thiết vì `SignalGeneratedEvent` bọc `Signal` trong 1 field duy nhất (`signal: Signal`, theo đúng convention của `MarketTickEvent(market_data: MarketData)`), nên `symbol` phải nằm sẵn trong `Signal`.

**`MACD.update()` trả `MACDValue`** (dataclass 3 field: macd/signal/histogram), không phải `float` — nên `StrategyContext.indicators` có kiểu `Mapping[str, float | MACDValue]` thay vì `dict[str, float]`.

**Không có `reset()` trên `IIndicator`:** cân nhắc rồi bỏ (YAGNI) — cần dữ liệu mới thì khởi tạo indicator mới, đơn giản hơn maintain reset path cho cả 3 class trong khi chưa có nhu cầu cụ thể.

**Không ship concrete `IStrategy`:** chỉ có protocol + 1 stub strategy (RSI threshold) trong test file, không xuất hiện trong `src/`. Strategy cụ thể (vd. EMA crossover) là quyết định sản phẩm của `BOT-008`/`BOT-021`, ngoài phạm vi task này — đã xác nhận với user.

**Đối chiếu công thức:** Không dùng số liệu "tham khảo" nhớ lại từ web — mỗi indicator được đối chiếu với 1 implementation độc lập thứ 2 (viết theo dạng vòng lặp mảng thuần, không dùng state incremental) trên cùng 1 bộ dữ liệu, chạy thực tế để lấy số chính xác trước khi đưa vào test (`tests/unit/domain/indicators/`), cộng thêm các test theo tính chất giải tích (giá không đổi → EMA hội tụ về đúng giá đó; giá tăng liên tục → RSI = 100.0 chính xác, không chia cho 0).

**Phạm vi KHÔNG làm** (đúng như task yêu cầu, để dành cho `BOT-008`/`BOT-021`/`BOT-023`): không đăng ký `StrategyEngine` vào DI container (`binance_bot_module.py`), không wiring vào `MarketTickEventHandler`/live WebSocket stream, không `PaperExchange`, không concrete strategy.

**File đã tạo:**
- `src/domain/indicators/{i_indicator,rsi,ema,macd}.py`
- `src/domain/strategies/{i_strategy,strategy_context}.py`
- `src/domain/value_objects/{signal,signal_action}.py`
- `src/domain/events/signal_generated_event.py`
- `src/application/services/strategy_engine.py`
- `tests/unit/domain/indicators/{test_rsi,test_ema,test_macd}.py`
- `tests/unit/application/services/test_strategy_engine.py`

Verify: `ruff check` + `ruff format --check` pass; toàn bộ 169 test (152 cũ + 17 mới) pass; các architecture guard test (`test_application_layer_structure.py`, `test_card_layer_structure.py`, `test_screen_layer_structure.py`) vẫn pass không bị ảnh hưởng.
