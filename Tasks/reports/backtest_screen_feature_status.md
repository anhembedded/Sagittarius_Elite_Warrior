# 🎯 Backtest Screen — Feature Status & Sanity Coverage

> Phạm vi: màn hình **Backtest** (`BackTestPresenter` / `BackTestView` /
> `BackTestViewModel`, `src/presentation/ui/screens/backtest/`), thuộc Epic
> [BOT-006](../backlog/BOT-006_backtest_engine_execution.md) Phase 1 và Epic
> [BOT-040](../backlog/BOT-040_backtest_screen_full_feature_epic.md).
>
> Grounded trực tiếp vào code thật tại commit `2d7e643` (nhánh
> `master-warrior`) — không suy đoán, mỗi hàng trỏ đúng file/class/control
> thật để verify lại nhanh. Cùng tinh thần với
> [Dev Board Test Case Catalog](dev_board_user_end_test_cases.md).
>
> **Cập nhật lại file này khi 1 task Backtest khác hoàn thành** (`BOT-057`,
> `BOT-058`, `BOT-059`, hoặc bất kỳ task nào ở Epic `BOT-040` chạm màn
> Backtest) — cùng bước với việc cập nhật `ROADMAP.md`, đừng để lệch.

**Chú giải cột Sanity** — 3 tầng khác nhau, đừng nhầm "có sanity = test kỹ":
- **Unit**: test hành vi thật (mock dispatcher/thread manager, real ViewModel,
  đôi khi cả QML thật) — nằm ở `tests/unit/presentation/ui/screens/`.
- **Sanity (DI)**: chỉ verify **DI có wire đúng không** (command → đúng
  handler, registry có đúng key) qua app boot thật — nằm ở
  [`tests/sanity/test_backtest_screen_di_sanity.py`](../../tests/sanity/test_backtest_screen_di_sanity.py).
- **Sanity (UI)**: verify **`BackTestView`/`BackTestPresenter` construct
  được thật** trên container thật (không mock dispatcher) + 2 tài liệu QML
  parse sạch — nằm ở
  [`tests/sanity/test_backtest_screen_ui_sanity.py`](../../tests/sanity/test_backtest_screen_ui_sanity.py).
  **Cố ý chỉ dừng ở construction** — không click nút, không dispatch thật,
  không chạy nền — để không lấn vào vùng crash đã biết của `BOT-038`.

  Không tầng Sanity nào test hành vi/UI thật (click → kết quả đúng) — 1 tính
  năng có ✅ Sanity vẫn có thể có bug hành vi nếu cột Unit trống.

---

## Bảng tính năng

| Tính năng | Trạng thái | Task | Grounding (code) | Unit test | Sanity |
|---|:---:|---|---|---|:---:|
| Sidebar route "Backtest Engine" (không còn placeholder) | ✅ | `BOT-022` | `main_window.py` — `NavItem("Backtest Engine", "backtest", ...)`, `_setup_router()` đăng ký `BackTestPresenter`/`BackTestView` | — | — |
| Màn hình construct được thật trên container thật (không mock), 2 QML doc parse sạch | ✅ | — | `BackTestView`/`BackTestPresenter` | `test_qml_documents_load_without_errors` (mock container) | ✅ (container thật) |
| Strategy dropdown đọc `StrategyRegistry` thật | ✅ | `BOT-022` | `BackTestPresenter.__init__` set `strategyOptions` từ `StrategyRegistry.available()`; QML `cboBacktestStrategy` | `test_strategy_options_loaded_from_registry_on_init` | `test_strategy_registry_has_the_default_backtest_strategy` |
| Timeframe picker | ✅ | `BOT-022` | QML `cboBacktestTimeframe`, `BackTestViewModel.selectedTimeframe` | `test_run_backtest_submits_background_task_and_locks_fsm` (default `"1m"`) | — |
| Khung thời gian: 7/30/90/365 ngày / toàn bộ / tuỳ chỉnh | ✅ | `BOT-022` | `time_range_preset.py` (`TimeRangePreset`, `resolve_time_range`), QML `cboBacktestRange`/`txtBacktestRangeStart`/`txtBacktestRangeEnd` | `test_time_range_preset.py` (5 test), `test_custom_range_*` trong `test_backtest_presenter.py` | — |
| Vốn ban đầu | ✅ | `BOT-022` | QML `txtBacktestCapital`, validate ở `_build_run_config` | `test_invalid_capital_is_rejected_without_submitting`, `test_non_positive_capital_is_rejected` | — |
| Nút "Chạy Backtest" — dispatch nền, không chặn UI | ✅ | `BOT-022` | `_on_run_backtest` → `IThreadManager.submit(_run_backtest, ...)`; QML `btnRunBacktest` | `test_run_backtest_submits_background_task_and_locks_fsm`, `test_qml_run_button_click_requests_a_run` | `test_backtest_command_resolves_to_its_handler[RunStaticBacktestCommand]` |
| Trạng thái Loading / Lỗi / Không có dữ liệu / 0 trade (phân biệt rõ) | ✅ | `BOT-022` | `_on_backtest_succeeded`/`_on_backtest_empty`/`_on_backtest_failed`, `UIMode IDLE/LOCKED/ERROR` | `test_no_historical_data_reports_empty_message_and_unlocks`, `test_zero_trades_reports_empty_message_with_the_metrics`, `test_dispatch_exception_reports_error_and_unlocks` | — |
| "Thông số Bot" — khoá tạm | ✅ (khoá có chủ đích) | `BOT-022` | QML `btnBacktestBotParams`, `enabled: false` | `test_bot_params_button_is_disabled` | — |
| Execution Trigger Rule — khoá về "On bar close" | ✅ (khoá có chủ đích) | `BOT-022` | `OrderExecutionMenu.qml`, item 0 `locked: true`, item 1-3 disable | — | — |
| 4 stat card thật (Net PnL / Max DD / Win Rate / Profit Factor) | ✅ | `BOT-055` | `performance_metrics_view.py` (`build_primary_stat_cards`), `MetricCard` × 4 trong `BackTestTopPanel.qml` | `test_performance_metrics_view.py` (10 test) | — |
| Max Drawdown — số tiền tuyệt đối (không chỉ %) | ✅ | `BOT-055` | `compute_max_drawdown_amount()` — cố ý lặp lại đúng thuật toán của `BacktestMetrics._max_drawdown_percent` | `test_max_drawdown_amount_agrees_with_backtest_metrics_percent` | — |
| Profit Factor = `inf` hiện "∞", không crash | ✅ | `BOT-055` | `_profit_factor_text()` | `test_infinite_profit_factor_displays_as_the_infinity_symbol_not_a_crash` | — |
| 0 trade vẫn ra đủ 4 card (đọc 0), không ẩn panel | ✅ | `BOT-055` | `_on_backtest_succeeded` luôn gọi `set_stat_cards` khi có `BacktestResult`, kể cả rỗng | `test_zero_trades_produces_four_cards_all_reading_zero_without_crashing` | — |
| "Mở rộng chỉ số chi tiết" — 8 chỉ số phụ | ✅ | `BOT-055` | `build_extended_stat_cards()`, `Popup extendedMetricsPopup` trong QML | `test_extended_cards_cover_every_remaining_metrics_field` | — |
| Chart Canvas — fetch klines thật cho khoảng backtest | ✅ | `BOT-056` | `_fetch_and_emit_chart_data` dispatch `GetHistoricalKlinesQuery` | `test_successful_run_fetches_klines_and_renders_the_ohlc_chart` | `test_backtest_command_resolves_to_its_handler[GetHistoricalKlinesQuery]` |
| Chế độ "Nến Nhật" (OHLC) | ✅ | `BOT-056` | `BackTestView._render_chart()` nhánh OHLC/BOTH | `test_successful_run_fetches_klines_and_renders_the_ohlc_chart` | — |
| Chế độ "Đường Vốn" (Equity) | ✅ | `BOT-056` | `equity_curve_to_candles()` (nến giả `open=high=low=close=equity`), tái dùng `set_chart_type("line")` | `test_switching_to_equity_mode_renders_a_line_from_the_equity_curve` | — |
| Chế độ "Song song" (OHLC + Equity subplot) | ✅ | `BOT-056` | `ChartCard.add_subplot_indicator` (X-linked, hạ tầng từ MACD/`BOT-032`) | `test_switching_to_both_mode_adds_an_equity_subplot`, `test_switching_away_from_both_mode_removes_the_equity_subplot` | — |
| Toggle 3-mode + overlay (native, ngoài QML) | ✅ | `BOT-056` | `chart_controls.py` (`BacktestChartControls`, `btnChartMode_*`), gắn vào `ChartCard.add_to_header` | `test_mode_buttons_switch_the_chart_mode_end_to_end` | — |
| 4 EMA overlay (tái dùng `ema_ribbon`) | ✅ | `BOT-056` | `IndicatorScriptRunner` batch feed, `_CHART_EMA_SCRIPT_KEY = "ema_ribbon"`; **đã fix duplicate-per-run bug** (`clear_from_chart` trước mỗi lần chạy) | `test_ema_toggle_is_a_no_op_when_the_script_is_not_registered`, `test_clear_from_chart_is_called_before_each_new_run_not_after` | `test_indicator_script_registry_has_the_chart_ema_overlay_script` |
| Buy/Sell flags từ `result.trades` | ✅ | `BOT-056` | `trade_flag_markers()`, `set_script_markers` (hạ tầng `BOT-032`) | `test_trade_flags_toggle_draws_and_clears_markers`, `test_chart_canvas_view.py` (5 test) | — |
| Volume toggle | ✅ | `BOT-056` | `ChartCard.set_volume_visible()` (method mới, không đụng core) | — | — |
| Top panel đủ cao để hiện value/badge của stat card (không bị cắt) | ✅ (đã fix, tìm ra khi chạy thật) | `BOT-022`/`055` fix | `_TOP_PANEL_HEIGHT = 190` (`backtest_view.py`) | — | — |

### Chưa có (🔲) — đã có task backlog giữ chỗ

| Tính năng | Task | Ghi chú |
|---|---|---|
| Trade Logs Table thật (lọc/tìm/export/dòng mở rộng) | [`BOT-057`](../backlog/BOT-057_backtest_trade_logs_table.md) | `BackTestTradeLogs.qml` hiện vẫn là mockup tĩnh 5 dòng giả ("#216 vị thế mua" lặp lại) |
| Symbol/Interval mặc định đọc từ `IConfig`, không hardcode | [`BOT-058`](../backlog/BOT-058_backtest_config_driven_symbol_and_interval.md) | Phát hiện khi chạy thật — Backtest hiện vô tình phụ thuộc cùng giá trị Dev Board hay sync |
| Nút "Đồng bộ ngay" khi thiếu dữ liệu + `BacktestState` machine riêng | [`BOT-059`](../backlog/BOT-059_backtest_inline_data_sync_affordance.md) | Hiện gặp "No historical data" là ngõ cụt, phải tự rời màn |
| Modal "Cấu hình Thông số Bot" (form động theo schema) | [`BOT-044`](../backlog/BOT-044_param_schema_core.md)/[`046`](../backlog/BOT-046_strategy_param_plumbing.md)/[`047`](../backlog/BOT-047_dynamic_params_form_ui.md) | Nút đã có (`btnBacktestBotParams`), đang khoá |
| Execution Trigger Rule — tick-level (3 lựa chọn còn lại) | [`BOT-042`](../backlog/BOT-042_tick_level_strategy_engine_support.md) | Chưa có action item cụ thể, còn câu hỏi kiến trúc |
| SL/TP + Position sizing theo rủi ro | [`BOT-041`](../backlog/BOT-041_stop_loss_take_profit_and_risk_sizing.md) | — |
| Đòn bẩy & Thanh lý | [`BOT-049`](../backlog/BOT-049_leverage_and_liquidation.md) | Rủi ro sai số cao nhất Epic |
| Short-selling | [`BOT-050`](../backlog/BOT-050_short_selling_support.md) | — |
| Thêm chiến lược ngoài `ema_crossover` | [`BOT-051`](../backlog/BOT-051_multi_ema_trend_follower.md)/[`052`](../backlog/BOT-052_four_ema_pullback_sideways_filter.md)/[`053`](../backlog/BOT-053_qml_structure_breakout.md) | Dropdown hiện chỉ có 1 lựa chọn thật |
| Dynamic/replay mode (tua nến, play/pause) | [`BOT-023`](../backlog/BOT-023_dynamic_backtest_engine.md)/[`BOT-024`](../backlog/BOT-024_backtest_screen_dynamic_ui.md) | Epic BOT-006 Phase 2, chưa bắt đầu |
| Symbol picker | *(chưa có task)* | **Gap thật, chưa ai giữ chỗ** — Backtest hiện luôn chạy 1 symbol mặc định (`ETHUSDT`, sẽ đổi thành config-driven ở `BOT-058` nhưng vẫn là 1 symbol cố định, không chọn được) |

### Giới hạn đã biết, cố ý không làm (không phải bug)

- **Chấm tròn màu lãi/lỗ trên đường Equity** (`BOT-056`) — `MarkerLayer` chỉ
  vẽ được trên `main_plot`, không vẽ được lên subplot Equity ở chế độ "Song
  song". Cần mở rộng `ChartCard` mới làm được, cố ý để lại làm follow-up.
- **Sharpe / Sortino / Payoff ratio** (`BOT-055`) — chưa chốt công thức
  (kỳ tính return, risk-free rate), quyết định "hỏi lại khi tới lúc làm".
- **QML Signal Badges** — chờ `BOT-053` (chưa có chiến lược QML nào tồn tại
  để sinh badge).

---

📄 Xem thêm: [Dev Board Test Case Catalog](dev_board_user_end_test_cases.md) · [ROADMAP.md](../ROADMAP.md)
