# ❌ ĐÃ HUỶ — BOT-039: Dev Board — Strategy Toggle List + Buy/Sell Markers

> **Trạng thái: HUỶ (2026-09-23), phát hiện qua rà soát backlog cho batch kế tiếp — không phải quyết định user có sẵn từ trước (khác tiền lệ `BOT-023`).**
> Giá trị thật task này theo đuổi — thấy hoạt động chiến lược lúc Live streaming, là subscriber thật đầu tiên của `SignalGeneratedEvent`, mở seam cho `BOT-008` — **đã đạt được**, bằng một thiết kế hoàn toàn khác: `StrategyArmingCoordinator` + `SignalFeed` (`EPIC-022D`/`EPIC-022E`/`EPIC-023A`–`D`).
> Nội dung gốc giữ nguyên bên dưới **chỉ để tham khảo lịch sử** — đừng thực hiện nó.

## Vì sao huỷ

Rà soát backlog cho batch tiếp theo (sau `BOT-115B`/`BOT-106D`/`BOT-025`/`BUG-133`)
xác nhận **cả 2 tiền đề load-bearing của task này đều sai** khi đọc thẳng code
hiện tại — không phải giả định mơ hồ:

1. **Control cosmetic "đã bị xoá, không wire lại" — nhưng không phải theo cách
   task này định làm.** `grep -rn "cboStrategy\|DevBoardPanel.qml" src/` ra
   rỗng: không chỉ combo đó, mà **toàn bộ `DevBoardPanel.qml`** đã biến mất
   cùng mọi file `.qml` khác (`EPIC-025` gỡ QML hoàn toàn, xác nhận lại lần
   nữa trong `BOT-025`/batch trước). Task này viết cho một tầng trình bày
   (QML) không còn tồn tại.
2. **`SignalGeneratedEvent` "chưa ai lắng nghe" — nay có ít nhất 6 subscriber
   thật:** `dashboard_presenter.py` (`_arming_coordinator.on_signal_generated`
   qua `SignalFeed`), `strategy_card_view_model.py`, `trading_presenter.py`,
   `strategy_arming_coordinator.py`, `live_trading_coordinator.py`,
   `backtest_presenter.py`/`signal_wiring.py` (đường Backtest, khác mục
   đích). Grep xác nhận trực tiếp, không suy đoán.

Sâu hơn 2 điểm trên: **mục tiêu thật của task** ("thấy signal khi đang live
streaming", "subscriber đầu tiên thật sự của `SignalGeneratedEvent`", "mở seam
cho `BOT-008`") **đã đạt được — bằng một kiến trúc khác hẳn**, ra đời sau khi
task này được viết:

- `EPIC-023C` thay hẳn combo giả bằng thẻ "Nạp chiến lược" thật
  (`dev_board_panel.py::_build_strategy_card`), nối `StrategyArmingCoordinator`
  — **1 strategy được "arm" tại 1 thời điểm**, mirror y hệt `TradingView`, chứ
  không phải danh sách checkbox bật/tắt nhiều strategy cùng lúc mà task này đề
  xuất.
- `SignalFeed` (`EPIC-023C`, cùng shared-bus pattern với `SyncProgressFeed`/
  `OrderFeed`/`EquityFeed`) là subscriber `SignalGeneratedEvent` chuẩn hoá, nối
  thẳng `_arming_coordinator.on_signal_generated`.
- Marker trên chart lúc Live đã có, nhưng qua đường khác: `EPIC-021K`/`EPIC-023A`
  vẽ marker khớp lệnh thật (`_on_order_filled` → `card.set_script_markers(_FILL_MARKERS_KEY, ...)`)
  — tín hiệu **đã khớp lệnh**, không phải tín hiệu thô task này định vẽ (mà
  chính task cũng tự ghi chú "không dùng `PaperExchange`, chỉ hiển thị tín
  hiệu thô" — một lớp thông tin khác, thấp giá trị hơn khớp lệnh thật đã có).

**Xây đúng như task này mô tả bây giờ sẽ là làm việc thừa và xung đột kiến
trúc**, không phải hoàn thành nốt phần còn thiếu: mô hình "nhiều strategy bật
đồng thời qua checkbox" ngược hẳn với mô hình "arm đúng 1 strategy" mà
`EPIC-022`/`EPIC-023` đã chốt và app đang chạy thật theo đó.

## Hệ quả cần biết

- Không có code nào của task này từng được viết — không có gì phải dọn/xoá,
  khác `BOT-023` (code Dynamic backtest cũ còn sống, phải dọn riêng).
- `TC-GAP-04` (`Tasks/reports/dev_board_user_end_test_cases.md`) đã cập nhật:
  đánh dấu FIXED bởi `EPIC-023C`, không phải bởi task này, và trỏ sang hồ sơ
  huỷ này thay vì trỏ vào backlog `BOT-039` không còn ý nghĩa.
- Nếu sau này thật sự cần "xem tín hiệu thô của nhiều strategy cùng lúc,
  không qua PaperExchange" như một tính năng riêng (khác khớp lệnh thật) —
  đó là một task mới, thiết kế lại từ đầu trên nền `SignalFeed`/
  `StrategyArmingCoordinator` đã có, không phải khôi phục nội dung dưới đây.

---

## (Nội dung gốc, chỉ để tham khảo lịch sử — KHÔNG thực hiện)

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
