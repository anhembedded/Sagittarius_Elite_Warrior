# 🗺️ Project Roadmap & Task Board

> [!NOTE]
> Bảng quản lý lộ trình phát triển và tiến độ công việc của dự án **Binance Trading Bot** theo mô hình **Kanban Board**.

---

## 📂 Thư mục Quản lý Task

```text
Sagittarius_Elite_Warrior/Tasks/
├── 🟢 completed/   # Các nhiệm vụ đã hoàn thành và qua kiểm thử (Passed 100% Tests)
├── 🟡 in_progress/ # Các nhiệm vụ đang thực hiện trong Sprint hiện tại
├── 🔴 backlog/     # Các nhiệm vụ chờ ưu tiên triển khai
├── ❌ cancelled/   # Các nhiệm vụ đã huỷ có chủ đích (giữ lại lý do, không thực hiện)
└── 📄 reports/     # Các báo cáo phân tích & kiểm thử (Audit Reports)
```

---

## 📊 Tổng quan Tiến độ (Sprint Status)

| Trạng thái | Số lượng Task | Tỷ lệ |
| :--- | :---: | :---: |
| 🟢 **Completed** | 113 | 65.3% |
| 🟡 **In Progress** | 0 | 0% |
| 🔴 **Backlog** | 54 | 31.2% |
| ❌ **Cancelled** | 6 | 3.5% |
| 📈 **Tổng số Task** | **173** | **100%** |

> 🐞 **Lỗi (bug) không tính trong bảng trên** — theo dõi riêng ở [Bug Board](bug_report/README.md), nơi liệt kê cả bug **đang mở** lẫn đã sửa.

> Cập nhật 2026-08-21: Hoàn thành `BOT-101` (RSI compose generalized smoothing + 18 edge-case unit tests). **Đối soát lại toàn bộ bảng theo thực tế trên đĩa** — trước đó bảng ghi 108 completed/55 backlog trong khi thư mục thật là 106/57: `BOT-112A`, `BOT-112B`, `BOT-112C`, `BOT-112E` đã ship code (PR #72/#73/#74/#75) nhưng file task vẫn nằm ở `backlog/` và 2 trong 4 file còn ghi trạng thái `🔴 Backlog`. Cả 4 đã được cập nhật trạng thái và chuyển sang `completed/`; Epic `BOT-112` giờ **4/5**, chỉ còn `BOT-112D`. Bug cũng đã đối soát: `BUG-019`/`BUG-020` (sinh ra từ `BOT-112C`), `BUG-023`, `BUG-025` (streaming data path), `BUG-026`, `BUG-027`, và `BUG-028` (trước trùng mã BUG-025, đã re-index) đã ở `bug_report/completed/`. `BUG-015` cũng vừa đóng (2026-08-21, native chart geometry rebuild) — hoá ra không phải bug renderer, mà là race trong chính probe script đọc property chẩn đoán trước khi render thread kịp publish qua cross-thread hop. Hiện còn **1 bug đang mở**: `BUG-016` — root cause đã khoanh chính xác (treo tại `view.grabWindow()`, xem hồ sơ), tác động thật thấp vì native đã là default production, chỉ chặn bookkeeping `BOT-098F5`/`F6D` — xem [Bug Board](bug_report/README.md).
>
> Trước đó (2026-08-20): hoàn thành `BOT-041`, `BOT-050`, `BOT-110`, `BOT-111` (trọn Epic `BOT-109`), `BOT-113`, `BOT-106A` (bước 1/3 Epic `BOT-106`), `BOT-114`; bổ sung Epic `BOT-112` (5 task con) và Epic `BOT-115` (Lưu trữ & Nạp lại Báo cáo Backtest, 4 task con `BOT-115A`…`BOT-115D`).

### 🤖 Phân loại Độ phức tạp & Loại Agent AI phù hợp (Agent Complexity Matrix)

| Ký hiệu / Badge | Độ phức tạp | Loại AI Agent phù hợp | Tiêu chí đánh giá & Loại Task |
| :---: | :---: | :---: | :--- |
| 🟢 **`S (Fast Agent)`** | **Thấp** | **Fast / Routine Models** *(Gemini Flash, Haiku, GPT-4o-mini)* | Sửa Docs/Roadmap, thêm config key, styling QML đơn giản, refactor 1 file độc lập, unit test nhỏ. |
| 🟡 **`M (Standard Agent)`** | **Trung bình** | **Standard Coding Models** *(Gemini Pro, GPT-4o, Sonnet non-thinking)* | Thêm Use Case mới (Command + Handler), QML component/modal mới, mở rộng Parameter Schema, kết nối ViewModel. |
| 🔴 **`L (Thinking Agent)`** | **Cao** | **Deep Reasoning / Thinking Models** *(Sonnet Thinking, Gemini Thinking, o3-mini)* | FSM State Machine, Thread-affinity (UI vs Worker), Thuật toán tài chính, Out-of-sample, Cooperative Cancellation, Action Ownership. |
| 🛡️ / ⚡ **`Specialized`** | **Chuyên biệt** | **Specialized Agents** *(Sentinel 🛡️ / Bolt ⚡)* | **Sentinel 🛡️**: Security audit, injection defense. **Bolt ⚡**: Tối ưu thuật toán O(N²), profiling rendering/memory, benchmark throughput. |


> Lịch sử tăng backlog theo từng đợt (22 lần, `BOT-040` → `BOT-098F6`) đã được
> gỡ khỏi file này 2026-08-19 vì trùng lặp thuần tuý với "Vấn đề"/rationale đã
> có sẵn trong từng file task liên quan (`Tasks/completed/`, `Tasks/backlog/`).
> Xem lại qua `git log -p -- Tasks/ROADMAP.md` nếu cần nguyên văn.

---

> ## 🧭 Định hướng đã chốt: **Backtest đáng tin trước, giao dịch thật gác lại**
>
> Từ 📄 [Rà soát định hướng App](reports/app_direction_audit.md) §3. Bot **chưa đặt được
> lệnh nào** — [`market_tick_event_handler.py`](../src/application/event_handlers/market_data/market_tick_event_handler.py)
> chỉ `logger.info()` rồi return; [`BOT-008`](backlog/BOT-008_live_trading_strategy_execution.md)
> là **P1**, ghi *"sẵn sàng bắt đầu"*, vẫn chưa hề động tới.
>
> User đã chốt: **ưu tiên [Epic `BOT-078`](backlog/BOT-078_backtest_trustworthiness_epic.md)
> (`BOT-079` → `BOT-080`) trước `BOT-008`.** Lý do: chiến lược chưa kiểm định
> out-of-sample, và [`PythonBinanceClient`](../src/infrastructure/binance/client.py)
> hiện nối thẳng **mainnet thật** (`Client(api_key, api_secret)`, không có testnet nào
> cấu hình sẵn) — bật `BOT-008` lên trước khi biết chiến lược có edge thật là rủi ro tiền
> thật không cần thiết. `BOT-008` **không bị xoá khỏi backlog**, chỉ xếp sau.
>
> ✅ **Cập nhật (14/08)**: `BOT-079`/`BOT-080`/`BOT-081` — toàn bộ Epic `BOT-078` — đã
> xong. Chưa tự ý coi `BOT-008` là đã mở khoá — đó là quyết định của user, không tự suy ra
> từ việc code xong.

---

## 🏛️ Epics — Dự Án Lớn & Phân Rã Hệ Thống

> Chi tiết mục tiêu, bối cảnh và danh sách task con được quản lý tại [**Tasks/epics/README.md**](epics/README.md).

| ID | Tên Epic | Trạng thái |
| :--- | :--- | :---: |
| **[EPIC-001](epics/EPIC-001_ema_trend_pullback_tradingview_cross_reference/README.md)** | Đối chiếu `EmaTrendPullbackStrategy` với TradingView thật | 🟡 Đang làm (1/2 task con xong) |
| **[EPIC-002](epics/EPIC-002_static_type_checking_in_local_ci/README.md)** | Kiểm tra kiểu tĩnh (`mypy`) trong CI cục bộ | 🟡 Đang làm (4/5 task con xong) |
| **[EPIC-003](epics/EPIC-003_presenter_and_god_file_decomposition/README.md)** | Phân rã Presenter/File quá tải (Coordinator Pattern, Domain Policy, QML) | 🟡 Đang làm (3/6 xong, 1 huỷ — `003D` hết đối tượng sau `EPIC-006F`) |
| **[EPIC-004](epics/EPIC-004_static_security_and_quality_analysis/README.md)** | Static security & quality analysis gate (Bandit + magic-number qua Ruff) | 🟡 Đang làm (3/4 task con xong) |
| **[EPIC-005](epics/EPIC-005_qml_to_qtwidgets_migration/README.md)** | Rút khỏi QML về QtWidgets, **trừ chart** — theo từng màn hình, mỗi bước rollback được | ⏹️ **Bị thay thế bởi `EPIC-006`** — 6/6 task con xong (`005F` do `EPIC-006D/E` làm) |
| **[EPIC-006](epics/EPIC-006_drop_qml/README.md)** | Bỏ hẳn QML, thuần QtWidgets | ✅ **Hoàn thành (6/6 task con)** — 2026-08-25; Elite hết sạch `.qml`. Kit QML của Engine ở lại (sample app cần) |
| **[EPIC-007](epics/EPIC-007_chuan_hoa_card_dung_chung/README.md)** | **Chuẩn hoá card dùng chung, đưa hình dạng lên Engine** — gộp ~10 biến thể màu card về 1 token, 6 hình dạng surface lên `pyside_mvc.widgets`, cắt 3 import chéo màn hình | 🔵 Chưa bắt đầu (0/7 task con) |
| **[EPIC-008](epics/EPIC-008_chuan_hoa_luong_event/README.md)** | **Chuẩn hoá luồng sự kiện** — Shared Kernel + port, `BaseEvent` kế thừa được thật, `EventRegistry` + catalog sinh tự động, 3 Feed thay 48 signal cầu nối | ✅ **Hoàn thành (8/8 task con)** — 2026-08-25 |

---

## 📋 Bảng Quản lý Nhiệm vụ (Task Board)

### 🟢 Completed (Đã hoàn thành)

- [x] **`BUG-041`**: [App không thoát tiến trình khi đóng trong lúc Storage Vault đang scan DB](bug_report/completed/BUG-041_app_shutdown_hangs_on_inflight_thread_pool_task.md)
- [x] **`BOT-101`**: [RSI compose 2 instance smoothing tổng quát thay vì tự tính avg_gain/avg_loss](completed/BOT-101_rsi_compose_generalized_smoothing.md)
- [x] **`BOT-112C`**: [Trực quan hóa Lỗ hổng & Vá Từng Đoạn Dữ liệu](completed/BOT-112C_gap_detection_visualizer_and_selective_repair.md)
- [x] **`BOT-112B`**: [Bảng Tra cứu Nến KLine Inspector & Kiểm định Tính toàn vẹn](completed/BOT-112B_kline_data_inspector_and_integrity_audit.md)
- [x] **`BOT-112E`**: [Hỗ trợ khung thời gian 1 giây và toàn bộ TimeFrame chuẩn](completed/BOT-112E_support_1s_kline_fetch_and_storage.md)
- [x] **`BOT-112A`**: [Hoàn thiện Tác vụ Cốt lõi & Hỗ trợ Đa Khung thời gian](completed/BOT-112A_data_management_core_actions_and_timeframe_support.md)
- [x] **`BUG-018`**: [Ô "Stored KLines Records" của Storage Vault mãi mãi hiện `—` vì auto-discovery lúc mở màn kết thúc bằng transition `IDLE -> IDLE`](bug_report/completed/BUG-018_data_management_idle_to_idle_unlock_kills_stat_refresh.md)
- [x] **`BOT-114`**: [Áp dụng đòn bẩy thật vào PaperExchange (Real Leverage Application)](completed/BOT-114_paper_exchange_real_leverage_application.md)
- [x] **`BOT-106A`**: [Sharpe, Sortino, Calmar & Max Drawdown Duration](completed/BOT-106A_advanced_metrics_sharpe_sortino_drawdown_duration.md)
- [x] **`BOT-113`**: [Tô nền xu hướng cho chiến lược (Trend-Zone Background Shading)](completed/BOT-113_strategy_trend_zone_background_shading.md)
- [x] **`BOT-111`**: [Xác thực trực quan & backtest cho chiến lược vàng `EmaTrendPullbackStrategy`](completed/BOT-111_golden_strategy_visual_and_backtest_verification.md)
- [x] **`BUG-017`**: [Backtest "Đồng bộ ngay" tải lại toàn bộ range, bỏ qua phần đã cache](bug_report/completed/BUG-017_backtest_sync_redownloads_full_range_ignoring_cached_coverage.md)
- [x] **`BOT-104`**: [Cửa sổ Đặc tính Chiến lược & Mô phỏng Môi giới (TradingView-Style Properties Modal)](completed/BOT-104_backtest_properties_and_broker_simulator_modal.md)
- [x] **Epic BOT-042** *(A/B/C/D)*: [Thiết kế](completed/BOT-042A_provisional_commit_design.md) + [Indicator contract](completed/BOT-042B_indicator_provisional_contract.md) + [Series ô tạm](completed/BOT-042C_series_provisional_slot.md) + [StrategyEngine tick path](completed/BOT-042D_strategy_engine_tick_path_and_docs.md)
- [x] **`BUG-013`**: [ResourceScope teardown crash khi bắt đầu backtest mới](bug_report/completed/BUG-013.md)
- [x] **BOT-098F6F**: [Native Equity/BOTH subplot support](completed/BOT-098F6F_native_equity_and_both_subplot_support.md)
- [x] **BOT-098F6E**: [Native default rollout and Python kill-switch](completed/BOT-098F6E_native_default_rollout.md)
- [x] **BOT-085** *(kèm `BUG-011`/`BUG-012`)*: [Bug
- [x] **BOT-095E1**: [Symbol market metadata & truthful order-rule validation](completed/BOT-095E1_symbol_market_metadata_validation.md)
- [x] **BOT-095F**: [Toggle Chỉ báo Tham chiếu Động trên Biểu đồ sau Backtest](completed/BOT-095F_backtest_dynamic_indicator_toggle.md)
- [x] **BOT-098F6B**: [Native chart adapter and snapshot contract](completed/BOT-098F6B_native_chart_adapter_snapshot_contract.md)
- [x] **BOT-098F6A**: [Backtest chart port and Python adapter](completed/BOT-098F6A_backtest_chart_port_and_python_adapter.md)
- [x] **BOT-100**: [Backtest chart-toolbar timeframe data contract](completed/BOT-100_backtest_chart_toolbar_timeframe_contract.md)
- [x] **BOT-098F3**: [Native retained volume & indicator buffers](completed/BOT-098F3_native_volume_indicator_buffers.md)
- [x] **BOT-099**: [Cooperative desktop shutdown](completed/BOT-099_cooperative_desktop_shutdown.md)
- [x] **BOT-098A1**: [Pixel-budget LOD for truthful Backtest trade markers](completed/BOT-098A1_marker_density_lod.md)
- [x] **BOT-098F2A**: [Native camera & axis tick contract](completed/BOT-098F2A_native_camera_and_axis_tick_contract.md)
- [x] **BOT-098F2**: [Native retained candle geometry](completed/BOT-098F2_native_retained_candle_geometry.md)
- [x] **BOT-098F1**: [Native C++ QML chart plugin build boundary](completed/BOT-098F1_native_qml_plugin_build_boundary.md)
- [x] **BOT-098E**: [Native chart renderer gate: cached frame, LOD & retained geometry](completed/BOT-098E_chart_lod_and_batching.md)
- [x] **BOT-098D**: [Backtest OpenGL backend guard](completed/BOT-098D_backtest_opengl_backend_guard.md)
- [x] **BOT-098C**: [Crosshair cache & paint-path probe](completed/BOT-098C_crosshair_and_paint_probe.md)
- [x] **BOT-098B**: [Cache & coalesce chart range updates](completed/BOT-098B_range_update_pipeline.md)
- [x] **BOT-098A**: [Marker viewport virtualization & FPS overlay dev-only](completed/BOT-098A_marker_viewport_and_dev_fps.md)
- [x] **BOT-031**: [UI Preview Convention
- [x] **BOT-095H**: [Quyền sở hữu Action Backtest & Chặn Callback Lỗi thời](completed/BOT-095H_backtest_action_ownership_and_stale_callback_fencing.md)
- [x] **BOT-095C**: [Hủy Backtest & Tiến độ/ETA](completed/BOT-095C_backtest_cancellation_and_stop_button.md)
- [x] **BOT-095B**: [Backtest FSM Dirty Tracking
- [x] **BOT-069**: [`ExclusiveAction`
- [x] **BOT-068**: [Guard thread-affinity cho UI + sanity test chống drift](completed/BOT-068_ui_thread_affinity_guard.md)
- [x] **BOT-084**: [Bug
- [x] **BOT-001**: [Data Synchronizer](completed/BOT-001_data_synchronizer.md)
- [x] **BOT-002**: [UI Dashboard](completed/BOT-002_ui_dashboard.md)
- [x] **BOT-004**: [Data Management Screen](completed/BOT-004_data_management_screen.md)
- [x] **BOT-005**: [Live Charting](completed/BOT-005_live_charting.md)
- [x] **BOT-007**: [UI Theme, Font & Layout Config](completed/BOT-007_ui_theme_config_optimization.md)
- [x] **BOT-009**: [TradingView Chart
- [x] **BOT-010**: [TradingView Chart
- [x] **BOT-012**: [Application Layer SOLID Refactoring](completed/BOT-012_application_solid_refactoring.md)
- [x] **BOT-013**: [Infrastructure Layer SOLID Refactoring](completed/BOT-013_infrastructure_solid_refactoring.md)
- [x] **BOT-014**: [Dev Board Single Chart Config](completed/BOT-014_dev_board_single_chart.md)
- [x] **BOT-015**: [QA & Testing Strategy Audit](completed/BOT-015_qa_testing_strategy_audit.md)
- [x] **BOT-016**: [UI Icon Pack & Assets Management](completed/BOT-016_ui_icon_pack_integration.md)
- [x] **BOT-020**: [Indicator & Strategy Engine (Core)](completed/BOT-020_indicator_strategy_engine_core.md)
- [x] **BOT-028**: [QML Hybrid Prototype Spike
- [x] **BOT-029**: [UI Restyle
- [x] **BOT-030**: [Full QML Migration (chart giữ QtWidgets)](completed/BOT-030_full_qml_migration.md)
- [x] **BOT-032**: [Custom Indicator Scripts (kiểu Pine Script, thuần Python)](completed/BOT-032_custom_indicator_scripts.md)
- [x] **BOT-034**: [Dev Board
- [x] **BOT-062**: [Bug
- [x] **BOT-037**: [SOLID/SRP audit cho `src/presentation/ui`](completed/BOT-037_ui_srp_audit_and_extraction.md)
- [x] **BOT-017**: [Settings Screen](completed/BOT-017_settings_screen.md)
- [x] **BOT-033**: [Hoàn thiện thao tác người dùng trên QML](completed/BOT-033_qml_user_actions.md)
- [x] **BOT-036**: [Gộp tín hiệu (Batching) khi replay lịch sử cho indicator script](completed/BOT-036_indicator_feed_batching.md)
- [x] **BOT-026**: [Concrete Strategy Foundation
- [x] **BOT-055**: [Backtest Screen
- [x] **BOT-058**: [Backtest Screen
- [x] **BOT-059**: [Backtest Screen
- [x] **BOT-060**: [Backtest Screen
- [x] **BOT-061**: [Bug
- [x] **BOT-048**: [Chuyển 6 script mặc định sang input](completed/BOT-048_migrate_default_scripts_to_inputs.md)
- [x] **BOT-051**: [Chiến lược Multi-EMA Trend Follower](completed/BOT-051_multi_ema_trend_follower.md)
- [x] **BOT-064**: [Danh sách chọn Indicator Script cho màn Backtest](completed/BOT-064_backtest_screen_indicator_script_picker.md)
- [x] **BOT-065**: [Ẩn overlay Indicator Script khi Backtest chuyển "Đường Vốn"](completed/BOT-065_backtest_script_overlay_hidden_in_equity_mode.md)
- [x] **BOT-027**: [Fix Race Condition
- [x] **BOT-057**: [Backtest Screen
- [x] **BOT-044**: [Param Schema Core
- [x] **BOT-046**: [Param Schema cho Strategy + nối registry/factory](completed/BOT-046_strategy_param_plumbing.md)
- [x] **BOT-047**: [Modal "Cấu hình Thông số Bot"
- [x] **BOT-045**: [Trade Journal Detail
- [x] **BOT-056**: [Backtest Screen
- [x] **BOT-022**: [Backtest Screen
- [x] **BOT-066**: [`safe_ui_action` báo lỗi thật, không nuốt im lặng](completed/BOT-066_fail_loud_ui_action_errors.md)
- [x] **BOT-067**: [`ResourceScope`
- [x] **BOT-070**: [`from_qml()`
- [x] **BOT-082**: [Sửa test đỏ vĩnh viễn
- [x] **BOT-072**: [Bug
- [x] **BOT-021**: [Static Backtest Execution Engine
- [x] **BOT-083**: [Bug
- [x] **BOT-079**: [Minh bạch phí giao dịch + cảnh báo tần suất](completed/BOT-079_fee_transparency_and_trade_frequency.md)
- [x] **BOT-080**: [Kiểm định out-of-sample / walk-forward
- [x] **BOT-081**: [Công bố giới hạn của backtest ngay trên UI kết quả](completed/BOT-081_backtest_limitation_disclosure.md)
- [x] **BOT-089**: [Panel co giãn theo nội dung
- [x] **BOT-090**: [Trade Logs hiển thị được dòng

- [x] **BOT-087**: [`OverlayHost`
- [x] **BOT-088**: [Chuyển 6 popup màn Backtest sang overlay host](completed/BOT-088_migrate_backtest_popups_to_overlay_host.md)
- [x] **BOT-074**: [Bug
- [x] **BOT-096**: [Backtest

---

### 🟡 In Progress (Sprint hiện tại)

*(trống — xem NOTE bên dưới)*

> [!NOTE]
> **Cập nhật 2026-08-24, do user quyết định: native C++/QML chart backend đã
> bị xoá hoàn toàn** (`BUG-039`: chưa từng render 1 frame production kể từ khi
> tắt mặc định 2026-08-24, pyqtgraph đủ nhanh) để mở khoá `EPIC-006F` (dỡ QML
> kit của Engine). 4 task hiệu năng native (`BOT-098F4`/`F5`/`F6C`/`F6D`) và
> 2 bug Windows-only chưa root-cause xong chặn chúng (`BUG-015`/`BUG-016`) đã
> chuyển sang [`cancelled/`](cancelled/) — không còn đối tượng để áp dụng.
> Toàn bộ lịch sử điều tra Windows RHI (D3D11, probe bug fixes) trước đây ghi
> ở đây giờ nằm trong chính các file task/bug đã huỷ, không lặp lại ở đây.

### 🔴 Backlog (Danh sách Ưu tiên & Phụ thuộc)

| Priority | Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :---: | :--- | :--- | :---: | :---: | :--- |
| ~~P1~~ **Hoãn có chủ đích** | **[BOT-008](backlog/BOT-008_live_trading_strategy_execution.md)** | **Live Trading Strategy Execution** | 🔴 **`L (Thinking)`** | `BOT-001` ✅, `BOT-005` ✅ | Tính toán chỉ báo (RSI, EMA, MACD) từ Live Stream & phát tín hiệu đặt lệnh qua Binance API. Mọi phụ thuộc kỹ thuật đã xong — `BOT-078` (out-of-sample) **đã xong** (14/08) nhưng **chưa tự động mở khoá**: cần quyết định tường minh của user, không suy ra từ việc code xong, vì `PythonBinanceClient` nối thẳng mainnet thật, không có testnet. Xem ghi chú định hướng ở đầu file. |
| **P1** | **[Nhóm Engine Hardening](reports/engine_defect_class_analysis.md)** *(`BOT-066`…`BOT-071`)* | **6 cơ chế engine chặn 6 lớp lỗi tái phát** | 🟡 **`M`** / 🔴 **`L`** | — | Sinh ra từ rà soát toàn bộ lịch sử bug: gom thành 6 **lớp lỗi** rồi hỏi "cơ chế nào khiến cả lớp đó không xảy ra được nữa". Xem bảng chi tiết bên dưới. 📄 [Phân tích Lớp Lỗi Engine](reports/engine_defect_class_analysis.md). |
| **P1** | **[Epic BOT-095](backlog/BOT-095_backtest_signals_fsm_lifecycle_epic.md)** | **Backtest UI Signals, FSM & Parameter Lifecycle** | 🔴 **`L (Thinking)`** | `BOT-088` ✅, `BOT-059` ✅ | Hoàn thiện máy trạng thái FSM (`BacktestUiState` mở rộng: `CONFIG_DIRTY`, `CANCELLING`, `COMPLETED`), Dirty Tracking loại bỏ kết quả Stale khi đổi Timeframe/Strategy/Vốn/Ngày, nút Hủy tác vụ nền `CancellationToken`, kiểm tra nến sẵn sàng khi đổi Timeframe, và Real-time validation. Xem bảng chi tiết bên dưới. 📄 [Đặc tả Epic BOT-095](backlog/BOT-095_backtest_signals_fsm_lifecycle_epic.md). |
| ✅ | **[Epic BOT-078](backlog/BOT-078_backtest_trustworthiness_epic.md)** | **Backtest Trustworthiness — kết quả có đáng tin không?** | 🔴 **`L (Thinking)`** | `BOT-021` ✅, `BOT-047` ✅ | **Đã hoàn thành (14/08)** — cả 3 task con (`BOT-079`/`BOT-080`/`BOT-081`) xong. Backtest giờ minh bạch phí, có kiểm định out-of-sample bắt buộc, và công bố giới hạn ngay trên UI. Xem bảng chi tiết bên dưới. 📄 [Rà soát định hướng](reports/app_direction_audit.md). |
| **P1** | **[Epic BOT-073](backlog/BOT-073_realtime_tick_backtest_epic.md)** | **Realtime Backtest — chạy theo tick, song song với Static** | 🔴 **`L (Thinking)`** | `BOT-021` ✅ | Yêu cầu trực tiếp của user: backtest hiện tại là *static* kiểu TradingView, không tả được hành vi bot khi live (indicator khung 1m nhưng dữ liệu về mỗi 1s). Mục tiêu: **2 chế độ backtest dùng song song**, chung `PaperExchange`/`BacktestResult`. Kèm 1 bug thật (`BOT-074`) và 2 quyết định kiến trúc user vừa chốt. Xem bảng chi tiết bên dưới. ✅ `BOT-079`/`BOT-080` (minh bạch phí + out-of-sample) đã xong — nền tảng "kết quả đáng tin" cho Realtime đã có. |
| **P2** | **[BOT-035](backlog/BOT-035_dev_board_load_more_on_scroll.md)** | **Dev Board — Tự tải thêm dữ liệu cũ khi kéo ra rìa trái chart (US-04)** | 🟡 **`M (Standard)`** | `BOT-034` ✅ | Kéo/scroll chart ra rìa trái dữ liệu đã tải hiện không làm gì — chart chỉ trống. Query/repository layer đã hỗ trợ sẵn (`GetHistoricalKlinesQuery.end_time`), việc còn lại là: detect gần rìa trái (`ViewportController`, chưa có hook), `ChartCard.prepend_historical_data()` mới (không phá zoom hiện tại, khác `render_historical_data`), và full rebuild+refeed cho `IndicatorScriptRunner` (không có đường "feed lùi" — đã verify). **Còn 3 câu hỏi mở** (ngưỡng trigger, số nến/lần, có tự sync từ Binance khi DB thiếu hay không) — chưa code, chờ user chốt. |
| ✅ | **[Epic BOT-086](backlog/BOT-086_ui_layout_and_overlay_architecture_epic.md)** | **Kiến trúc Layout & Overlay của UI — hết vá pixel bằng tay** | 🟡 **`M (Standard)`** | — | Nguồn: [`BUG-004`](bug_report/completed/BUG-004.md), user đánh giá *"UI mechanical, philosophy chưa tốt, không phải riêng 1 view"* — **đã hoàn thành cả 2 Track A & Track B**. |
| **P2** | **[BOT-018](backlog/BOT-018_notifications_alerting.md)** | **Notifications / Alerting** | 🟡 **`M (Standard)`** | — | Cảnh báo qua UI/Telegram khi sync lỗi, stream mất kết nối, phát hiện gap dữ liệu. Tận dụng `IEventBus` đã có sẵn. |
| **P3** | **[BOT-116](backlog/BOT-116_native_chart_bridge_module_grouping.md)** | **Gom 7 module cầu nối native chart vào thư mục `native_chart/` riêng** | 🟢 **`S (Fast)`** | — | User phát hiện: 7 file (`native_chart_indicator_snapshot.py`, ..., `native_chart_viewport_gestures.py`) nằm phẳng ở `src/presentation/ui/` lẫn với 3 file app-wide thật (`app_bootstrapper.py`/`main_window.py`/`constants.py`) dù không cùng tầng ý nghĩa — 17 file cần sửa import (đã đo thật, không phải 34 như ước lượng ban đầu). Thuần tổ chức thư mục, không đổi hành vi — 2 câu hỏi thiết kế cần chốt trước khi code (đổi tên bỏ tiền tố hay không, dời test theo hay không). |
| **P2** | **[BOT-019](backlog/BOT-019_watchlist_market_overview.md)** | **Watchlist / Market Overview** | 🟡 **`M (Standard)`** | `BOT-005` ✅ | Bảng theo dõi nhiều symbol cùng lúc (giá, %change, volume) realtime. Tận dụng hạ tầng Live Stream đã hoàn thiện. |
| **P2** | **[Epic BOT-006](backlog/BOT-006_backtest_engine_execution.md)** | **Backtest Engine — Màn hình Backtest Thực thụ (TradingView Strategy Tester)** | 🔴 **`L (Thinking)`** | `BOT-001` ✅ | Epic, chia theo Phase — xem bảng chi tiết bên dưới. Không còn phụ thuộc `BOT-008` (backtest dùng Paper Exchange giả lập, không cần order thật). |
| **P2** | **[Epic BOT-040](backlog/BOT-040_backtest_screen_full_feature_epic.md)** | **Backtest Screen — Full Feature Set (TradingView Strategy Tester Parity)** | 🔴 **`L (Thinking)`** | `BOT-021` ✅ | Epic mới, từ spec + mockup đầy đủ do user cung cấp (4 khu vực: Top Toolbar / Performance Metrics / Chart Canvas / Trade Logs Table). Có bảng đối chiếu spec ↔ code, tách rõ phần làm được ngay vs phần cần `BOT-041`…`BOT-045`. **Supersede scope** của `BOT-022`/`BOT-024` (2 task đó đã được mở rộng tại chỗ, không tạo mới). Xem bảng chi tiết bên dưới. 📄 [Feature Status & Sanity Coverage](reports/backtest_screen_feature_status.md). |
| **P3** | **[BOT-011](backlog/BOT-011_chart_tradingview_tier3_advanced.md)** | **TradingView Chart — Tier 3 Advanced** *(Ưu tiên thấp)* | 🟡 **`M (Standard)`** | `BOT-010` ✅ | Drawing tools (Trendline, Fibonacci), Context Menu chuột phải & Multi-chart/Snapshot. Giá trị thấp cho tự động hóa bot (task tự ghi chú); cần test tương tác chuột thật — cân nhắc kỹ trước khi làm toàn bộ. |
| **P3** | **[BOT-039](backlog/BOT-039_dev_board_strategy_toggle_and_markers.md)** | **Dev Board — Strategy toggle + markers** *(sau khi Epic BOT-006 Phase 1 ổn định)* | 🟡 **`M (Standard)`** | `BOT-026` ✅ | Nửa UI tách ra từ BOT-026 gốc: toggle list Strategy trên Dev Board (US-02, mirror cơ chế Indicator), marker Buy/Sell vẽ qua `set_script_markers` có sẵn, mutually-exclusive với Indicators. Giá trị: thấy signal lúc live streaming + subscriber đầu tiên của `SignalGeneratedEvent` (seam cho `BOT-008`). |
| **P3** | **[BOT-117](completed/BOT-117_stale_pyside_mvc_paths_in_palette_docstring.md)** | **Sửa đường dẫn `QmlShared` cũ trong docstring `palette.py`** | 🟢 **`S (Fast)`** | — | Phát hiện 2026-08-23 khi đối chiếu app này với practice mới chốt bên `EPIC-002` (app mẫu) của `Sagittarius_Engine`: 2 dòng comment/docstring còn trỏ `pyside_mvc.QmlShared`/`QmlShared.state_tokens`, đường dẫn cũ trước đợt tái cấu trúc engine 2026-08-23 (thật ra giờ là `Sagittarius/UI/` và `tokens/`). Comment-only, không ảnh hưởng runtime. |
| **P3** | **[BOT-101](completed/BOT-101_rsi_compose_generalized_smoothing.md)** | **RSI compose smoothing tổng quát thay vì tự tính avg_gain/avg_loss** | 🟢 **`S (Fast)`** | — | DRY refactor nội bộ, không đổi hành vi quan sát được. Nảy sinh từ review thiết kế `BOT-042A` (2026-08-19) — Wilder's smoothing của RSI về toán học là 1 dạng EMA với `α=1/period`, đang viết tay lại thay vì compose. **Không chặn, không bị chặn bởi `BOT-042`.** Đề xuất song song (tiêm `IIndicator` qua DI vào `MACD`) đã bị từ chối cùng lúc review — MACD hard-code `EMA` đúng theo định nghĩa toán học, không phải coupling cần gỡ. |
| ✅ | **[BOT-102](completed/BOT-102_backtest_symbol_picker.md)** | **Backtest screen — thêm cơ chế đổi symbol (hiện khoá cứng)** | 🟡 **`M (Standard)`** | — | **Đã hoàn thành (19/08)** — user chọn nguồn symbol thật (Binance exchange-info, không phải danh sách tĩnh). `IExchangeClient.get_available_symbols()`/`ListAvailableSymbolsQuery` mới (repo trước đó chưa từng gọi exchange-info dưới bất kỳ hình thức nào); `SymbolPickerModal.qml` mới (grid + tìm kiếm, do Binance trả >1300 symbol); Presenter giữ `self._symbol` làm nguồn sự thật duy nhất, `selectedSymbol` trên ViewModel chỉ là kênh ghi từ modal. Verify bằng real-window probe: bấm nút thật, gọi Binance thật (1361 symbol), lọc tìm kiếm, chọn `ETHUSDT` cập nhật đúng presenter/chart/toolbar, QML sạch lỗi — 2 ảnh chụp màn hình xác nhận. Full suite 1496 pass (3 fail xác nhận có từ trước, không liên quan, cùng loại `BOT-038`), `ruff` sạch. |
| **P2** | **[BOT-103](backlog/BOT-103_realtime_backtest_gil_contention.md)** | **Realtime Backtest — UI đơ lúc chạy do GIL contention, không phải chạy trên UI thread** | 🟡 **`M (Standard)`** | `BOT-076` ✅ | User báo trực tiếp khi dùng thật: "chạy realtime tính toán... đang chạy trên UI thread kìa" (2026-08-19). Đã verify code trước khi ghi task: `_run_backtest` (cả 2 nhánh Static/Realtime) **đã** dispatch qua `IThreadManager.submit()` → `ThreadPoolExecutor` thật, không phải Qt UI thread; `progress_callback` cũng đã throttle mỗi 256 tick, không phải signal-flood. Nguyên nhân thật: `_simulate()` (`run_realtime_backtest/handler.py`) là vòng `for` Python CPU-bound tới hàng trăm nghìn tick không có điểm nhường CPU, giữ GIL gần liên tục khiến main/UI thread đói CPU — đúng triệu chứng user thấy dù kiến trúc đã đúng. 3 hướng đề xuất trong task (nhường GIL định kỳ / chuyển sang `ProcessPoolExecutor` / giảm chi phí mỗi tick), chưa chốt hướng nào. |
| **P?** | **[BOT-038](backlog/BOT-038_intermittent_segfault_full_ui_integration_suite.md)** | **Segfault ngẫu nhiên khi chạy toàn bộ `tests/integration/presentation/ui/`** | 🔴 **`L (Thinking)`** | — | Crash native (Qt/PySide6) intermittent, không deterministic theo test hay theo outcome — cùng nghi vấn lớp bug object-lifetime đã gặp ở `BOT-034` §5. Đã điều tra 1 vòng (bisect, gdb không debuginfod), dừng theo yêu cầu user — xem §4 "Hướng điều tra tiếp theo" trong file. **Không tự ý tiếp tục điều tra nếu chưa được yêu cầu lại.** |
| **P1** | **BOT-091** | **Backtest hybrid render/runtime guard — lỗi `QQuickRenderControl beginFrame/endFrame` sau khi chạy backtest** | 🔴 **`L (Thinking)`** | `BOT-087` ✅, `BOT-088` ✅ | Bug runtime thật trên màn Backtest: sau `RunStaticBacktestCommand` hoàn tất và UI tiếp tục `GetHistoricalKlinesQuery`, Qt nổ `QQuickRenderControl: Attempted to beginFrame() while the QRhi is already recording a frame` / `QQuickWidget: Failed to begin recording a frame`. Đây **không** phải lỗi parse QML, DI, presenter logic hay layout (`BOT-089`/`BOT-090`); nghi vấn nằm ở hybrid composition với nhiều `QQuickWidget` hoạt động đồng thời (`top_widget`, `bottom_widget`, `top_overlay_host.quick_widget`, `overlay_host.quick_widget`) cộng chart native redraw burst. Gap test hiện tại: sanity chỉ dựng màn + check `quick_widget.errors()`, unit/layout tests chỉ kiểm tra logic/geometry; **không có** test nào chạy backtest thật + fetch klines thật + quan sát vòng đời frame/render runtime. **Cập nhật 15/08:** đã có runtime probe chạy app thật ở dev-mode với dữ liệu `BTCUSDT` khung `1m` seed local để ép đi qua success path `RunStaticBacktestCommand` -> `GetHistoricalKlinesQuery`; probe mở thêm các toolbar popup/menu chính và đổi chart mode qua lại. Các lượt probe đó **chưa tái hiện lại** dòng `QQuickRenderControl`, nên bug vẫn được giữ ở backlog điều tra: chưa có reproduction tối thiểu ổn định từ phía AI và cũng chưa có bằng chứng runtime mới để kết luận đã hết. Rule của task này: **pytest/sanity pass không bao giờ đủ**; chỉ được coi xong khi chính kịch bản dev-mode thật được chạy lại và log sạch không còn `QQuickRenderControl` hay lỗi khung hình liên quan. |
| **P1** | **[BOT-098](backlog/BOT-098_backtest_chart_pan_zoom_performance.md)** | **Backtest Chart — Pan/Zoom mượt theo frame budget** | ⚡ **`L (Bolt / Thinking)`** | `BOT-098A`…`BOT-098F2` ✅; liên quan `BOT-091`, `BOT-096` ✅ | Retained native candle geometry đã hoàn thành; tiếp tục axis/camera, volume/indicator và interaction layers trong `BOT-098F` trước production migration. Không dùng TradingView Lightweight Charts/WebEngine. |


#### 🛡️ Nhóm Engine Hardening — Chi tiết (`BOT-066`…`BOT-071`)

> Nguồn: 📄 [Phân tích Lớp Lỗi Engine](reports/engine_defect_class_analysis.md). Không phân tích từng bug riêng lẻ mà nhóm toàn bộ lịch sử bug thành **lớp lỗi**, rồi đề xuất cơ chế tầng engine chặn cả lớp. Xuất phát từ ghi chú của user ở [`BUG-001`](bug_report/completed/BUG-001.md): *"tôi nghĩ engine nên có cơ chế lo điều này"*.
>
> **Cả 6 task đều sửa `sagittarius_engine/` (repo cha)** → commit ở cả hai repo, giống `BOT-030`/`BOT-032`/`BOT-036`.
>
> **Thứ tự khuyến nghị: `BOT-066` → `BOT-067` → `BOT-068`.** `BOT-066` đi trước không phải vì quan trọng nhất mà vì nó gần như miễn phí và biến mọi lớp còn lại thành lỗi **kêu to** — chừng nào 45 điểm `safe_ui_action` còn nuốt lỗi, cơ chế mới nào cũng có thể hỏng âm thầm đúng kiểu `BOT-061`. `BOT-070` rẻ nhất, không phụ thuộc gì, làm xen kẽ lúc nào cũng được.

| Task ID | Cơ chế | Độ phức tạp / Agent | Lớp lỗi chặn (ca thật) | Chi phí |
| :--- | :--- | :---: | :--- | :---: |
| ✅ **[BOT-066](completed/BOT-066_fail_loud_ui_action_errors.md)** | **`safe_ui_action` báo lỗi thật** — log có traceback + `UiActionFailedEvent` + re-raise ở dev mode | 🟢 **`S (Fast)`** | **B. Lỗi bị nuốt im lặng** — `BOT-061` (thông số user gõ bị vứt, không báo gì). Decorator bọc **36 điểm** (`grep` thời điểm làm), comment trong chính file cũ thừa nhận *"we just swallow"*. Bật dev-mode toàn suite lộ ra **8 bug FSM double-fault thật** (test gọi thẳng worker method bỏ qua bước khoá FSM entry point luôn làm) — không reachable từ production, nhưng đã sửa test cho khớp con đường gọi thật. | Thấp |
| ✅ **[BOT-067](completed/BOT-067_resource_scope_lifecycle.md)** | **`ResourceScope`** — teardown LIFO/idempotent tự động theo vòng đời lần chạy | 🟡 **`M (Standard)`** | **C. Nhân bản khi chạy lại** — 5 bug: `a84f58a`, `4ba1eae`, `dd565a0`, `5a063b5`, `f07d490`. **Lớp tái phát nhiều nhất** | Trung bình |
| ✅ **[BOT-068](completed/BOT-068_ui_thread_affinity_guard.md)** | **Guard thread-affinity** `@ui_mutator` + sanity test quét mọi ViewModel | 🛡️ **`L (Sentinel/Thinking)`** | **A. Chạm UI từ luồng nền** — [`BUG-001`](bug_report/completed/BUG-001.md) (app treo, `QBasicTimer`). Engine hiện có **0** guard thread nào; `set_stats()` đã drift thiếu `@Slot` | Trung bình |
| ✅ **[BOT-069](completed/BOT-069_exclusive_action_single_flight.md)** | **`ExclusiveAction`** — single-flight + nhóm key xung khắc | 🔴 **`L (Thinking)`** | **D. Re-entrancy** — `BOT-027` ✅ đã fix nhưng bằng **quy ước** (cờ viết tay, lặp 2 chỗ), entry point thứ 3 sẽ không tự có guard | Thấp |
| ✅ **[BOT-070](completed/BOT-070_qml_value_normalizer.md)** | **`from_qml()`** — unwrap `QJSValue` đệ quy | 🟢 **`S (Fast)`** | **E. Marshaling QML↔Python** — `BOT-061`. `QJSValue` xử lý ở **đúng 1 chỗ** trong cả repo → mỗi `@Slot("QVariant")` mới là một `BOT-061` mới | Rất thấp |
| ✅ **[BOT-071](completed/BOT-071_boot_asset_preflight.md)** | **Pre-flight asset lúc boot** — `AssetValidatorExtension` fail-fast ở dev mode | 🟢 **`S (Fast)`** | **F. Asset thiếu fallback im lặng** — 7 icon mất trong `git reset`, ship lỗi qua nhiều phiên tới khi user tự đọc log ([`BUG-002`](bug_report/completed/BUG-002.md)) | Thấp |

> ⏸️ **Ca cố ý KHÔNG đề xuất cơ chế**: `BOT-062`/`5c20156` (`self._autostart` chỉ gán khi config gate bật nhưng gọi vô điều kiện). Bản chất chỉ là thiếu null-guard — xây machinery tốn hơn phần tiết kiệm được. Ghi lại để lần sau không ai đề xuất rồi mất công phân tích lại.
> 🔗 **`BOT-067` ↔ `BOT-069` là cặp đôi**: vòng đời `ResourceScope` chính là vòng đời `ExclusiveAction`. Nếu làm cả hai, `ExclusiveAction` nên là nơi mở/đóng scope. **Không ghép thành 1 task** — 2 khái niệm khác nhau, dùng độc lập được.

#### 🧱 Epic BOT-086 — Chi tiết (Layout & Overlay Architecture)

> Nguồn: 📄 [`BUG-004`](bug_report/completed/BUG-004.md). User hỏi thẳng *"Do we need dynamic layout mechanism?"* → **có**, và cần thêm một cơ chế thứ hai nữa. Đây **không phải bug của màn nào**, mà là 2 lỗ kiến trúc.
>
> ⚠️ **2 track trực giao — sửa cái này KHÔNG tự sửa cái kia.** Kể cả khi panel co giãn đúng theo nội dung (~150px cho 4 stat card), modal 606px **vẫn** phải thoát khỏi widget cha. Ngược lại, có overlay host rồi thì Trade Logs **vẫn** 0 dòng.

| Task | Track | Tên Nhiệm vụ | Phụ thuộc | Mô tả ngắn |
| :--- | :---: | :--- | :---: | :--- |
| ✅ **[BOT-087](completed/BOT-087_overlay_host_engine.md)** | A | **`OverlayHost` — overlay full-window ở `pyside_mvc`** | — | **Xong.** Overlay trong suốt phủ full window (`OverlayHost`), `Overlay.overlay` = `1400x900`, modal 606px vừa, click-through khi rảnh (`WA_TransparentForMouseEvents`), geometry bám resize. Xem mục Completed phía trên. |
| ✅ **[BOT-088](completed/BOT-088_migrate_backtest_popups_to_overlay_host.md)** | A | **Chuyển 6 popup màn Backtest sang overlay host** | `BOT-087` ✅ | **Xong — Track A & Epic BOT-086 hoàn thành.** Cả 6 popup (`extendedMetricsPopup`, `limitationsPopup`, `BotParamsDialog`, `capitalPopup`, `IndicatorPickerMenu`, `OrderExecutionMenu`) đã chuyển sang `BackTestModals.qml` được host bởi `OverlayHost`. Có UI regression test verify không còn bị clipping. Xem mục Completed phía trên. |
| ✅ **[BOT-089](completed/BOT-089_content_driven_panel_sizing.md)** | B | **Panel co giãn theo nội dung — cắt vòng lặp "nâng magic number"** | — | **Xong.** `setFixedHeight(190)` bỏ hẳn, panel giờ đọc `contentColumn.implicitHeight` thật. 2 bug thật phát sinh lúc code (cả 2 verify bằng ảnh chụp UI + mutation test): (1) `ensurePolished()` gọi nhầm item (`root` thay vì `contentColumn`); (2) "ROW 2" dùng `Layout.fillHeight` khiến card/kết quả bị `contentColumn` bỏ qua hoàn toàn — **đây mới là nguyên nhân thật của ảnh chụp gốc `BUG-004`**. Toolbar bọc `ScrollView` ngang, `ScrollBar.policy` phải là `AlwaysOn` (không phải `AsNeeded` — đọc thẳng `Basic/ScrollBar.qml` xác nhận `AsNeeded` vô hình tới khi hover). Xem mục Completed phía trên. |
| ✅ **[BOT-090](completed/BOT-090_trade_logs_visible_rows.md)** | B | **Trade Logs hiển thị được dòng — hiện trống hoàn toàn** | `BOT-089` ✅ | **Xong — Track B hoàn thành.** `setMinimumHeight()` mới (mirror `_bind_top_panel_height`) chặn splitter kéo pane xuống dưới `minimumUsableHeight` (QML tự tính: toolbar+header bảng+5 dòng+phân trang — quyết định UX có chủ đích, không phải "đo lại nội dung" vì `ListView` vốn cuộn được). `PAGE_SIZE` giữ cố định 20, không làm động. Verify bằng ảnh chụp UI thật: 5 dòng hiện đầy đủ. Xem mục Completed phía trên. |

> ✅ **Epic BOT-086 hoàn thành**: cả Track A (`BOT-087`/`BOT-088`) và Track B (`BOT-089`/`BOT-090`) đã hoàn tất. Hạ tầng layout & popup của toàn app và màn Backtest đã được chuẩn hóa.
> 📌 **Nợ tự nhận**: `extendedMetricsPopup` đã tràn sẵn từ `BOT-055` (8 card = 422px > 190px), nhưng `BOT-079` (+1 card) và `BOT-080` (+2 card) đẩy lên **606px** mà không ai đo, còn `BOT-081` tạo thêm `limitationsPopup` (~410px) ngay trong panel 190px đó — test chỉ verify "bấm không crash", đúng gap harness đã ghi từ `BOT-047`. `BOT-087` §3.3 bắt buộc đóng gap này.
>
> 🤝 **HANDOFF (15/08) — Track A chuyển cho AI session khác, chưa code dòng nào.**
> Phiên trước dừng ở prompt-adaptation (`.jules/bolt.prompt.md`, `.jules/palette.prompt.md`)
> và tạo [`.agents/Handover.md`](../.agents/Handover.md).
> ⚠️ *Sửa 2026-08-25: `Handover.md` đã được viết lại hoàn toàn và **không còn** mục quy ước/gotcha
> mà dòng trên hứa hẹn — quy ước thật ở [`.agents/ONBOARDING.md`](../.agents/ONBOARDING.md), bản
> Handover cũ ở `git show f0e63ca:.agents/Handover.md`.* Trạng thái thật:
> - `BOT-087`/`BOT-088`: cả 2 checklist trong task file **100% chưa tick**, chưa có branch,
>   chưa có commit nào ở `sagittarius_engine/` hay `Sagittarius_Elite_Warrior/` cho Track A.
> - Bắt đầu từ `BOT-087` (không phụ thuộc gì) — đọc §2 của file đó, đã có probe khả thi thật
>   (không phải lý thuyết) kèm đoạn code Python probe sẵn dùng làm điểm xuất phát.
> - Rủi ro lớn nhất đã biết trước (đọc §4 `BOT-087`): z-order `OverlayHost` với `ChartCard`
>   (pyqtgraph/QtWidgets) — **phải chạy tay xem modal có phủ đúng lên chart không**, đừng tin
>   lý thuyết. Nếu chart che modal → dừng, hỏi user, đừng tự đổi sang hướng A/C (xem `BOT-086` §3).

#### 🔄 Epic BOT-095 — Chi tiết (Backtest UI Signals, FSM & Parameter Lifecycle)

> Nguồn: Rà soát toàn diện luồng tương tác và quản lý trạng thái trên màn hình Backtest.
> 
> **Vấn đề giải quyết**: Khắc phục triệt để lỗi Stale Data khi người dùng đổi Timeframe (`1m` $\rightarrow$ `5m`), Strategy, Vốn, Ngày (kết quả cũ bị giữ nguyên sai lệch), mở rộng Finite State Machine (`BacktestUiState`), bổ sung nút Hủy (`CancellationToken`), kiểm tra nến sẵn sàng trong SQLite (Data Probe) và Real-time validation. 📄 [Đặc tả Epic BOT-095](backlog/BOT-095_backtest_signals_fsm_lifecycle_epic.md).

| Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :---: | :--- |
| ✅ **[BOT-095A](completed/BOT-095A_declarative_fsm_engine_foundation.md)** | **Hạ tầng Declarative State Machine & Event Dispatching** | 🔴 **`L (Thinking)`** | — | `sagittarius_engine.extensions.fsm` (`DeclarativeStateMachine`), ma trận `(State, Event) -> NextState`, `dispatch(event)`, `load_matrix()`, bảo vệ Re-entrancy và Thread-Affinity. |
| **[BOT-095B](completed/BOT-095B_backtest_fsm_dirty_tracking.md)** ✅ | **Màn hình Backtest FSM & Quản lý Trạng thái Stale Data (Dirty Tracking)** | 🔴 **`L (Thinking)`** | `BOT-095A` ✅ | `backtest_fsm_matrix.py`, Dirty Tracking so khớp `BacktestRunConfig`, Amber Banner với Diff Summary, tự động khôi phục `COMPLETED`, và bảo vệ nút Xuất CSV. |
| ✅ **[BOT-095H](completed/BOT-095H_backtest_action_ownership_and_stale_callback_fencing.md)** | **Quyền sở hữu Action & Chặn Callback Lỗi thời** | 🔴 **`L (Thinking)`** | `BOT-095A` ✅, `BOT-095B` ✅ | `action_id`/generation, immutable config snapshot và stale-callback fencing đã hoàn thành; **mở khóa C/D/G.** |
| ✅ **[BOT-095C](completed/BOT-095C_backtest_cancellation_and_stop_button.md)** | **Nút Hủy / Dừng Backtest & Tiến độ Tính toán Realtime (`CancellationToken` & ETA)** | 🔴 **`L (Thinking)`** | `BOT-095H` ✅ | Nút Cancel, cancellation outcome tường minh, progress/ETA benchmarked; cancellation check đi qua mọi pass mô phỏng. |
| ✅ **[BOT-095D1](completed/BOT-095D1_backtest_range_coverage_probe.md)** | **Range Coverage Probe theo cadence** | 🟡 **`M (Standard)`** | `BOT-095C` ✅ | Fast aggregate SQLite + DTO coverage immutable cho đúng `[start, end)`, phát hiện boundary/gap/duplicate/nến chưa đóng. |
| ✅ **[BOT-095D](completed/BOT-095D_backtest_timeframe_change_and_data_probe.md)** | **1-Click Auto-Sync & Run, Date Range Gap Check & Live Preview** | 🟡 **`M (Standard)`** | `BOT-095C` ✅, `BOT-095H` ✅, `BOT-095D1` ✅ | Preview theo timeframe/range, sync progress, post-sync re-probe và auto-continue có action fencing. |
| ✅ **[BOT-095E](completed/BOT-095E_backtest_realtime_input_validation.md)** | **Khung Kiểm định Đầu vào Mở rộng (Pre-Backtest Assertion Pipeline) & Stepper** | 🟡 **`M (Standard)`** | `BOT-095E1` (market metadata follow-up) | Assertion pipeline local, validation realtime, published-candle watermark, post-sync coverage re-probe, hotkeys/stepper qua Python; Full CI 928 primary + 25 sanity xanh. |
| ✅ **[BOT-095E2](completed/BOT-095E2_param_schema_step_metadata.md)** | **Step Metadata cho Strategy Parameter Schema** | 🟢 **`S (Fast)`** | `BOT-095E` ✅ | Metadata `step` explicit cho Strategy/Indicator, normalisation Python và Qt interaction regression test. |
| **[BOT-095G](backlog/BOT-095G_backtest_session_run_history_cache.md)** | **Bộ nhớ đệm Lịch sử Lần chạy (Session Run History Cache)** | 🔴 **`L (Thinking)`** | `BOT-095H` | Snapshot immutable có provenance, bounded-memory cache và restore transactionally; không hứa SLA “0ms”. |

---

#### 🔬 Epic BOT-078 — Chi tiết (Backtest Trustworthiness)

> Nguồn: 📄 [Rà soát định hướng App](reports/app_direction_audit.md) §1 & §2.
>
> **Khác `BOT-073`**: `BOT-073` lo *engine mô phỏng có giống thật không*. Epic này lo *con số engine trả ra có bị hiểu sai không* — engine đúng 100% vẫn có thể dẫn tới kết luận sai.

| Task ID | Tên Nhiệm vụ | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :--- |
| ✅ **[BOT-079](completed/BOT-079_fee_transparency_and_trade_frequency.md)** | **Minh bạch phí + cảnh báo tần suất giao dịch** | `BOT-021` ✅, `BOT-055` ✅ | **Xong.** `BacktestMetrics` +4 field; cảnh báo hiện ở dòng riêng cạnh "Mở rộng chỉ số chi tiết" (không phải badge), card "Total Fees Paid" thêm vào popup mở rộng. Xem mục Completed phía trên. |
| ✅ **[BOT-080](completed/BOT-080_out_of_sample_walk_forward.md)** | **Kiểm định out-of-sample / walk-forward** | `BOT-047` ✅ | **Xong.** Mức 1 (tách in-sample 70%/out-of-sample 30% theo số nến, không phải walk-forward). `RunStaticBacktestCommandHandler` tự chạy cả 2 nửa **bắt buộc mỗi lần**, độc lập với kết quả full-range (stat cards/chart/trade log không đổi). Cảnh báo overfit + 2 card mới tái dùng nguyên cơ chế `BOT-079`. Xem mục Completed phía trên. |
| ✅ **[BOT-081](completed/BOT-081_backtest_limitation_disclosure.md)** | **Công bố giới hạn trên UI kết quả** | `BOT-079` ✅ | **Xong — Epic `BOT-078` hoàn thành.** Icon ⓘ (nút thật, test-clickable) cạnh kết quả mở popup liệt kê giới hạn *đang áp dụng cho lần chạy này* — 1 dòng thật sự động theo state (cảnh báo thiếu out-of-sample chỉ hiện khi `result.out_of_sample is None`), các dòng còn lại gom về đúng 1 hằng số (sửa 1 chỗ khi `BOT-041`/`049`/`050`/`073` xong). Xem mục Completed phía trên. |

> ✅ **Epic hoàn thành (14/08)**: cả 3 task (`BOT-079`/`BOT-080`/`BOT-081`) đã xong. Kết quả
> Backtest giờ minh bạch phí, có kiểm định ngoài mẫu bắt buộc, và công bố rõ mọi giả định
> đang áp dụng — nền tảng "đáng tin" trước khi dùng `BOT-047` tinh chỉnh nghiêm túc hoặc
> bắt đầu `BOT-073`.
> 💡 **Cám dỗ đã đề phòng**: epic này từng có nguy cơ bị coi là "việc phụ" vì không thêm
> tính năng nào nhìn thấy được. Nhưng nó quyết định **mọi kết luận** rút ra từ app — kể cả
> kết luận "chiến lược này tốt, đem tiền thật vào".

#### ⏱️ Epic BOT-073 — Chi tiết (Realtime Backtest theo tick)

> Nguồn: yêu cầu trực tiếp của user — *"Indicator could set on tf 1m, but realtime data feed every 1s. So every one sec, we must calculate the last candle and all last indicator. I want a realtime backtest... 2 backtest strategies available on my app."*
>
> **Supersede scope** của `BOT-042` (task đó không bị xoá, chỉ được chốt lại quyết định kiến trúc còn treo và trở thành task con — giống cách `BOT-040` xử lý `BOT-022`/`BOT-024`).
>
> ✅ **`BOT-023` (Dynamic Backtest) đã bị HUỶ (2026-08-18, user chốt)** — [hồ sơ huỷ](cancelled/BOT-023_dynamic_backtest_engine.md). Nó vẫn **bar-by-bar** nên không giải quyết được yêu cầu này, mà lại mang ràng buộc ngược ("phải khớp Static tuyệt đối") trong khi Realtime **cố ý khác** Static. App còn đúng **2 engine**: Static (`BOT-021` ✅) + Realtime (`BOT-076`); phần play/pause/tốc độ trở thành lớp điều khiển trên vòng lặp tick của `BOT-076` (§3.5), không phải engine riêng.

| Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :---: | :--- |
| ✅ **[BOT-074](completed/BOT-074_execution_trigger_rule_inverted_lock.md)** | **Bug — Execution Trigger Rule: cờ `locked` đảo ngược** | 🟢 **`S (Fast)`** | — | Cái **duy nhất chạy thật** ("On bar close") bị làm mờ; 3 cái **chưa cài đặt** thì bấm được bình thường — và trạng thái checkbox **không bao giờ rời khỏi QML** (`grep`: không có `executionTrigger` nào ở Python). **Đã sửa:** `locked: true` cho cả 4 lựa chọn đảm bảo tính trung thực UI. |
| ✅ | **[BOT-075](backlog/BOT-075_tick_data_feasibility_spike.md)** | **Spike — khả thi & chi phí dữ liệu tick** | 🟡 **`M (Standard)`** | — | **Xong (19/08)**, xem [báo cáo](reports/tick_data_feasibility.md): sync thật 7 ngày `BTCUSDT` ở `1s` (604.801 dòng) — 120,12 MiB `.db`, query 6,32s, `RunStaticBacktestCommandHandler` thật chạy 10,98s/11.285 trades. Kết luận: **khả thi có điều kiện** — bắt buộc chạy nền (progress+cancel đã có sẵn), nên cho chọn độ phân giải `1s/5s/15s`. Nguồn dữ liệu **đã chốt: `1s kline`, không `aggTrades`**. Không còn chặn `BOT-076`. |
| ✅ | **[Epic BOT-042](backlog/BOT-042_tick_level_strategy_engine_support.md)** | **Provisional vs Commit cho `IIndicator`/`Series`/`StrategyEngine`** | 🔴 **`L (Thinking)`** | `BOT-020` ✅, `BOT-026` ✅ | **Hoàn thành (19/08)** — cả 4 task con (`BOT-042A`/`B`/`C`/`D`) đã xong, xem mục Completed phía trên. Không còn chặn `BOT-076` ngoài chính nó. |
| ✅ | **[BOT-076](completed/BOT-076_realtime_backtest_engine.md)** | **Realtime Backtest Engine** | 🔴 **`L (Thinking)`** | `BOT-042` ✅, `BOT-075` ✅ | **Hoàn thành (19/08)**. §3.1+3.2: `RunRealtimeBacktestCommand`/`RunRealtimeBacktestCommandHandler` thật, vòng lặp tick-bucket-theo-bar, equity curve chốt **theo bar** (đúng yêu cầu, tránh lệch tập điểm với Static). Bẫy thật gặp phải: tick đóng bar bị đánh giá 2 lần (provisional + commit cùng dữ liệu) sinh tín hiệu giả đúp — sửa bằng phát hiện "tick cuối bar" qua `close_time >= bar_end`, chỉ đi qua 1 đường. §3.3: mở khoá chế độ tick trong `OrderExecutionModal.qml`, `_run_backtest` dispatch đúng lệnh theo `execution_mode`, `TickModeRequiresBoundedRangeRule` chặn tick mode + "Toàn bộ lịch sử" (từng gây vòng lặp "Đồng bộ ngay" vô hạn thật). §3.5 (replay control) **huỷ có chủ đích** — hỏi thẳng user, chọn "Drop it, close out BOT-076". 12 test §3.1/3.2 + 4 test §3.3 presenter + mutation-check. Phát hiện thêm khi làm `BOT-102`: `_build_run_config()` từng thiếu `symbol=self._symbol`, xem `BOT-102`. |
| **[BOT-077](backlog/BOT-077_calc_on_order_fills.md)** | **`calc_on_order_fills`** — chạy lại strategy ngay khi lệnh khớp | 🔴 **`L (Thinking)`** | `BOT-076` ✅ | Làm rõ dòng "On order filled" từng ghi *"chưa rõ nghĩa"* ở `BOT-040` §2.1. Với **chỉ dữ liệu nến** đây là **trường hợp suy biến** (fill ở open nến N+1, lúc đó `open=high=low=close`) → chỉ có nghĩa thật khi đã có tick. Rủi ro riêng: **đệ quy** entry→fill→chạy lại→entry, cần giới hạn cứng + test. |

> ⚠️ **`calc_on_order_fills` KHÔNG phải cách giải quyết nỗi lo Stop Loss** (user lo "lệnh khớp phút 10, chờ tới phút 60 mới đặt được SL → cháy tài khoản"). Pine **buộc phải** có nó vì trong Pine muốn đặt SL thì phải gọi `strategy.exit()` từ trong script. Sàn thật thì SL/TP là **lệnh nằm sẵn trên sàn** (bracket/OCO), sàn tự canh 24/7, bot sập nguồn SL vẫn còn. → **[`BOT-041`](completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md) mới là thứ đóng lỗ hổng đó, ưu tiên cao hơn hẳn `BOT-077`.**
> 📌 **Bất biến sẽ phải sửa lời hứa**: `BOT-020` hiện hứa "batch ≡ incremental". Static và Realtime **cố ý** cho kết quả khác nhau — phải ghi rõ ra giấy (action item bắt buộc trong `BOT-042` §4.2), nếu không người sau sẽ tưởng Realtime đang bug. Ngoại lệ duy nhất phải khớp: chạy Realtime với 1 tick/bar.
> 🎭 **Rủi ro lớn nhất — fidelity ảo**: tick 1s **vẫn không phải** tick thật; vẫn thiếu slippage, độ trễ mạng, orderbook depth, partial fill. Độ phân giải tick chỉ là **1 trong 4-5 nguồn sai lệch** so với live thật.

#### 🎯 Epic BOT-006 — Chi tiết theo Phase

| Phase | Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **0** | ✅ **[BOT-020](completed/BOT-020_indicator_strategy_engine_core.md)** | **Indicator & Strategy Engine (Core)** | 🔴 **`L (Thinking)`** | — | RSI/EMA/MACD + `StrategyEngine` chạy được batch (static) lẫn incremental (dynamic/live). Nền tảng dùng chung với `BOT-008`. |
| **0.5** | ✅ **[BOT-026](completed/BOT-026_concrete_strategy_foundation.md)** | **Concrete Strategy Foundation** | 🟡 **`M (Standard)`** | `BOT-020` ✅ | `BaseStrategy` (ABC, domain-only) + `EmaCrossoverStrategy` cụ thể đầu tiên + `StrategyRegistry`. Dọn `ema_cross_script.py` (indicator không còn tự vẽ marker Buy/Sell — việc đó là của Strategy). |
| **1** | ✅ **[BOT-021](completed/BOT-021_static_backtest_execution_engine.md)** | **Static Backtest Execution Engine** | 🔴 **`L (Thinking)`** | `BOT-020` ✅, `BOT-026` ✅ | Chạy chiến lược trên toàn bộ dữ liệu lịch sử trong 1 lượt nhanh (không throttle), trả `BacktestResult` (trades, equity curve, 13 metric kiểu TradingView Performance Summary). Fill tại open bar kế tiếp (không phải close bar tín hiệu). |
| **1** | ✅ **[BOT-022](completed/BOT-022_backtest_screen_static_ui.md)** | **Backtest Screen — Khung màn hình + Top Toolbar** | 🟡 **`M (Standard)`** | `BOT-021` ✅ | Màn hình Backtest thực thụ đầu tiên, chạy được thật end-to-end. 4 panel đẹp (Properties/Performance Summary/Trade Logs/Overview) tiếp theo ở `BOT-055`/`BOT-056`/`BOT-057`. |
| ❌ | **[BOT-023](cancelled/BOT-023_dynamic_backtest_engine.md)** | **~~Dynamic Backtest Engine~~ — ĐÃ HUỶ** | — | — | **Huỷ 2026-08-18 (user chốt).** Vẫn bar-by-bar nên không đáp ứng yêu cầu Realtime; giá trị riêng (play/pause/tốc độ) là lớp **trình bày**, đã chuyển vào [`BOT-076`](completed/BOT-076_realtime_backtest_engine.md) §3.5. Không dựng engine replay thứ hai. |
| ❌ | **[BOT-024](cancelled/BOT-024_backtest_screen_dynamic_ui.md)** | **~~Backtest Screen — Replay UI~~ — ĐÃ HUỶ** | — | — | **Huỷ 2026-08-19 (user chốt).** Cùng tính năng play/pause/replay speed đã bị từ chối ở `BOT-076` §3.5 dưới mã task khác — giữ cả hai sẽ để backlog treo một việc đã bị từ chối. |
| **X** | **[BOT-025](backlog/BOT-025_backtest_domain_events_completeness.md)** | **Backtest Domain Events — Completeness Pass** | 🟢 **`S (Fast)`** | `BOT-021` ✅, `BOT-076` ✅ | Chuẩn hoá toàn bộ event Backtest (Static + Realtime) vào 1 module, tài liệu hoá rõ khi nào phát/ai lắng nghe. |
| **3** | **[BOT-039](backlog/BOT-039_dev_board_strategy_toggle_and_markers.md)** | **Dev Board — Strategy toggle + markers** | 🟡 **`M (Standard)`** | `BOT-026` ✅ | Nửa UI Dev Board tách khỏi BOT-026 gốc — làm sau khi màn Backtest (Phase 1) ổn định, không phải điều kiện chặn Phase 1/2. |

> Thứ tự khuyến nghị: `BOT-020` ✅ → `BOT-026` ✅ → `BOT-021` ✅ → `BOT-022` ✅ → `BOT-055`/`BOT-056`/`BOT-057` → *(đánh giá lại, xác nhận Static ổn định)* → `BOT-075` ✅ → `BOT-042` ✅ → **`BOT-076`** ✅ → `BOT-024` → `BOT-025` (`BOT-023` đã huỷ, xem Epic `BOT-073`). `BOT-039` làm song song hoặc sau, không chặn đường chính. Đối chiếu kết quả với TradingView thật (báo cáo lưu ở `reports/backtest_tradingview_crosscheck.md`) là bước bắt buộc trước khi coi Phase 1 "xong".

#### 🎯 Epic BOT-040 — Chi tiết (mở rộng màn Backtest theo spec đầy đủ)

> Đã **chia nhỏ** thành 4 nhóm theo yêu cầu user. Trong mỗi nhóm, thứ tự liệt kê là thứ tự làm khuyến nghị.
> **Đường ngắn nhất tới màn Backtest dùng được**: `BOT-022` ✅ → `BOT-055` ✅ → `BOT-056` ✅ → `BOT-057` ✅ (không cần Nhóm A/B/C).

**Nhóm A — Hệ thống tham số** *(chặn nhiều nhất, ưu tiên cao nhất)*

| Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :---: | :--- |
| ✅ **[BOT-044](completed/BOT-044_param_schema_core.md)** | **Param Schema Core** *(kiểu `input()` Pine Script)* | 🟡 **`M (Standard)`** | `BOT-032` ✅ | `ScriptInput`/`InputKind`/`InputDeclarations` ở `domain/scripting/` (dùng chung, `BOT-046` tái dùng nguyên) + `input_int/float/bool/string()` trên `BaseIndicatorScript` + property `inputs`. `IndicatorScriptRegistry.create(key, params)` giờ **truyền thật** thay vì bỏ qua. Validate ở domain, raise thay vì kẹp giá trị. ⚠️ **Đảo ngược `BOT-032` §9.1**. |
| ✅ **[BOT-046](completed/BOT-046_strategy_param_plumbing.md)** | **Param Schema cho Strategy + nối registry/factory** | 🟡 **`M (Standard)`** | `BOT-044` ✅, `BOT-026` ✅ | `BaseStrategy` thêm hook `setup()` + `input_int/float/bool/string()`/`inputs` — tái dùng nguyên `InputDeclarations`/`ScriptInput` từ `domain/scripting/` (BOT-044), không chia sẻ qua kế thừa (2 base class vẫn tách biệt). `StrategyRegistry.create(key, params)`/`build_engine(..., params)` giờ truyền thật. `EmaCrossoverStrategy` chuyển từ constructor kwargs (`fast_period=`/`slow_period=`) sang khai báo trong `setup()` — default 12/26 giữ nguyên. Bất biến "diff = 0 dòng" (`i_strategy.py`/`strategy_context.py`/`strategy_engine.py`/`test_strategy_engine.py`) giữ nguyên. 12 test mới. 730 test pass, coverage 94.86%, `ruff` sạch. |
| ✅ **[BOT-047](completed/BOT-047_dynamic_params_form_ui.md)** | **Modal "Cấu hình Thông số Bot" — form động** | 🟡 **`M (Standard)`** | `BOT-044` ✅, `BOT-046` ✅ | Dựng form từ schema (4 kiểu widget, nhóm field, "Khôi phục Mặc định", "Lưu & Re-Backtest"). Thêm chiến lược mới **không phải sửa UI**. |
| ✅ **[BOT-048](completed/BOT-048_migrate_default_scripts_to_inputs.md)** | **Chuyển 6 script mặc định sang input** | 🟢 **`S (Fast)`** | `BOT-044` ✅, `BOT-047` ✅ | **Giữ nguyên cả 6**, chỉ đổi period/fast/slow/signal từ hardcode sang `input_int()` với default y hệt giá trị cũ. `min_warmup_bars` **vẫn là class attribute** (chưa động) — đúng vì chưa ai truyền `params` thật cho indicator script (xem `BOT-063`). |
| **[BOT-063](backlog/BOT-063_indicator_settings_modal.md)** | **Modal "Thông số Chỉ báo" cho Dev Board** | 🟡 **`M (Standard)`** | `BOT-048` ✅ | Tái dùng pattern `BOT-047` (form động, Lưu/Khôi phục Mặc định) nhưng cho **indicator script** thay vì strategy — `indicator_script_runner.py` hiện gọi `create(key)` không truyền `params`, cần nối lại. Chưa bắt đầu. |

**Nhóm B — PaperExchange nâng cao**

| Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :---: | :--- |
| ✅ **[BOT-045](completed/BOT-045_trade_journal_detail_and_metadata.md)** | **Trade Journal Detail — lý do vào/thoát & metadata** | 🟡 **`M (Standard)`** | `BOT-021` ✅, `BOT-026` ✅ | `Signal.metadata` + `ExitReason` enum (5 member, 3 chừa sẵn cho `BOT-041`/`BOT-049`) + `Trade.entry_reason`/`exit_reason`/`metadata`. Đóng luôn dòng mở rộng chi tiết của `BOT-057` §2.2. 15 test mới, `ruff` sạch. |
| ✅ | **[BOT-041](completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md)** | **Stop Loss / Take Profit + Position Sizing theo rủi ro** | 🔴 **`L (Thinking)`** | `BOT-021` ✅, `BOT-045` ✅ | **Hoàn thành (19/08)**, bước 0 của Epic `BOT-109`. `PaperExchange.check_intrabar_stops()` mới (gọi mỗi bar dù không signal, khớp tại giá mục tiêu, SL thắng khi chạm cả hai — quyết định đã ghi trong docstring); `PositionSizingType.RISK_PERCENT`. Additive 100% — 19 test cũ `BOT-021`/`BOT-104` không sửa vẫn pass. 14 test mới + mutation-check 2 chỗ. |
| **[BOT-049](backlog/BOT-049_leverage_and_liquidation.md)** | **Đòn bẩy & Thanh lý** | 🔴 **`L (Thinking)`** | `BOT-041` ✅ | Isolated margin + liquidation price. ⚠️ **Rủi ro sai số cao nhất Epic** — bắt buộc đối chiếu nguồn ngoài (Binance Futures docs), không tự suy diễn công thức. |
| ✅ | **[BOT-050](completed/BOT-050_short_selling_support.md)** | **Short-selling** | 🔴 **`L (Thinking)`** | `BOT-041` ✅ | **Hoàn thành (20/08)**, bước 1 Epic `BOT-109`. `SignalAction` thêm `SHORT`/`COVER` riêng (không overload `BUY`/`SELL`, quyết định user chốt). `PaperExchange` mở rộng side-aware: PnL/slippage/SL-TP đảo chiều cho Short, `equity()` mark-to-market Short (gap tự phát hiện, không có trong task gốc), từ chối mix Long+Short cùng lúc. Tab/nhãn SHORT trong Trade Logs hoạt động thật. 45 test `PaperExchange` cũ pass không sửa, 18 test mới + mutation-check 3 chỗ (2 lần bắt được "false pass" do cấu hình mặc định che lỗi thật). |

**Nhóm C — Chiến lược** *(chỉ mục: [BOT-043](backlog/BOT-043_named_strategy_library.md))*

| Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :---: | :--- |
| ✅ **[BOT-051](completed/BOT-051_multi_ema_trend_follower.md)** | **Multi-EMA Trend Follower** | 🟢 **`S (Fast)`** | `BOT-046` ✅ | EMA 8/21/50/200 (đúng tên mockup), vào long khi xếp tầng đầy đủ, thoát khi phá thứ tự — 2 câu hỏi mở của task đã chốt với user trước khi code. |
| **[BOT-052](backlog/BOT-052_four_ema_pullback_sideways_filter.md)** | **4 EMA Pullback + Sideways Filter** | 🟡 **`M (Standard)`** | `BOT-046` ✅ | Chiến lược trong tiêu đề mockup của user. Phần khó: định nghĩa "sideways" bằng số liệu (ATR/ADX **chưa có**; `IIndicator.update()` chỉ nhận 1 float nên ATR đụng giới hạn kiến trúc). |
| **[BOT-053](backlog/BOT-053_qml_structure_breakout.md)** | **QML Structure Breakout** | 🔴 **`L (Thinking)`** | `BOT-046` ✅ | Nhận diện price-action pattern (Quasimodo), sinh "QML Score" cho Trade Logs + QML Signal Badges. Cần hạ tầng **swing high/low detection** (chưa có trong `domain/scripting/`). |
| ✅ | **[BOT-110](completed/BOT-110_ema_trend_confirm_pullback_strategy.md)** | **EMA Trend Confirm + Pullback + TP%** | 🟡 **`M (Standard)`** | `BOT-050` ✅ | **Hoàn thành (20/08)**, bước 3 Epic `BOT-109`. Port 1:1 từ Pine v6. `StrategyContext.current_position_side` mới (additive) giải quyết câu hỏi kiến trúc SELL/COVER mở sẵn trong task gốc. **Bug thật tự phát hiện khi viết test tick-safety**: bộ đếm xác nhận xu hướng đọc `series[0]` làm "giá trị nến trước" tự tham chiếu ngược provisional của chính nó qua nhiều `on_forming_bar_tick()` cùng 1 nến — sửa bằng `Series.committed()` mới (đọc lịch sử đã commit, bỏ qua provisional đang treo). 9 test mới + mutation-verify, full suite 1539 pass. |

> ⏸️ **SMC + Liquidity Sweep (BOT-054 cũ) đã bỏ khỏi phạm vi** — ghi chú đầy đủ để cân nhắc lại sau ở [BOT-043](backlog/BOT-043_named_strategy_library.md) mục 2.
> ⚠️ **Hạ tầng còn thiếu cho mọi chiến lược phân tích cấu trúc giá** ([BOT-043](backlog/BOT-043_named_strategy_library.md) mục 3): (1) chưa có công cụ phát hiện **swing high/low**; (2) **`Series` mặc định chỉ giữ 16 bar** (`DEFAULT_HISTORY`) — chọn có chủ đích cho lookback ngắn của indicator, nhưng nhiều khả năng **không đủ cho phân tích cấu trúc**. `Series(history=N)` đã hỗ trợ tuỳ chỉnh, cần đánh giá bao nhiêu là đủ.

**Nhóm D — Màn hình Backtest**

| Phase | Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **1** | ✅ **[BOT-022](completed/BOT-022_backtest_screen_static_ui.md)** | **Khung màn hình + Top Toolbar** | 🟡 **`M (Standard)`** | `BOT-021` ✅ | `BacktestView`/`BacktestPresenter` + Sidebar entry + chọn strategy/thời gian/vốn/timeframe + nút Chạy Backtest (background thread) + trạng thái Loading/Empty/Error. **Sau task này màn hình đã chạy được thật.** |
| **1** | ✅ **[BOT-055](completed/BOT-055_backtest_performance_metrics_panel.md)** | **Performance Metrics Panel** | 🟡 **`M (Standard)`** | `BOT-022` ✅ | 4 stat card (Net PnL / Max DD / Win Rate / Profit Factor) + mở rộng (Popup, 8 chỉ số). Sharpe/Sortino/Payoff ratio **chưa làm** — chưa chốt công thức. |
| **1** | ✅ **[BOT-056](completed/BOT-056_backtest_chart_canvas.md)** | **Chart Canvas** | 🟡 **`M (Standard)`** | `BOT-022` ✅, `BOT-055` ✅, `BOT-032` ✅ | 3 chế độ: Nến Nhật / Đường Vốn (Equity) / **Song song (Cả 2)**. Overlays: 4 EMA, Buy/Sell Flags, Volume. Chấm tròn màu lãi/lỗ trên đường Equity **chưa làm** (MarkerLayer chỉ vẽ trên main_plot). QML Badges chờ `BOT-053`. |
| **1** | ✅ **[BOT-057](completed/BOT-057_backtest_trade_logs_table.md)** | **Trade Logs Table** | 🟡 **`M (Standard)`** | `BOT-022` ✅, `BOT-056` ✅, `BOT-045` ✅ | §2.1 (bảng/lọc/tìm/export/phân trang) + §2.2 (**dòng mở rộng** 3 khối chi tiết, làm xong trong `BOT-045`). 37 test ban đầu, `ruff` sạch. |
| **1** | ✅ **[BOT-058](completed/BOT-058_backtest_config_driven_symbol_and_interval.md)** | **Symbol/Interval mặc định đọc từ Config** | 🟢 **`S (Fast)`** | `BOT-022` ✅ | Đọc `IConfig`'s `DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL` (đã có, chỉnh được qua Settings) — Backtest không còn phụ thuộc ngầm vào Dev Board. Đọc 1 lần lúc khởi tạo màn, fallback an toàn khi config trống/bẩn (không crash). 5 test mới, `ruff` sạch. |
| **1** | ✅ **[BOT-059](completed/BOT-059_backtest_inline_data_sync_affordance.md)** | **Nút "Đồng bộ ngay" khi thiếu dữ liệu** | 🟡 **`M (Standard)`** | `BOT-022` ✅, `BOT-058` ✅ | Backtest là tính năng chính, không được ngõ cụt khi thiếu dữ liệu. Nút sync tường minh (không tự động ngầm) + state machine `BacktestUiState` riêng thay `UIMode` dùng chung. 12 test mới, `ruff` sạch. |
| **1** | ✅ **[BOT-060](completed/BOT-060_backtest_chart_draws_strategy_own_indicators.md)** | **Chart vẽ đúng indicator của Strategy đang backtest** | 🟡 **`M (Standard)`** | `BOT-046` ✅, `BOT-047` ✅, `BOT-056` ✅ | Toggle từng cố định vẽ `ema_ribbon` (20/50/100/200) bất kể strategy nào đang chạy — marker Buy/Sell không khớp đường vẽ (bug user báo qua ảnh chụp thật). Giờ vẽ đúng `strategy.build_indicators()` — file mới `strategy_indicator_lines.py` (thuần Python), xoá hẳn phụ thuộc `IndicatorScriptRunner`/`ema_ribbon` khỏi màn Backtest. |
| **1** | ✅ **[BOT-064](completed/BOT-064_backtest_screen_indicator_script_picker.md)** | **Danh sách chọn Indicator Script (như Dev Board)** | 🟡 **`M (Standard)`** | `BOT-060` ✅ | Nút "Chỉ báo" mới (`IndicatorPickerMenu.qml`) mở dropdown checklist, tái dùng nguyên `IndicatorScriptListModel`/`IndicatorScriptRunner` của Dev Board — chạy **song song**, không thay thế `strategy_indicator_lines.py` của `BOT-060`. Gap chưa làm: script overlay chưa tự ẩn khi chuyển "Đường Vốn" (Equity-solo). |
| **1** | ✅ **[BOT-065](completed/BOT-065_backtest_script_overlay_hidden_in_equity_mode.md)** | **Ẩn overlay Script khi chuyển "Đường Vốn"** | 🟢 **`S (Fast)`** | `BOT-060` ✅, `BOT-064` ✅ | `_set_script_overlay_lines_visible()` mới, gọi từ `_on_chart_mode_changed` cạnh `_on_ema_toggled()` đã có — lặp `self._chart_script_runner.active`, chỉ ẩn script `overlay=True` (subplot như RSI/MACD không share trục giá, giữ nguyên hiển thị). Test tái hiện bug thật trước khi sửa (đúng `.agents/rules/code-rule.md`). |
| **1** | ✅ **[BOT-096](completed/BOT-096_truthful_backtest_exit_markers.md)** | **Backtest: Marker / Icon thoát LONG trung thực** | 🟢 **`S (Fast)`** | `BOT-056` ✅, `BOT-057` ✅ | Phân tách rõ ràng giữa `LONG ENTRY` ("MUA (LONG)") và `LONG EXIT` ("ĐÓNG LONG"), loại bỏ nhãn `Sell` gây hiểu nhầm sang lệnh SHORT; hiển thị trung thực tab `Bán (SHORT) [Chưa hỗ trợ]`. |
| **1** | ✅ **[BOT-097](completed/BOT-097_backtest_display_timezone_selector.md)** | **Backtest: Chọn múi giờ hiển thị (UTC vs Giờ hệ thống)** | 🟢 **`S (Fast)`** | `BOT-095D` ✅ | Selector múi giờ hiển thị trên toolbar (`UTC`, `Giờ hệ thống`, IANA zones), định dạng đồng bộ cho chart axis, tooltip, trade logs entry/exit; bảo toàn 100% dữ liệu UTC invariant trong engine/DB. |
| **1** | ✅ **[BOT-102](completed/BOT-102_backtest_symbol_picker.md)** | **Backtest: Modal chọn Symbol (Binance Exchange Info)** | 🟡 **`M (Standard)`** | `BOT-095E1` ✅ | Lấy trực tiếp danh sách 1361+ mã từ Binance REST API có tìm kiếm; sửa bug `_build_run_config()` bị gán nhầm default ETHUSDT. |
| **2** | ✅ **[BOT-104](completed/BOT-104_backtest_properties_and_broker_simulator_modal.md)** | **Backtest: Hộp thoại Đặc tính Chiến lược & Mô phỏng Môi giới** | 🔴 **`L (Thinking)`** | `BOT-022` ✅, `BOT-076` ✅, `BOT-095B` ✅ | Modal đa Tab chuẩn TradingView gom gọn Thông số, Vốn & Position Sizing (% Equity/USD), Pyramiding nhồi lệnh, Slippage trượt giá, Commission, Đòn bẩy & FSM Dirty Tracking. |
| ❌ | **[BOT-024](cancelled/BOT-024_backtest_screen_dynamic_ui.md)** | **~~Backtest Screen — Replay UI~~ — ĐÃ HUỶ** | — | — | Huỷ 2026-08-19, xem hồ sơ huỷ — trùng tính năng đã bị từ chối ở `BOT-076` §3.5. |

**Nhóm E — Quản trị Lệnh Nâng cao, Phân tích Lượng hóa & Tối ưu hóa Chiến lược**

| Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :---: | :--- |
| ✅ | **[Epic BOT-109](backlog/BOT-109_golden_strategy_ema_trend_confirm_pullback_epic.md)** | **Chuẩn Tham Chiếu Vàng — Thực thi Chiến lược "EMA Trend Confirm + Pullback + TP%"** | 🔴 **`L (Thinking)`** | `BOT-041` ✅, `BOT-050` ✅, `BOT-104` ✅ | **Hoàn thành (20/08)** — cả 4 bước (`BOT-041`/`BOT-050`/`BOT-110`/`BOT-111`) đã xong, xem mục Completed phía trên. `BOT-105A` không bắt buộc cho riêng golden strategy này, vẫn ở backlog riêng. |
| 🔴 | **[Epic EPIC-001](epics/EPIC-001_ema_trend_pullback_tradingview_cross_reference/README.md)** | **Đối chiếu `EmaTrendPullbackStrategy` với TradingView thật** | 🟡 **`M (Standard)`** | `BOT-110` ✅, `BOT-111` ✅ | Mới tạo (20/08) — chi tiết ở file riêng của epic, không lặp lại đây (quy ước mới, xem `Tasks/epics/README.md`). |
| 🟡 | **[Epic EPIC-002](epics/EPIC-002_static_type_checking_in_local_ci/README.md)** | **Kiểm tra kiểu tĩnh (`mypy`) trong CI cục bộ** | 🟢 **`S (Fast)`** | — | 4/5 task con xong (23/08) — cổng `mypy` đã sống trong `ci-local.ps1 -Full`; `EPIC-002E` gỡ `sagittarius_engine` khỏi `ignore_missing_imports` (engine ship `py.typed` từ 2.2.0, đang cài 2.3.0) nên biên giới app↔engine không còn bị hạ xuống `Any`. Chi tiết ở file riêng của epic (`Tasks/epics/README.md`). |
| 🟡 | **[Epic EPIC-003](epics/EPIC-003_presenter_and_god_file_decomposition/README.md)** | **Phân rã Presenter/File quá tải (Coordinator Pattern, Domain Policy, QML component split)** | 🔴 **`L (Thinking)`** | `EPIC-002` (mypy gate bảo vệ trong lúc refactor) | 3/6 task con xong (25/08) — chi tiết ở file riêng của epic (`Tasks/epics/README.md`). |
| 🟡 | **[Epic EPIC-004](epics/EPIC-004_static_security_and_quality_analysis/README.md)** | **Static security & quality analysis gate (Bandit + magic-number + code-smell qua Ruff)** | 🟢 **`S (Fast)`** | — | 3/4 task con xong (24/08) — gate `S/PLR2004/B/SIM/ERA/N` đã fail-cứng, ~48 finding thật đã sửa, false positive được ignore theo phạm vi; còn task tài liệu `C`. Chi tiết ở file riêng của epic (`Tasks/epics/README.md`). |
| **[Epic BOT-105](backlog/BOT-105_advanced_order_execution_and_risk_epic.md)** | **Quản trị Lệnh Nâng cao & Kiểm soát Rủi ro (SL/TP, Trailing, Magnifier)** | 🔴 **`L (Thinking)`** | `BOT-041` ✅, `BOT-076` ✅ | Quản trị lệnh chuyên nghiệp: Trailing Stop, Break-Even Stop, Partial TP (`BOT-105A`), Bar Magnifier phân xử râu nến chạm cả SL/TP bằng tick 1s (`BOT-105B`). |
| 🟡 | **[Epic BOT-106](backlog/BOT-106_advanced_financial_analytics_and_reports_epic.md)** | **Báo cáo & Phân tích Chỉ số Tài chính Nâng cao (Sharpe, Sortino, MAE/MFE)** | 🟡 **`M (Standard)`** | `BOT-055` ✅, `BOT-057` ✅ | **1/3 xong (20/08)**: `BOT-106A` ✅ (Sharpe/Sortino/Calmar & Max Drawdown Duration), còn lại `BOT-106B` (MAE/MFE từng trade), `BOT-106C` (Drawdown Underwater Chart & Monthly Returns Heatmap). |
| **[Epic BOT-107](backlog/BOT-107_strategy_robustness_and_monte_carlo_epic.md)** | **Kiểm định Độ tin cậy Chiến lược & Mô phỏng Monte Carlo (Anti-Overfitting)** | 🔴 **`L (Thinking)`** | `BOT-021` ✅, `BOT-078` ✅ | Phân tách In-Sample / Out-of-Sample đối sánh mù (`BOT-107A`), mô phỏng ngẫu nhiên 10,000 kịch bản Monte Carlo đánh giá xác suất phá sản (Risk of Ruin %) (`BOT-107B`). |
| **[Epic BOT-108](backlog/BOT-108_strategy_parameter_optimization_epic.md)** | **Tối ưu hóa Tham số Chiến lược Tự động (Grid Search & Heatmap)** | 🔴 **`L (Thinking)`** | `BOT-044` ✅, `BOT-095C` ✅ | Quét lưới tham số đa tiến trình ProcessPool (`BOT-108A`), bảng xếp hạng Leaderboard + Bản đồ nhiệt tham số 2D tìm vùng bình nguyên ổn định (`BOT-108B`). |
| **[Epic BOT-115](backlog/BOT-115_backtest_report_persistence_epic.md)** | **Lưu trữ & Nạp lại Báo cáo Backtest (Report Persistence & Portability)** | 🔴 **`L (Thinking)`** | `BOT-021` ✅, `BOT-095B` | Xuất một lần chạy ra file `.sagi-report.json` độc lập (kết quả + cấu hình + provenance), nạp lại sau nhiều ngày trên máy khác mà không chạy lại engine, và so sánh 2 báo cáo cạnh nhau. JSON có `schema_version`, **không bao giờ `pickle`** (file report là input không tin cậy). |
| **[BOT-115A](backlog/BOT-115A_backtest_report_schema_and_serializer.md)** | **Schema `BacktestReport` & Serializer JSON** | 🟡 **`M (Standard)`** | `BOT-021` ✅, `BOT-104` ✅ | Thuần domain, zero UI: dataclass + `to_json`/`from_json` + provenance + validate nghiêm ngặt (whitelist `strategy_key`/enum, tính lại metrics để phát hiện file bị sửa tay). Equity curve lưu dạng cột cho gọn. |
| **[BOT-115B](backlog/BOT-115B_backtest_report_export_ui.md)** | **Xuất báo cáo từ màn Backtest** | 🟢 **`S (Fast)`** | `BOT-115A` | Nút "Lưu báo cáo" + `QFileDialog` theo đúng khuôn `_on_trade_log_export_requested()` đã có, thư mục `reports/` mặc định. Ghi config của **lần chạy đã sinh ra kết quả**, không phải toolbar đang gõ dở. |
| **[BOT-115C](backlog/BOT-115C_backtest_report_import_and_readonly_state.md)** | **Nạp báo cáo & Chế độ xem chỉ đọc** | 🔴 **`L (Thinking)`** | `BOT-115A`, `BOT-095B` | State `VIEWING_IMPORTED_REPORT` để dirty-tracking của `BOT-095B` không bắn banner vô nghĩa; badge cảnh báo khi provenance lệch; thiếu nến trong vault thì hạ cấp có giải thích + nút sync (`BOT-059`) thay vì chart rỗng. |
| **[BOT-115D](backlog/BOT-115D_backtest_report_side_by_side_comparison.md)** | **So sánh 2 báo cáo cạnh nhau** | 🟡 **`M (Standard)`** | `BOT-115C` | Modal 2 cột: diff cấu hình (tái dùng `compute_diff_summary()`), metrics side-by-side có tô màu đúng chiều (`max_drawdown` nhỏ hơn là tốt hơn), 2 đường vốn chồng nhau đã chuẩn hoá cùng mốc. |

**Nhóm F — Quản trị Cơ sở Dữ liệu & Kho Dữ liệu Thị trường Nâng cao (Market Data Hub & Storage Vault)**

| Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :---: | :--- |
| 🟡 **[Epic BOT-112](backlog/BOT-112_data_management_and_market_vault_overhaul_epic.md)** | **Đại tu Quản trị Cơ sở Dữ liệu Thị trường — Market Data Hub & Storage Vault Overhaul** | 🔴 **`L (Thinking)`** | `BOT-004` ✅, `BOT-030` ✅ | **4/5 xong (21/08)**: `BOT-112A` ✅ (đa timeframe + auto-discover), `BOT-112B` ✅ (KLine Inspector + kiểm định toàn vẹn), `BOT-112C` ✅ (gap visualizer + selective repair), `BOT-112E` ✅ (hỗ trợ `1s`). Còn `BOT-112D` (Import/Export CSV/Parquet & VACUUM). |
| ✅ **[BOT-112A](completed/BOT-112A_data_management_core_actions_and_timeframe_support.md)** | **Hoàn thiện Tác vụ Cốt lõi & Hỗ trợ Đa Khung thời gian** | 🟡 **`M (Standard)`** | `BOT-004` ✅ | Gỡ bỏ placeholder header vô dụng, thêm selector Timeframe 1m-1d, Auto-discover shards on screen load, xóa dữ liệu thật & tích hợp Binance Symbol Picker. |
| ✅ **[BOT-112B](completed/BOT-112B_kline_data_inspector_and_integrity_audit.md)** | **Bảng Tra cứu Nến KLine Inspector & Kiểm định Tính toàn vẹn** | 🟡 **`M (Standard)`** | `BOT-112A` | Xem chi tiết nến thô OHLCV phân trang, nhảy nhanh theo Timestamp, kiểm định nến bất thường (High < Low, Volume < 0, trùng lặp). |
| ✅ **[BOT-112C](completed/BOT-112C_gap_detection_visualizer_and_selective_repair.md)** | **Trực quan hóa Lỗ hổng & Vá Từng Đoạn Dữ liệu (Selective Gap Repair)** | 🔴 **`L (Thinking)`** | `BOT-112A` | Thanh Timeline độ phủ dữ liệu trực quan, danh sách chi tiết các lỗ hổng thời gian và nút "Vá Lỗ Hổng Này" chỉ tải bù đúng đoạn thiếu. |
| **[BOT-112D](backlog/BOT-112D_market_data_import_export_csv_parquet.md)** | **Nhập / Xuất Dữ liệu Lịch sử (CSV/Parquet) & Bảo trì Ổ cứng** | 🟡 **`M (Standard)`** | `BOT-112A` | Xuất dữ liệu KLines ra CSV/Parquet/JSON, nạp file CSV nến offline vào SQLite, nút bảo trì thu hồi dung lượng đĩa `VACUUM` & `WAL checkpoint`. |

**Nhóm G — Đề xuất Cải tiến Giao diện & Trải nghiệm Người dùng (UI / UX Proposals — PROP Series)**

| Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :---: | :--- |
| **[PROP-001](backlog/PROP-001_trade_entry_exit_connection_line.md)** | **Đường Nối Lệnh Vào - Ra (Trade Entry-Exit Connection Line on Hover & Selection)** | 🟡 **`M (Standard)`** | `BOT-056` ✅ | Khi rê chuột vào marker hoặc chọn dòng trong Trade Logs, vẽ đường nét đứt mờ (xanh cho Win, đỏ cho Loss) nối từ Entry sang Exit, hiển thị thời gian giữ lệnh & % PnL. |
| **[PROP-002](backlog/PROP-002_bidirectional_table_chart_interaction.md)** | **Tương Tác Hai Chiều Bảng Trade Logs & Biểu Đồ (Bi-directional Table & Chart)** | 🟡 **`M (Standard)`** | `BOT-056` ✅, `BOT-057` ✅ | Click hàng trong Trade Logs $\rightarrow$ chart tự động smooth pan & highlight marker; Click marker trên chart $\rightarrow$ Trade Logs tự lật đến đúng trang & chọn hàng. |
| **[PROP-003](backlog/PROP-003_zoom_adaptive_trade_marker_details.md)** | **Chi Tiết Marker Thích Ứng Mức Phóng To (Zoom-Adaptive Trade Marker PnL Details)** | 🟡 **`M (Standard)`** | `BOT-098A` ✅ | Zoom xa: Giữ tam giác tối giản; Zoom cực gần (< 30 nến): Tự động hiển thị mini-badge % PnL và nhãn lệnh (TP, SL, Sig) bên cạnh tam giác. |
| **[PROP-004](backlog/PROP-004_advanced_chart_marker_filters.md)** | **Bộ Lọc Marker Nâng Cao Trên Biểu Đồ Backtest (Advanced Chart Marker Filter Controls)** | 🟢 **`S (Fast)`** | `BOT-056` ✅ | Dropdown lọc nhanh marker trên chart: Tất cả / Chỉ lệnh Thắng / Chỉ lệnh Thua / Chỉ Long / Chỉ Short / Lọc theo ngưỡng $|PnL| \ge X\%$. |

**Ngoài nhóm**

| Task ID | Tên Nhiệm vụ | Độ phức tạp / Agent | Dependencies | Mô tả ngắn |
| :--- | :--- | :---: | :---: | :--- |
| **[Epic BOT-042](backlog/BOT-042_tick_level_strategy_engine_support.md)** | **Tick-Level Indicator/Strategy Engine Support** *(nay thuộc [Epic `BOT-073`](backlog/BOT-073_realtime_tick_backtest_epic.md))* | 🔴 **`L (Thinking)`** | `BOT-020` ✅, `BOT-026` ✅ | Chặn 2/4 Execution Trigger Rule. ✅ **Câu hỏi kiến trúc đã được user chốt: hướng (b)** — indicator tính lại mỗi tick; action item cụ thể nay đã có ở `BOT-042` §4. User tự làm phần **nạp** tick 1s; task này chỉ lo phần **tiêu thụ**. Đã chia 4 task con `BOT-042A`…`D` (19/08) — xem file epic. |

> **Đang treo, chưa tạo task**: nút "AI Chẩn đoán" trong spec (user chốt **hoãn** — chưa rõ dùng LLM API thật hay heuristic nội bộ, ảnh hưởng chi phí/hạ tầng nên không đoán); và Execution Trigger Rule "On order filled" (chưa rõ nghĩa trong ngữ cảnh backtest). Cả 2 ghi lại ở [BOT-040](backlog/BOT-040_backtest_screen_full_feature_epic.md) mục 3.
