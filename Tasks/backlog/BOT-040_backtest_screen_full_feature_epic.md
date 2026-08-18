# Epic: Backtest Screen — Full Feature Set (TradingView Strategy Tester Parity)

> Phụ thuộc [Epic BOT-006](BOT-006_backtest_engine_execution.md) — cụ thể là
> `BOT-021` ✅ (Static engine, đã xong) và [`BOT-076`](BOT-076_realtime_backtest_engine.md)
> (Realtime engine, chưa làm — thay cho `BOT-023` [đã huỷ 2026-08-18](../cancelled/BOT-023_dynamic_backtest_engine.md)). **Supersede** `BOT-022`/`BOT-024` — 2 task đó không bị xoá, chỉ được
> mở rộng scope trực tiếp trong chính file của chúng để bám theo spec đầy đủ
> ở đây, tránh làm 2 lần (bản "rút gọn" trước rồi làm lại bản "đầy đủ" sau).

## 1. Mục tiêu

User cung cấp 1 spec đầy đủ cho màn hình Backtest (4 khu vực: Top Toolbar,
Performance Metrics Panel, Chart Canvas, Trade Logs Table) — chi tiết hơn hẳn
scope gốc của `BOT-022`. Epic này ghi lại **toàn bộ** spec đó, đối chiếu với
code đã có (`BOT-021`: `PaperExchange`/`Trade`/`BacktestResult`/
`BacktestMetrics`, `BOT-026`: `StrategyRegistry`), và tách rõ 3 nhóm:

1. **Làm được ngay** — dữ liệu/hạ tầng đã có sẵn, chỉ còn nối UI.
2. **Cần task riêng trước** — thiếu hẳn 1 khả năng ở tầng engine/domain,
   không thể giả vờ có trong lúc làm UI.
3. **Chưa đủ rõ để bắt đầu** — cần user chốt thêm trước khi viết action item
   cụ thể (không đoán).

## 2. Đối chiếu spec ↔ code hiện có

### 2.1 Top Toolbar

| Mục trong spec | Trạng thái | Ghi chú |
| :--- | :--- | :--- |
| Dropdown chọn chiến lược | ✅ Làm được ngay | `StrategyRegistry.available()` đã có. Chỉ có 1 entry thật (`ema_crossover`) hiện tại — dropdown sẽ ngắn cho tới khi `BOT-043` thêm chiến lược. |
| Layout 1 cửa sổ / 2 biểu đồ / lưới | ⚠️ 1 cửa sổ làm trước, 2/lưới hoãn | Việc UI thuần, không phụ thuộc engine — nhưng nhiều `ChartCard` cùng lúc là khối lượng việc riêng, không phải "1 dòng code". Đề xuất: chỉ làm layout 1 cửa sổ ở `BOT-022`, 2 cửa sổ/lưới để task riêng sau nếu thực sự cần. |
| Khung thời gian test (7/30/90/365 ngày, toàn bộ, tuỳ chỉnh) | ✅ Làm được ngay | Map thẳng vào `RunStaticBacktestCommand.start_time`/`end_time` đã có sẵn — UI chỉ cần tính ngày từ preset. |
| Vốn ban đầu + đơn vị tiền tệ | ✅ Làm được ngay (đơn vị chỉ là nhãn) | `RunStaticBacktestCommand.initial_balance` đã có. Toàn bộ hệ thống ngầm định USDT-pair nên "đơn vị tiền tệ" chỉ là text hiển thị, không có multi-currency thật. |
| Timeframe | ✅ Làm được ngay | `RunStaticBacktestCommand.interval` đã có. |
| Execution Trigger Rules — **On bar close** | ✅ Đã là hành vi mặc định | `RunStaticBacktestCommandHandler` hiện tại luôn chạy theo bar close. |
| Execution Trigger Rules — **On historical/realtime bar tick** | ❌ Cần `BOT-042` → nay thuộc [Epic `BOT-073`](BOT-073_realtime_tick_backtest_epic.md) | `StrategyEngine`/`IIndicator` hiện chỉ nhận 1 giá trị đóng nến/lần gọi (`update(value: float)`) — không có khái niệm "giữa nến". User tự làm phần nạp dữ liệu tick 1s; `BOT-042` là phần engine cần để *dùng* được dữ liệu đó. **Đã chốt hướng (b)** (indicator tính lại mỗi tick) — xem `BOT-042` §4. |
| Execution Trigger Rules — **On order filled** | ✅ Đã rõ nghĩa → [`BOT-077`](BOT-077_calc_on_order_fills.md) | ~~Chưa rõ nghĩa trong ngữ cảnh backtest~~ — user đã giải thích: đây là **`calc_on_order_fills = true`** của Pine Script (chạy lại tập lệnh ngay khoảnh khắc lệnh khớp, không chờ đóng nến). Nhận định "chưa rõ nghĩa" lúc đó **đúng với hoàn cảnh** — nó thật sự chỉ có nghĩa khi đã có tick data, nên `BOT-077` chặn bởi `BOT-076`. ⚠️ **Không phải** cách giải quyết vấn đề an toàn SL — đó là `BOT-041`; xem `BOT-077` §2. |
| **Bot Parameters Modal — cơ chế khai báo tham số** | ❌ Cần `BOT-044` | **Không có hệ thống tham số nào cả.** Modal phải dựng form **động** từ khai báo của từng strategy/indicator (kiểu `input()` Pine Script), không hardcode field. ⚠️ Đây là **đảo ngược quyết định `BOT-032` §9.1** ("không cần runtime input" → đã bỏ spinbox, thay bằng 6 script cố định period). Xem `BOT-044` mục 2. |
| Bot Parameters Modal — SL %/TP %/Leverage/Risk % mỗi lệnh | ❌ Cần `BOT-041` + `BOT-044` | `PaperExchange` (BOT-021) hiện là spot, all-in, không SL/TP/leverage. Ngoài ra 4 field này thuộc **exchange config**, không phải strategy — cần chốt cách ghép 2 nguồn schema vào 1 modal (`BOT-044` mục 3.3). |
| Bot Parameters Modal — EMA Fast/Slow period | ❌ Cần `BOT-044` | `EmaCrossoverStrategy(fast_period, slow_period)` đã nhận tham số ở constructor, nhưng `StrategyRegistry.create(key)` không nhận `params` (khác `IndicatorScriptRegistry` đã chừa sẵn) **và** không có cách nào để UI biết chiến lược này có 2 tham số tên gì, kiểu gì, default bao nhiêu. Cần schema, không chỉ là chỗ nối `params`. |
| Bot Parameters Modal — QML Pattern Sensitivity % | ❌ Cần `BOT-043` + `BOT-044` | Chưa có chiến lược "QML" nào tồn tại để có tham số này. |
| Reset mặc định / Lưu & Re-backtest | ✅ Làm được ngay | UI thuần, gọi lại `RunStaticBacktestCommand` với input mới. |
| **AI Chẩn đoán** | ❓ Chưa đủ rõ để bắt đầu | Xem mục 3 — cần user chốt trước khi có action item. |
| Nút Chạy Backtest | ✅ Đã có sẵn | Dispatch `RunStaticBacktestCommand` — handler đã hoàn thiện ở `BOT-021`. |

### 2.2 Performance Metrics Panel

| Mục trong spec | Trạng thái |
| :--- | :--- |
| Net PnL (số tiền + %) | ✅ `BacktestMetrics.net_profit`/`net_profit_percent` |
| Max Drawdown (số tiền + %) | ⚠️ Chỉ có %. `max_drawdown_percent` đã có; số tiền tuyệt đối tại đáy drawdown chưa expose riêng — việc nhỏ nếu cần, làm trong `BOT-022` (tính lại từ `equity_curve` khi hiển thị, không cần sửa `BacktestMetrics`). |
| Win Rate (% + số lệnh thắng/tổng) | ✅ `percent_profitable` (%); số lệnh thắng/tổng đếm trực tiếp từ `result.trades` ở UI, không cần sửa engine. |
| Profit Factor | ✅ `BacktestMetrics.profit_factor` |
| Mở rộng: Sharpe / Sortino / Payoff ratio | ❌ Cần quyết định công thức trước | Sharpe/Sortino cần chuỗi return theo kỳ (daily? per-trade?) + risk-free rate giả định — chưa có trong `BacktestMetrics` (chỉ có 13 metric hiện tại). Việc nhỏ về code nhưng cần chốt công thức trước khi thêm field, tránh tính sai rồi phải sửa lại. Để trong `BOT-022`'s action items dưới dạng "mở rộng `BacktestMetrics`", KHÔNG tự chọn công thức khi code — hỏi lại nếu tới lúc làm. |

### 2.3 Chart Canvas

| Mục trong spec | Trạng thái |
| :--- | :--- |
| Nến Nhật (OHLC) | ✅ `ChartCard` đã có (`BOT-005`/`009`/`010`) |
| Đường Equity | ⚠️ Cần 1 chế độ vẽ mới | `BacktestResult.equity_curve` (`list[(datetime, float)]`) đã có đủ dữ liệu (kể cả `initial_balance`/`final_balance` cho header "Vốn đầu → Vốn cuối") — cần thêm 1 line-mode cho `ChartCard` hoặc 1 view riêng, việc UI thuần. Mockup còn có chấm tròn tại mỗi lệnh (đỏ/xanh theo lãi/lỗ) — lấy từ `BacktestResult.trades`. |
| Chế độ "Song song (Cả 2)" — OHLC + Equity cùng lúc | ⚠️ UI thuần | 2 panel chồng dọc chia sẻ trục thời gian. `ChartCard` đã có cơ chế subplot (dùng cho MACD ở `BOT-032`) — nhiều khả năng tái sử dụng được, cần kiểm tra khi làm. |
| Toggle 4 EMA | ✅ Hạ tầng đã có | Indicator script `ema_cross`/`ema_ribbon` (BOT-032) đã vẽ EMA qua `self.plot()`. Lưu ý: EMA hiển thị hiện tại là của **indicator script**, không nhất thiết cùng period với EMA **strategy** đang backtest — cần đồng bộ period khi làm UI (không phải gap kiến trúc, chỉ là chi tiết cần để ý). |
| QML Signal Badges | ❌ Cần `BOT-043` | Không có chiến lược QML nào tồn tại. |
| Buy/Sell Flags (LONG/SHORT tại điểm vào lệnh) | ⚠️ Làm được ngay cho LONG; SHORT cần `BOT-050` | Nguồn dữ liệu là `BacktestResult.trades` (đã có `entry_time`/`entry_price`) — vẽ marker qua `set_script_markers` sẵn có (BOT-032). `EmaCrossoverStrategy` hiện chỉ long-only nên sẽ không bao giờ có nhãn SHORT cho tới khi có short-capable strategy/exchange. |
| Toggle Volume | ✅ Đã có (`BOT-009`) |
| Crosshair (OHLC theo con trỏ) + Zoom/Reset | ✅ Đã có (`BOT-009`/`010`) |

### 2.4 Trade Logs Table

| Mục trong spec | Trạng thái |
| :--- | :--- |
| Tab lọc Tất cả/LONG/SHORT/Thắng/Thua | ⚠️ LONG/Thắng/Thua làm được ngay; SHORT luôn rỗng cho tới `BOT-050` |
| Tìm kiếm theo mã lệnh/ngày | ✅ Làm được ngay (lọc `list[Trade]` ở UI) |
| Export | ✅ Làm được ngay (CSV từ `list[Trade]`) |
| STT / mã lệnh | ✅ Đánh số thứ tự ở UI — `Trade` không cần thêm field `id` (không có ý nghĩa nghiệp vụ, chỉ để hiển thị) |
| Loại (Long/Short, Vào/Thoát) | ⚠️ Giống mục SHORT ở trên |
| Ngày giờ vào/ra | ✅ `Trade.entry_time`/`exit_time` |
| Giá vào/thoát | ✅ `Trade.entry_price`/`exit_price` |
| Quy mô (số lượng + USD) | ✅ `Trade.quantity`; giá trị USD tính ở UI = `quantity * entry_price` |
| Lãi/lỗ ròng | ✅ `Trade.pnl` |
| Return % | ✅ `Trade.pnl_percent` |
| Phân trang | ✅ Làm được ngay (UI thuần, `QTableView`) |
| **Dòng mở rộng: Lý do vào lệnh / Lý do thoát lệnh** | ❌ Cần `BOT-045` | `Signal.reason` **đã có sẵn** (BOT-026) nhưng `PaperExchange` vứt bỏ khi dựng `Trade`; và chưa có khái niệm "lý do thoát" (tín hiệu / SL / TP / thanh lý / hết dữ liệu). |
| **Dòng mở rộng: chỉ số riêng theo chiến lược** (vd "QML Signal Score 92/100") | ❌ Cần `BOT-045` (+ `BOT-043` cho chỉ số QML thật) | `Signal` không có chỗ cho metadata mở rộng. User nêu rõ *"tùy vào chiến thuật"* → phải là dict mở, không phải cột cố định. |
| Dòng mở rộng: Thời lượng lệnh ("4h 00m") | ✅ Tính được ngay | `exit_time - entry_time`, không cần field mới. |

## 3. Chưa đủ rõ — cần user chốt trước khi có action item

- **AI Chẩn đoán**: spec chỉ ghi "Nút phân tích và đánh giá chất lượng chiến
  lược bằng AI" — chưa rõ: dùng model nào (gọi API ngoài? heuristic nội bộ
  không phải AI thật?), input là gì (toàn bộ `BacktestResult`? chỉ metrics?),
  output kỳ vọng là gì (text nhận xét? điểm số? gợi ý chỉnh tham số?). Đây là
  quyết định có ảnh hưởng chi phí/hạ tầng thật (gọi API ngoài tốn phí, cần
  API key, cần quyết định nhà cung cấp) — **không đoán**, để trống trong epic
  này, tách task riêng sau khi chốt.
- **"On order filled" trigger**: xem bảng 2.1.

## 4. Sơ đồ Phase

Các task đã được **chia nhỏ** (theo yêu cầu user) thành 4 nhóm. Trong mỗi
nhóm, thứ tự liệt kê là thứ tự làm khuyến nghị.

### Nhóm A — Hệ thống tham số (chặn nhiều nhất, ưu tiên cao nhất)

| Task | Mô tả ngắn |
| :--- | :--- |
| [`BOT-044`](../completed/BOT-044_param_schema_core.md) | **Param Schema Core** — value object + API `input_int/float/bool/string()` trên `BaseIndicatorScript`, cơ chế 2 pha (khai báo → đọc schema → tạo lại với params). ⚠️ Đảo ngược `BOT-032` §9.1. |
| [`BOT-046`](../completed/BOT-046_strategy_param_plumbing.md) | Mang cơ chế đó sang `BaseStrategy` + nối `StrategyRegistry.create(params)` / `build_engine(params)`. |
| [`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md) | Modal "Cấu hình Thông số Bot" dựng form **động** từ schema (4 kiểu widget, nhóm field, "Khôi phục Mặc định", "Lưu & Re-Backtest"). |
| [`BOT-048`](../completed/BOT-048_migrate_default_scripts_to_inputs.md) | Chuyển 6 script mặc định sang khai báo period bằng input (**giữ nguyên cả 6**, default 20/50/100/200/14 — user đã chốt). |

### Nhóm B — PaperExchange nâng cao

| Task | Mô tả ngắn |
| :--- | :--- |
| [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md) | **Trade Journal Detail** — lý do vào/thoát + metadata theo chiến lược. Làm **trước** `BOT-041` để SL/TP có sẵn chỗ ghi `exit_reason`. |
| [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) | SL/TP tự đóng vị thế + position sizing theo % rủi ro (2 cái không tách rời: sizing cần biết SL). |
| [`BOT-049`](BOT-049_leverage_and_liquidation.md) | Đòn bẩy + **thanh lý**. Rủi ro sai số cao nhất Epic — bắt buộc đối chiếu nguồn ngoài. |
| [`BOT-050`](BOT-050_short_selling_support.md) | Short-selling. Task duy nhất **đổi hành vi đã có test pin**. |

### Nhóm C — Chiến lược ([`BOT-043`](BOT-043_named_strategy_library.md) là chỉ mục)

| Task | Độ khó | Mô tả ngắn |
| :--- | :---: | :--- |
| [`BOT-051`](../completed/BOT-051_multi_ema_trend_follower.md) | Thấp | Multi-EMA Trend Follower — mở rộng từ `EmaCrossoverStrategy`. |
| [`BOT-052`](BOT-052_four_ema_pullback_sideways_filter.md) | Trung bình | 4 EMA Pullback + Sideways Filter — cần định nghĩa "sideways" bằng số liệu. |
| [`BOT-053`](BOT-053_qml_structure_breakout.md) | Cao | QML Structure Breakout — nhận diện price-action pattern, sinh "QML Score". |

> ⏸️ **SMC + Liquidity Sweep đã bỏ khỏi phạm vi** (user quyết định) — ghi chú
> đầy đủ để cân nhắc lại sau nằm ở
> [`BOT-043`](BOT-043_named_strategy_library.md) mục 2.
> Hai hạ tầng còn thiếu cho mọi chiến lược phân tích cấu trúc giá (swing
> high/low detection; `Series` mặc định chỉ giữ **16 bar**) ghi ở `BOT-043`
> mục 3.

### Nhóm D — Màn hình Backtest (Phase 1-2)

| Task | Mô tả ngắn |
| :--- | :--- |
| ✅ [`BOT-022`](../completed/BOT-022_backtest_screen_static_ui.md) | Khung màn hình + Top Toolbar + nút Chạy Backtest. Sau task này màn hình đã **chạy được thật**. |
| ✅ [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md) | Performance Metrics Panel (4 stat card + mở rộng). |
| ✅ [`BOT-056`](../completed/BOT-056_backtest_chart_canvas.md) | Chart Canvas — 3 chế độ (OHLC / Equity / Song song) + overlays. |
| [`BOT-057`](../completed/BOT-057_backtest_trade_logs_table.md) | Trade Logs Table + dòng mở rộng chi tiết. |
| [`BOT-024`](BOT-024_backtest_screen_dynamic_ui.md) | Phase 2 — kế thừa toàn bộ UI trên + replay controls, sau khi [`BOT-076`](BOT-076_realtime_backtest_engine.md) xong (`BOT-023` đã huỷ). |

### Ngoài nhóm

| Task | Mô tả ngắn |
| :--- | :--- |
| [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md) | Tick-level support — chặn 2/4 Execution Trigger Rule. **Chưa có action item**, còn 1 câu hỏi kiến trúc chưa chốt. |

## 5. Lưu ý

- Không làm hết Nhóm B/C "cho đủ bộ" trước khi có nhu cầu thật — Nhóm D
  (`BOT-022`…`BOT-057`) vẫn có giá trị đứng một mình với phần ✅/⚠️ (đây đã là
  gần hết spec). Ưu tiên theo nhu cầu thật của user, không tự suy diễn thứ tự.
- **Đường ngắn nhất tới một màn Backtest dùng được**: `BOT-022` ✅ → `BOT-055` ✅ →
  `BOT-056` ✅ → `BOT-057` (2.1). Không cần Nhóm A/B/C nào cả. Nhóm A (`BOT-044`…)
  là thứ mở khoá nhiều tính năng nhất tiếp theo.
- `BOT-042` (tick-level) là phần **engine tiêu thụ** dữ liệu — việc **nạp**
  dữ liệu tick 1s (Binance API, lưu trữ, sharding...) do user tự làm, ngoài
  phạm vi task này. Khi user có dữ liệu tick thật, quay lại `BOT-042` để
  thiết kế chi tiết cách `StrategyEngine` dùng nó (mỗi tick gọi lại
  `decide()`? hay chỉ indicator cập nhật mỗi tick còn strategy vẫn chỉ quyết
  định ở bar close? — câu hỏi mở, chưa chốt).
- Nhóm B tách 3 task theo đúng ranh giới cơ chế: SL/TP + sizing
  (`BOT-041`) → đòn bẩy + thanh lý (`BOT-049`) → short (`BOT-050`). Chúng
  **cùng thuộc một lớp thiết kế `PaperExchange`** nên nếu làm liền tay có thể
  gộp — nhưng tách ra để mỗi phần có test tính tay riêng, vì đây là vùng tính
  toán tài chính dễ sai và sai thì im lặng.
