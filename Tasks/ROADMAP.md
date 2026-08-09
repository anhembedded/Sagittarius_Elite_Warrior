# 🗺️ Project Roadmap & Task Board

> [!NOTE]
> Bảng quản lý lộ trình phát triển và tiến độ công việc của dự án **Binance Trading Bot** theo mô hình **Kanban Board**.

---

## 📂 Thư mục Quản lý Task

```text
Binace_Bot/Tasks/
├── 🟢 completed/   # Các nhiệm vụ đã hoàn thành và qua kiểm thử (Passed 100% Tests)
├── 🟡 in_progress/ # Các nhiệm vụ đang thực hiện trong Sprint hiện tại
├── 🔴 backlog/     # Các nhiệm vụ chờ ưu tiên triển khai
└── 📄 reports/     # Các báo cáo phân tích & kiểm thử (Audit Reports)
```

---

## 📊 Tổng quan Tiến độ (Sprint Status)

| Trạng thái | Số lượng Task | Tỷ lệ |
| :--- | :---: | :---: |
| 🟢 **Completed** | 16 | 53% |
| 🟡 **In Progress** | 1 | 3% |
| 🔴 **Backlog** | 13 | 44% |
| 📈 **Tổng số Task** | **30** | **100%** |

---

## 📋 Bảng Quản lý Nhiệm vụ (Task Board)

### 🟢 Completed (Đã hoàn thành)

- [x] **BOT-001**: [Data Synchronizer](completed/BOT-001_data_synchronizer.md) — *Đồng bộ dữ liệu nến lịch sử Binance vào SQLite Sharding.*
- [x] **BOT-002**: [UI Dashboard](completed/BOT-002_ui_dashboard.md) — *Khung giao diện chính với PySide6 & CQRS Pipeline.*
- [x] **BOT-004**: [Data Management Screen](completed/BOT-004_data_management_screen.md) — *Màn hình quét DB và xem trạng thái dữ liệu.*
- [x] **BOT-005**: [Live Charting](completed/BOT-005_live_charting.md) — *Vẽ biểu đồ nến real-time qua Binance WebSocket Stream.*
- [x] **BOT-007**: [UI Theme, Font & Layout Config](completed/BOT-007_ui_theme_config_optimization.md) — *(một phần)* 3/4 mục đã có sẵn từ đợt refactor trước; hoãn có chủ đích việc đổi sang `QGridLayout` (chưa có sub-card cụ thể để thiết kế theo).
- [x] **BOT-009**: [TradingView Chart — Tier 1 Core UX](completed/BOT-009_chart_tradingview_tier1_ux.md) — *Volume bars, Last price line, OHLC info box, Auto-follow ("⏩ Live"), Toggle/Remove indicator & Subplot legend.*
- [x] **BOT-010**: [TradingView Chart — Tier 2 Toolbar](completed/BOT-010_chart_tradingview_tier2_chrome.md) — *(một phần)* Chart type switcher (Candlestick/Line/Area/Heikin Ashi) & Timeframe toolbar UI; hoãn Trade Markers Manager (chưa có `OrderFilledEvent` thật để lắng nghe).
- [x] **BOT-012**: [Application Layer SOLID Refactoring](completed/BOT-012_application_solid_refactoring.md) — *Sửa vi phạm DIP ở BulkSync handler (dùng `IDispatcher`), loại bỏ Primitive Obsession cho `get_database_status` (`DatabaseStatusSnapshot`/`DatabaseStatusDTO`).*
- [x] **BOT-013**: [Infrastructure Layer SOLID Refactoring](completed/BOT-013_infrastructure_solid_refactoring.md) — *Tách helper cho Repository (mapping & UPSERT), DI cho Binance Client, tách `_run_stream()` WebSocket thành các hàm con.*
- [x] **BOT-014**: [Dev Board Single Chart Config](completed/BOT-014_dev_board_single_chart.md) — *Chuyển Dashboard thành Dev Board, đổi mặc định sang 1 chart `ETHUSDT` & cập nhật test suites.*
- [x] **BOT-015**: [QA & Testing Strategy Audit](completed/BOT-015_qa_testing_strategy_audit.md) — *(một phần)* Thêm tầng `tests/sanity/`, testing guidelines, cờ `-SanityOnly`/`-UnitOnly`/`-Full` + `--cov-fail-under=80` cho `ci-local.ps1`. 📄 [Báo cáo Audit](reports/qa_testing_strategy_report.md). Hoãn Concurrency/Thread-Safety tests.
- [x] **BOT-016**: [UI Icon Pack & Assets Management](completed/BOT-016_ui_icon_pack_integration.md) — *Tích hợp Lucide Icons (SVG) vào Sidebar/ControlCard/MonitorCard qua `IconLoader` (cache, recolor, fallback).*
- [x] **BOT-020**: [Indicator & Strategy Engine (Core)](completed/BOT-020_indicator_strategy_engine_core.md) — *Epic `BOT-006` Phase 0. `IIndicator`/`RSI`/`EMA`/`MACD` + `IStrategy`/`StrategyEngine` (batch & incremental, cùng 1 code path đảm bảo 2 chế độ luôn khớp kết quả). Nền tảng dùng chung cho `BOT-008`/`BOT-021`/`BOT-023`.*
- [x] **BOT-028**: [QML Hybrid Prototype Spike — Settings Screen](completed/BOT-028_qml_hybrid_prototype_spike.md) — *Kiểm chứng khả thi Hybrid (giữ `ChartCard`/pyqtgraph, phần còn lại chuyển QML qua `QQuickWidget`). Kết quả chính: `QQuickWidget` render đúng dưới `QT_QPA_PLATFORM=offscreen`, `PresenterManager` KHÔNG cần sửa gì để host QML. Chưa rút abstraction vào `pyside_mvc` (đợi màn hình QML thứ 2).*
- [x] **BOT-029**: [UI Restyle — Theme "Sagittarius Elite Warrior"](completed/BOT-029_ui_restyle_sagittarius_theme.md) — *Đổi giao diện đen+gold theo mockup, branding "Sagittarius Elite Warrior". Phase 1-2 (theme/branding/sidebar/Dev Board top bar) + Phase 4 (đảo QML→Widgets cho Settings) xong bằng QtWidgets. Phase 3 (restyle Database) **supersede bởi `BOT-030`** — thiết kế gộp thẳng vào bản QML thay vì làm 2 lần.*
- [x] **BOT-030**: [Full QML Migration (chart giữ QtWidgets)](completed/BOT-030_full_qml_migration.md) — *Chuyển toàn bộ UI sang QML trừ `ChartCard` — lý do là AI dịch mockup→code trực tiếp hơn ở QML (không phải hiệu năng — bug pan giật đã tìm ra và sửa xong ở Widgets, thuần thuật toán, đảo ngược quyết định QML→Widgets của `BOT-029` Phase 4). 5 phase: nền tảng QML dùng chung → Sidebar → Settings → Database → Dev Board (hybrid `QSplitter` + `ChartCard`) → dọn dẹp (`ui_matrix.json`, dead code). `ci-local.ps1 -Full`: 283 passed, 2 xfailed, coverage 92.31%. Chưa promote hạ tầng QML vào `pyside_mvc` — chỉ 1 app dùng, đợi consumer thứ 2 thật sự.*
- [x] **BOT-032**: [Custom Indicator Scripts (kiểu Pine Script, thuần Python)](completed/BOT-032_custom_indicator_scripts.md) — *Tự viết indicator bằng 1 class Python thường (`setup()` khai báo, `execute()` gọi `self.plot()`/`self.mark()`/`self.shade()`/`self.info()`), không tạo DSL mới, tự hiện trong UI khi đăng ký. Domain (`BaseIndicatorScript` đầy đủ primitive + `domain/scripting/` dùng chung cho strategy sau này) + registry + 9 script (`rsi_14`/`ema_20`/`ema_50`/`ema_100`/`ema_200`/`macd_full`/`ema_ribbon`/`ema_cross`/`dev_showcase`) + Presenter/Runner vẽ line/tint/status-panel/marker lên `ChartCard` thật + UI bật/tắt (`IndicatorScriptListModel` + `default_enabled`) + docs (`ui_architecture.md` §11). **Phase 6: không còn indicator nào hardcode trong engine** — RSI/EMA/MACD hardcode cũ đã xoá hẳn khỏi `dashboard_presenter.py`/`dashboard_view_model.py`/QML, thay bằng 6 script cố định-period (không dùng runtime params, theo đúng quyết định "không cần runtime input"); EMA 20/50/100/200 mặc định bật sẵn (US-07). 378 unit + 6 sanity + 43 integration test, tất cả pass, ruff sạch. **Còn 2 mục Phase 4 cố ý bỏ qua** (màu đổi theo bar, `fill()`) — rủi ro cao vì đụng `IndicatorManager` dùng chung với mọi indicator, để task riêng có review.*
- [x] **BOT-034**: [Dev Board — Auto-start Live, Render-window tách Fetch-amount, Timeframe thật](completed/BOT-034_dev_board_autostart_and_data_lifecycle.md) — *Đóng 3 gap đã biết (TC-GAP-03/06/08). §6: nối `ChartToolbar.sig_timeframe_changed` thay `cboTimeframe` cosmetic — đổi timeframe giữa lúc LIVE thì dừng/load lại/start lại theo timeframe mới. §4: tách "75 nến render" khỏi "bao nhiêu nến cần tải" — `_compute_fetch_limit()` = max(render window, `min_warmup_bars` lớn nhất trong script đang bật, floor từ config `DEV_BOARD_MIN_FETCH_CANDLES`, default 75). §5: `AutoStartController` (file riêng) tự bấm Start Live ngay khi mở Dev Board, fallback sang Load History nếu không có `MarketTickEvent` nào trong `DEV_BOARD_AUTOSTART_FALLBACK_SECONDS` giây (default 2.0, đọc từ config) — dùng `CancellationToken` có sẵn của Sagittarius để dừng việc nền khi user bấm Stop hoặc app thoát (KHÔNG cancel khi đổi tab/navigate away, theo đúng yêu cầu user). Đường đi tới bản pass sạch phải sửa 1 crash C++ thật (Windows access violation) do 3 nguyên nhân riêng biệt cộng dồn — xem §9 trong task file để root-cause đầy đủ, bài học chính: không `qtbot.waitSignal()` trên tín hiệu bắn nhiều lần liên tiếp từ background thread. 396 unit + 29 integration test pass sạch, chạy lại nhiều lần không flaky.*

---

### 🟡 In Progress (Đang thực hiện)

- [ ] **BOT-033**: [Hoàn thiện thao tác người dùng trên QML](in_progress/BOT-033_qml_user_actions.md) — *Biến các control tĩnh trên QML (Symbol/Timeframe/Date range/Market/Strategy...) thành thao tác có hiệu lực. Phase 1 (an toàn thao tác bất đồng bộ, chặn Load History chạy chồng) đã xong. Phase 2 (nối Symbol/Timeframe/Date range) — mục timeframe/ChartToolbar đã được hoàn thành từ phía `BOT-034` (task chạy song song, xem cross-reference trong file). Phase 3 chờ quyết định sản phẩm (Market/Strategy/Settings persistence).*

---

### 🔴 Backlog (Danh sách Ưu tiên & Phụ thuộc)

| Priority | Task ID | Tên Nhiệm vụ | Dependencies | Mô tả ngắn |
| :---: | :--- | :--- | :---: | :--- |
| **P1** | **[BOT-008](backlog/BOT-008_live_trading_strategy_execution.md)** | **Live Trading Strategy Execution** | `BOT-001` ✅, `BOT-005` ✅ | Tính toán chỉ báo (RSI, EMA, MACD) từ Live Stream & phát tín hiệu đặt lệnh qua Binance API. Sẵn sàng bắt đầu — mọi phụ thuộc đã hoàn thành. |
| **P1** | **[BOT-027](backlog/BOT-027_fix_concurrent_load_history_race_condition.md)** | **Fix Race Condition — "Load History" click chồng** | `BOT-020` ✅ | Bấm "Load History" ≥2 lần liên tiếp làm dữ liệu nến bị feed 2 lần vào cùng bộ indicator (RSI/EMA/MACD sai số liệu) — đã tái hiện bằng test thật (`xfail` có chủ đích) trong `test_dev_board_async_race_conditions.py`. 📄 [Test Case Catalog](reports/dev_board_user_end_test_cases.md). |
| **P2** | **[BOT-035](backlog/BOT-035_dev_board_load_more_on_scroll.md)** | **Dev Board — Tự tải thêm dữ liệu cũ khi kéo ra rìa trái chart (US-04)** | `BOT-034` ✅ | Kéo/scroll chart ra rìa trái dữ liệu đã tải hiện không làm gì — chart chỉ trống. Query/repository layer đã hỗ trợ sẵn (`GetHistoricalKlinesQuery.end_time`), việc còn lại là: detect gần rìa trái (`ViewportController`, chưa có hook), `ChartCard.prepend_historical_data()` mới (không phá zoom hiện tại, khác `render_historical_data`), và full rebuild+refeed cho `IndicatorScriptRunner` (không có đường "feed lùi" — đã verify). **Còn 3 câu hỏi mở** (ngưỡng trigger, số nến/lần, có tự sync từ Binance khi DB thiếu hay không) — chưa code, chờ user chốt. |
| **P2** | **[BOT-026](backlog/BOT-026_dev_board_strategy_signals_and_markers.md)** | **Dev Board — Concrete Strategy + Buy/Sell Markers** | `BOT-020` ✅ | Chiến lược cụ thể đầu tiên (vd. EMA Crossover) dùng `StrategyEngine`, hiển thị tín hiệu Buy/Sell trên Dev Board (log + marker trên chart). Nối tiếp Indicator Control Card, chủ động hoãn từ phiên làm indicator ("chưa cần strategy bây giờ"). |
| **P2** | **[BOT-017](backlog/BOT-017_settings_screen.md)** | **Settings Screen** | — | UI chỉnh API key/symbol/interval/sync days thay vì sửa tay `user_config.json`. Không phụ thuộc gì, rủi ro thấp, giá trị UX cao. |
| **P2** | **[BOT-018](backlog/BOT-018_notifications_alerting.md)** | **Notifications / Alerting** | — | Cảnh báo qua UI/Telegram khi sync lỗi, stream mất kết nối, phát hiện gap dữ liệu. Tận dụng `IEventBus` đã có sẵn. |
| **P2** | **[BOT-019](backlog/BOT-019_watchlist_market_overview.md)** | **Watchlist / Market Overview** | `BOT-005` ✅ | Bảng theo dõi nhiều symbol cùng lúc (giá, %change, volume) realtime. Tận dụng hạ tầng Live Stream đã hoàn thiện. |
| **P2** | **[Epic BOT-006](backlog/BOT-006_backtest_engine_execution.md)** | **Backtest Engine — Màn hình Backtest Thực thụ** | `BOT-001` ✅ | Epic, chia theo Phase — xem bảng chi tiết bên dưới. Không còn phụ thuộc `BOT-008` (backtest dùng Paper Exchange giả lập, không cần order thật). |
| **P3** | **[BOT-011](backlog/BOT-011_chart_tradingview_tier3_advanced.md)** | **TradingView Chart — Tier 3 Advanced** *(Ưu tiên thấp)* | `BOT-010` ✅ | Drawing tools (Trendline, Fibonacci), Context Menu chuột phải & Multi-chart/Snapshot. Giá trị thấp cho tự động hóa bot (task tự ghi chú); cần test tương tác chuột thật — cân nhắc kỹ trước khi làm toàn bộ. |
| **P3** | **[BOT-031](backlog/BOT-031_ui_preview_convention_and_tool.md)** | **UI Preview Convention — mock file/màn + tool auto-discover** *(dev tooling)* | `BOT-030` ✅ | Chuẩn hoá `scripts/preview_qml.py` (prototype có sẵn, hardcode 4 màn) thành convention chính thức: mỗi View có 1 file `preview.py` cùng cấp, tool tự quét `screens/`/`components/` để phát hiện thay vì danh sách cứng, có guard test enforce. Do user chủ động đề xuất, hoãn ưu tiên. |

#### 🎯 Epic BOT-006 — Chi tiết theo Phase

| Phase | Task ID | Tên Nhiệm vụ | Dependencies | Mô tả ngắn |
| :---: | :--- | :--- | :---: | :--- |
| **0** | ✅ **[BOT-020](completed/BOT-020_indicator_strategy_engine_core.md)** | **Indicator & Strategy Engine (Core)** | — | RSI/EMA/MACD + `StrategyEngine` chạy được batch (static) lẫn incremental (dynamic/live). Nền tảng dùng chung với `BOT-008`. |
| **1** | **[BOT-021](backlog/BOT-021_static_backtest_execution_engine.md)** | **Static Backtest Execution Engine** | `BOT-020` ✅ | Chạy chiến lược trên toàn bộ dữ liệu lịch sử trong 1 lượt nhanh (không throttle), trả `BacktestResult` (trades, equity curve, metrics). |
| **1** | **[BOT-022](backlog/BOT-022_backtest_screen_static_ui.md)** | **Backtest Screen — Static UI** | `BOT-021` | Màn hình Backtest thực thụ đầu tiên: cấu hình chiến lược, chạy, xem kết quả (equity curve, trade list, stat cards). |
| **2** | **[BOT-023](backlog/BOT-023_dynamic_backtest_engine.md)** | **Dynamic Backtest Engine** | `BOT-020` ✅, `BOT-021` | Mở rộng vòng lặp replay hiện có (`run_backtest/handler.py`) thành Paper Exchange & Virtual Event Loop — chạy chiến lược theo từng nến, tua nhanh/chậm/tạm dừng. |
| **2** | **[BOT-024](backlog/BOT-024_backtest_screen_dynamic_ui.md)** | **Backtest Screen — Dynamic UI** | `BOT-022`, `BOT-023` | Mở rộng màn hình Phase 1 với replay controls (play/pause/speed) + cập nhật chart/equity/trade log trực tiếp theo từng nến. |
| **X** | **[BOT-025](backlog/BOT-025_backtest_domain_events_completeness.md)** | **Backtest Domain Events — Completeness Pass** | `BOT-021`, `BOT-023` | Chuẩn hoá toàn bộ event Backtest (Static + Dynamic) vào 1 module, tài liệu hoá rõ khi nào phát/ai lắng nghe. |

> Thứ tự khuyến nghị: `BOT-020` ✅ → `BOT-021` → `BOT-022` → *(đánh giá lại)* → `BOT-023` → `BOT-024` → `BOT-025`.
