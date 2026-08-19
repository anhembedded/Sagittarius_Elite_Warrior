# Nhiệm vụ: Triển Khai Chiến Lược "EMA Trend Confirm + Pullback + TP%" (BOT-110)

**Trạng thái:** Hoàn thành (20/08) — bước 3 của [Epic BOT-109](../backlog/BOT-109_golden_strategy_ema_trend_confirm_pullback_epic.md).

## 1. Mục tiêu

Chuyển thể 1:1 mã Pine Script v6 của chiến lược *"EMA Trend Confirm +
Pullback + TP%"* sang Python (`EmaTrendPullbackStrategy`, kế thừa
`BaseStrategy`), đúng tên/mặc định/nhóm/min/max/step của 10 input để UI
tham số round-trip nguyên vẹn.

## 2. Câu hỏi kiến trúc đã chốt trước khi code

File task gốc tự nêu block "câu hỏi kiến trúc chưa chốt": muốn phát đúng
`SELL` (đang Long) hay `COVER` (đang Short) trên cùng một điều kiện
touch-exit, strategy phải **biết mình đang ở phía nào**, nhưng
`StrategyContext` vốn hoàn toàn "position-blind". Giải quyết bằng cách thêm
trường **tuỳ chọn** `current_position_side: PositionSide | None = None` vào
`StrategyContext`, luồng qua `StrategyEngine.on_tick()`/
`on_forming_bar_tick()`/`_process_one()` (tham số tuỳ chọn, mặc định
`None`), và `PaperExchange.current_side` (property mới, dựa trên đảm bảo
"chỉ 1 phía mở cùng lúc" của `BOT-050`) — cả 2 handler (`run_static_backtest`,
`run_realtime_backtest`) đọc `exchange.current_side` **trước** khi gọi
`fill()` của signal bar đó, truyền vào `on_tick`/`on_forming_bar_tick`.
`run_batch()` (dùng bởi indicator script, không phải backtest) không đổi —
luôn truyền `None` ngầm định. Additive hoàn toàn: không strategy nào khác
phải sửa, không `IStrategy` nào bị phá.

## 3. Triển khai

**`EmaTrendPullbackStrategy`** (`src/domain/strategies/ema_trend_pullback_strategy.py`):
- 2 EMA: dài (mặc định 200) xác định xu hướng — chỉ "confirmed" sau
  `tick_confirm` nến đóng liên tiếp cùng phía **không** có râu nến chạm EMA
  dài; ngắn (mặc định 50) là nơi entry pullback về.
- Thoát bằng chạm EMA dài (điều kiện vô hiệu hoá xu hướng, đồng thời là
  exit trigger tuỳ chọn) **hoặc** take-profit intrabar của `PaperExchange`
  (`BOT-041`/`BOT-050`) — **không** phải logic tự thân trong class này.
  `take_profit_percent` khai báo ở đây chỉ để schema tham số round-trip
  đúng như Pine gốc; muốn nó có tác dụng thật phải set riêng
  `BrokerSimulationConfig.take_profit_pct` (Broker Simulator, `BOT-104`) —
  2 giá trị mặc định trùng nhau (2.0%) nên chạy mặc định vẫn khớp Pine,
  nhưng đổi 1 cái không tự đổi cái kia. `enable_alerts` cũng chỉ tồn tại vì
  lý do schema — codebase này chưa có cơ chế gửi alert nào cả, trường này
  vô tác dụng.
- State xác nhận xu hướng (`trend_side`/`consecutive_bars`/
  `confirmed_trend`) và `low`/`high` (cho `candle_confirm_entry`) theo dõi
  qua `Series` + `self.track()`, không phải instance attribute thô — bắt
  buộc cho đúng ở cấp tick (`BOT-076`): `decide()` có thể bị gọi nhiều lần
  cho cùng 1 nến chưa đóng (`on_forming_bar_tick`), chỉ nến đóng thật mới
  được phép nâng các bộ đếm này.

**`Series.committed()`** (mới, `src/domain/scripting/series.py`) — phát
hiện và sửa một **bug thật** trong lúc viết regression test cho đúng đảm
bảo trên (không phải chỉ là lỗ hổng test, xem §4): đọc `series[0]` làm
"giá trị nến trước" là **sai** ở lần gọi `on_forming_bar_tick()` thứ 2 trở
đi trong cùng 1 nến đang hình thành, vì tại thời điểm đó `[0]` đã là giá
trị tạm (provisional) mà chính method này `poke` ở lượt tick trước —
accumulator tự đưa output tạm của chính nó quay lại làm input, khiến bộ
đếm có thể nâng nhiều lần trong 1 nến thay vì đúng 1 lần khi nến đóng thật
— chính loại bug mà kiến trúc provisional/commit `BOT-042` sinh ra để
ngăn, nhưng cách đọc `[0]` ở đây đã vô tình tái tạo lại nó dù đã đi qua
`track()`. `Series.committed(offset)` đọc thẳng lịch sử đã commit, bỏ qua
provisional đang treo — `_update_trend_confirmation()` và
`_entry_confirmation()` đổi sang đọc `.committed(0)` thay vì `[0]`.

**`binance_bot_module.py`**: đăng ký `"ema_trend_confirm_pullback"` vào
`StrategyRegistry`.

## 4. Test

9 test `test_ema_trend_pullback_strategy.py`: schema/mặc định khớp Pine,
`build_indicators()` trả đúng 2 EMA, xu hướng tăng/giảm xác nhận rồi nến
pullback phát đúng BUY/SHORT, râu nến chạm EMA dài reset đúng bộ đếm,
touch-exit phát đúng SELL (đang Long) / COVER (đang Short) / HOLD (đang
Flat), và test bảo đảm tick-safety.

**Test tick-safety ban đầu là "false pass"**: phiên bản đầu dùng cùng 1
nến forming không đổi lặp lại 20 lần *sau khi* xu hướng đã confirmed sẵn —
mọi lượt tick tính ra cùng 1 đáp số nên không phân biệt được đọc provisional
đúng (`committed()`, luôn lấy nến đã đóng gần nhất) với đọc tự tham chiếu
sai (`[0]` thô, trả về giá trị tạm chưa commit mà chính lượt tick trước đã
poke) — cả 2 cách đều pass. Viết lại: dựng nến #2 ở trạng thái **chưa** đủ
`tick_confirm` (mới 2/3 nến liên tiếp) và có hình dạng pullback hợp lệ, để
một lần "confirmed sớm" sai lộ ra thành 1 tín hiệu BUY sai quan sát được từ
bên ngoài, thay vì bị nuốt bởi 1 `confirmed_trend` đã bão hoà sẵn.

Mutation-verify: đảo `.committed(0)` về `[0]` thô → test tick-safety fail
đúng với `SignalAction.BUY` giả (dự đoán bằng tay khớp thực tế), khôi phục
lại xác nhận pass.

Full suite (trừ `tests/integration/presentation/ui/`): 1539 pass, `ruff`
sạch trên `src`/`tests`.

## 5. Ngoài phạm vi (cố ý chưa làm)

- Vẽ 2 đường EMA và marker Buy/Sell/Short/Cover trên chart, sanity/E2E
  chạy `.\scripts\ci-local.ps1 -Full` — thuộc `BOT-111` (bước cuối Epic
  `BOT-109`).
