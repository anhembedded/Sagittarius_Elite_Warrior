# Nhiệm vụ: Dev Board — Strategy Toggle List + Buy/Sell Markers

> Thuộc Epic [BOT-006 — Backtest Engine](BOT-006_backtest_engine_execution.md), Phase 3. Phụ thuộc `BOT-026` ✅. Ưu tiên **P3** — làm sau khi màn Backtest (Epic BOT-006 Phase 1 / Epic BOT-040) đã ổn định, không nằm trên đường chặn của epic đó.

## 1. Mục tiêu (Objective)

Cho phép bật/tắt 1 hoặc nhiều `Strategy` (từ `StrategyRegistry`, có sẵn từ
`BOT-026`) ngay trên Dev Board trong lúc **Live streaming**, thấy tín hiệu
Buy/Sell dưới dạng marker trên chart và log ra System Monitor — theo đúng cơ
chế mà Indicator scripts đã có (`BOT-032`). Đây là nửa UI đã tách khỏi bản
BOT-026 gốc, theo US-02 (`Tasks/UserStory_Propose.md`).

Giá trị thật của task này (khác Backtest screen): thấy signal **khi đang
live streaming**, không phải chạy trên dữ liệu lịch sử đã xong — và là
**subscriber đầu tiên thật sự** của `SignalGeneratedEvent`
(`src/domain/events/signal_generated_event.py`, hiện `StrategyEngine` đã
phát nhưng chưa ai lắng nghe) — mở seam sẵn cho `BOT-008` (Live Trading).

## 2. Mô tả (Description)

Kiến trúc mirror gần như 1:1 cơ chế Indicator script đã có
(`IndicatorScriptListModel` → `IndicatorScriptRunner` →
`DashboardPresenter._on_script_marker_data` →
`ChartCard.set_script_markers()`), áp dụng cho `StrategyRegistry`/
`BaseStrategy` (`BOT-026`) thay vì `IndicatorScriptRegistry`/
`BaseIndicatorScript` (`BOT-032`). Khác biệt quan trọng nhất: 1 `IStrategy`
chỉ trả về **1 `Signal`/bar** (không phải nhiều `PlottedLine`/`PlottedMarker`
như indicator), và chạy qua `StrategyEngine.on_tick()` (incremental, đã có
từ `BOT-020`) chứ không tự quản lý `IIndicator` như
`BaseIndicatorScript.compute()` làm.

Control cosmetic hiện có (`cboStrategy`,
`src/presentation/ui/screens/dashboard/DevBoardPanel.qml:201-215`,
`model: ["Manual", "SMA Crossover"]`) gọi tên 1 strategy **không tồn tại**
("SMA Crossover" khác `EmaCrossoverStrategy` thật của `BOT-026`) và không có
logic nào đọc nó (`TC-GAP-04`,
`Tasks/reports/dev_board_user_end_test_cases.md`). Task này **xoá hẳn** nó
thay vì wire lại — cùng tiền lệ `BOT-034` đã xoá `cboTimeframe` cosmetic để
thay bằng `ChartToolbar` thật.

## 3. Các bước thực hiện (Action Items)

- [ ] `src/presentation/ui/screens/dashboard/strategy_list_model.py` —
  `StrategyListModel(QAbstractListModel)`, copy shape của
  `IndicatorScriptListModel` (`key`/`title`/`enabled` role, `set_available()`,
  `enabledKeysChanged`). Nguồn dữ liệu: `StrategyRegistry.available()`
  (`BOT-026`).
- [ ] `src/presentation/ui/screens/dashboard/strategy_runner.py` —
  `StrategyRunner`, copy shape của `IndicatorScriptRunner` nhưng đơn giản hơn
  nhiều (không có `PlottedLine`/`PlottedRegion`/`InfoField` — strategy chỉ có
  `Signal`): constructor nhận `registry: StrategyRegistry`,
  `emit_markers: Callable[[str, list[MarkerPoint]], None]`,
  `emit_log: Callable[[str], None]`, `on_error`. Nội bộ dùng
  `build_engine(registry, key, event_bus)` (factory có sẵn từ `BOT-026`) để
  dựng `StrategyEngine` cho mỗi strategy đang bật; feed từng candle qua
  `engine.on_tick(candle)`; khi `Signal.action` là BUY/SELL (bỏ qua HOLD) →
  convert thành `MarkerPoint = (x, y, text, color, direction)` (x =
  `signal.time.timestamp()`, y = `signal.price`, text = `"Buy"`/`"Sell"`,
  color xanh/đỏ giống `_BULL`/`_BEAR` trong `ema_cross_script.py`, direction
  `"up"`/`"down"`) và gọi `emit_markers(f"strategy:{key}", [...])`; đồng thời
  `emit_log(f"[{key}] {signal.action.value} @ {signal.price} — {signal.reason}")`.
  Namespace `"strategy:{key}"` (khác `IndicatorScriptRunner`'s bare
  `qualified_line_name`) để marker của Strategy và của Indicator (nếu 1
  indicator cũng tự `mark()`) không đè lên nhau trên cùng `ChartCard`.
- [ ] Wiring trong `dashboard_presenter.py` (mirror khối
  `_script_registry`/`_script_runner` hiện có ở dòng ~270-289): resolve
  `StrategyRegistry` từ container, dựng `StrategyRunner`, nối
  `self._view_model.strategy_model.set_available(self._strategy_registry.available())`,
  connect callback marker vào **đúng** `ChartCard.set_script_markers()` đã có
  sẵn (`chart_card.py:300`) — **không thêm API mới**, `set_script_markers`
  vốn nhận `(key, markers)` bất kể nguồn là Indicator hay Strategy.
- [ ] Feed strategy cùng lúc với indicator trong `_rebuild_scripts()` /
  `StreamLifecycleController` (bất cứ nơi nào `_script_runner.feed(...)`
  đang được gọi mỗi candle) — thêm 1 lệnh gọi tương ứng cho
  `_strategy_runner`.
- [ ] QML — thêm khối "STRATEGIES" trong `DevBoardPanel.qml`, đặt cạnh khối
  "INDICATORS" (dòng ~296-330), cùng layout `Rectangle`/`ColumnLayout` +
  `Repeater` trên `viewModel.strategyModel`, mỗi dòng 1 `StyledCheck`
  (`objectName: "chkStrategy_" + model.key"`, mirror
  `"chkScript_" + model.key`).
- [ ] **Mutually-exclusive với Indicators** (quyết định đã chốt): bật 1
  strategy thì **tắt tất cả** indicator script đang bật (và ngược lại) —
  tránh chart bị chồng marker/curve từ 2 nguồn cùng lúc gây rối. Implement ở
  ViewModel layer (nơi giữ enabled state, giống ghi chú trong
  `IndicatorScriptListModel`'s docstring), không phải ở Presenter.
- [ ] **Xoá** `cboStrategy` khỏi `DevBoardPanel.qml` (dòng 201-215) — không
  wire lại.
- [ ] Xoá strategy khỏi chart: khi user tắt checkbox, gọi
  `ChartCard.clear_script_markers(f"strategy:{key}")` (đã có sẵn,
  `chart_card.py:303`), theo đúng hành vi "tắt state bị xoá khỏi chart mà
  không cần reload toàn bộ màn hình" (US-02 acceptance criteria).
- [ ] Unit/integration test: `StrategyListModel` set_available/enabled
  round-trip (mirror test có sẵn của `IndicatorScriptListModel`);
  `StrategyRunner` sinh đúng marker cho 1 chuỗi giá đã biết trước (golden,
  tái dùng fixture của `BOT-026` nếu hợp); mutually-exclusive: bật strategy
  tắt hết indicator đang bật và ngược lại; `test_strategy_dropdown_has_no_presenter_effect`
  (`tests/integration/presentation/ui/test_dev_board_known_gaps.py:157`)
  phải được **viết lại** để test khối "STRATEGIES" mới, không xoá (tiền lệ
  `BOT-036` §6.1); cập nhật `TC-GAP-04` trong
  `Tasks/reports/dev_board_user_end_test_cases.md` từ "gap" thành "FIXED".

## 4. Rủi ro / Lưu ý (Constraints & Risks)

- **Không** đụng `StrategyEngine`/`IStrategy`/`StrategyContext` — dùng
  nguyên `on_tick()` đã test, không thêm code tính toán mới ở tầng domain.
- **Không** trùng lặp với marker của `BOT-021`/`BOT-057` (Trade Logs Table
  của Epic BOT-040) — 2 nguồn khác nhau: task này vẽ marker **thời gian
  thực lúc Live streaming** trên Dev Board; `BOT-021`/`BOT-057` vẽ marker
  **sau khi 1 lượt backtest tĩnh đã chạy xong** trên màn Backtest. Không
  chia sẻ code UI, chỉ chia sẻ chung API `set_script_markers`.
  `StrategyRunner` ở đây **không** dùng `PaperExchange` — không tính PnL,
  không mô phỏng khớp lệnh, chỉ hiển thị tín hiệu thô.
  Mỗi strategy chạy trên `StrategyEngine` **của riêng nó** (1 instance/key,
  giống `IndicatorScriptRunner.ActiveScript` per key) — bật nhiều strategy
  cùng lúc bị chặn bởi rule mutually-exclusive-với-indicator, nhưng bản thân
  nhiều strategy bật cùng lúc (nếu sau này rule đổi) không cần đổi thiết kế
  `StrategyRunner`, vì nó vốn đã lặp qua tất cả các key đang bật.
- Vì mutually-exclusive với Indicator: khi user bật Strategy, cần đảm bảo
  `_rebuild_scripts()` không cố feed cả 2 runner cùng lúc — tránh lãng phí
  CPU tính indicator scripts đã bị tắt (dù `_script_runner` có kiểm tra
  enabled list trước khi feed, review lại logic hiện có trước khi thêm
  runner thứ 2 để tránh trùng lặp).
