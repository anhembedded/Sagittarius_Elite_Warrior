# EPIC-006E — Backtest (top panel / trade logs / 11 modal) → QtWidgets

**Thuộc:** [`EPIC-006`](../README.md)
**Trạng thái:** ✅ Xong (2026-08-24)

---

## Phạm vi thật — lớn hơn ước lượng ban đầu

Đo được sau khi bắt đầu: `backtest_presenter.py` (2735 dòng) + `test_backtest_presenter.py`
(~3973 dòng, trộn lẫn cả top panel/trade logs/modal trong 1 file) + ~5 file test khác — tổng
**~7800 dòng test** liên quan riêng Backtest. Lớn hơn hẳn Sidebar+DevBoard cộng lại. Do
`test_backtest_presenter.py` trộn lẫn cả 3 phần, không tách gọn thành 3 lần gate/commit như kế
hoạch ban đầu (khác `EPIC-005E`) — làm xong toàn bộ code (top panel + trade logs + 11 modal),
rồi rewrite test 1 lần, gate/commit 1 lần cho cả epic.

## Kiến trúc

- **Top panel** (`backtest_top_panel.py`, `BackTestTopPanel(QWidget)`): toolbar 9 nút (symbol/
  strategy/timeframe/range/timezone/capital/order-exec/indicator-picker/bot-params) + nút Run,
  4 banner (progress/preview/stale/coverage), stat-cards row / result box. Không còn cơ chế đọc
  `implicitHeight` từ QML — layout QtWidgets tự báo `sizeHint()` đúng.
- **Trade logs** (`backtest_trade_logs_panel.py`, `BackTestTradeLogsPanel(QWidget)`): tab
  Trades/Logs (tái dùng `LogPanelWidget` từ EPIC-005E/006D), filter tabs, bảng trade log tự
  build lại toàn bộ mỗi khi `tradeLogRowsChanged` (cùng pattern "rebuild, không diff" của
  `DevBoardPanel._rebuild_script_rows()`), pagination.
- **11 modal** (`backtest_modals.py`) — mỗi modal kế thừa `Overlay` (engine, EPIC-006B), orchestrator
  `BackTestModalsHost` thay hẳn `BackTestModals.qml` + `OverlayHost`/`QQuickWidget`: `QDialog`
  thật tự modal + tự center, không cần host full-window click-through nữa (lý do BOT-087 tồn
  tại — QML Popup cần host — không còn áp dụng).
- **`BotParamsDialog.qml` (200 dòng) không port** — xác minh chết thật: `git grep 'BotParamsDialog {'`
  không có instantiation nào, `StrategyPropertiesModal.qml` (BOT-104) đã thay thế hoàn toàn.

## Quyết định kiến trúc giữa chừng: `SelectableCard` (engine)

User hỏi thẳng: sao viết `QPushButton` tay cho time-range picker thay vì dùng Card của engine?
Đúng — pattern "list item chọn-1, viền accent khi selected" lặp lại ở **5 picker**
(Strategy/Timeframe/Symbol/TimeRange/Timezone), đủ ngưỡng promote. `Card` hiện tại không có
semantics click/selected (chỉ là khung tĩnh có title), nên thêm **`SelectableCard(Panel)`** mới
vào `pyside_mvc.widgets` (Sagittarius_Engine, nhánh `task/selectable-card-widget`, merge `main`
tại `1358e3c`): `clicked` signal qua `mousePressEvent`/`mouseReleaseEvent` (press+release cùng
nằm trong bounds), property `selected`, role mới `StyleRole.SELECTABLE_CARD` +
`WidgetState.SELECTED` trong `style.py` (token-driven, không hex literal ngoài `style.py`).
6 test mới ở engine (`897 → 903 passed`). `_selectable_list_card()`/`_selectable_grid_card()`
trong `backtest_modals.py` dùng chung `SelectableCard` cho cả 5 picker.

## Bug thật tìm được khi port: numeric stepper của `BotParamField.qml` bị thiếu

`test_up_key_steps_a_visible_numeric_parameter_through_the_view_model` (đã có từ trước) fail
sau port đầu tiên — QML's `Keys.onPressed`/`WheelHandler` (mũi tên Lên/Xuống, cuộn chuột step
qua `viewModel.step_bot_param_value()`, chuẩn hoá phía Python chứ không tính bằng JS) bị bỏ sót
hoàn toàn trong `_BotParamFieldWidget` bản đầu. Sửa bằng `_NumericStepLineEdit(QLineEdit)` mới,
override `keyPressEvent`/`wheelEvent`, verify lại bằng chính test cũ (không viết test mới để
che dấu — dùng đúng test đã bắt được bug).

## Bug KHÔNG liên quan phát hiện giữa chừng — note riêng, không sửa ở đây

**BUG-041** (`Tasks/bug_report/incomplete/`): app không thoát tiến trình thật khi đóng lúc có
job nền chạy trên `ThreadManager` (`ThreadManagerExtension.shutdown(wait=False)` không cứu được
— CPython's `concurrent.futures.thread._python_exit` luôn join mọi worker thread bất kể
`wait=`). Phát hiện lúc user tự chạy app tay, xác minh nguyên nhân bằng code thật + source
CPython, note lại rồi tiếp tục epic theo yêu cầu user — không phải QML/EPIC-006.

## Cleanup ruff --fix phạm vi rộng

`ruff check --fix .` (không path-scope) tự sửa luôn 16 file `scripts/*.py` không liên quan
(import-sort thuần tuý, an toàn nhưng ngoài phạm vi commit này) — revert lại bằng
`git checkout --`, chạy `ruff check`/`ruff format` scoped đúng các file EPIC-006E đã sửa.

## Test — viết lại toàn bộ 1 lần

11 file test: `test_backtest_view_layout.py` (rewrite toàn bộ, 15 test), `test_backtest_presenter.py`
(170 test, 15 sửa), `test_backtest_popups_overlay.py` (rewrite toàn bộ, 9 test), `test_backtest_bottom_tabs.py`,
`test_backtest_progress_cancel_qml.py`, `test_backtest_user_flow.py` (integration, 4 test),
`test_backtest_screen_ui_sanity.py`, `test_backtest_native_chart_di_sanity.py`,
`test_bug031_cross_thread_timer.py` (xoá 1 test — regression class không còn khả năng xảy ra),
`test_bot_params_dialog_qml.py`, `test_order_execution_modal.py`, `test_strategy_properties_modal.py`.

## Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`, `1815 passed / 53 sanity`
(sanity giảm 1 vì xoá `test_backtest_screen_qml_parses_clean_against_real_theme_and_icons` —
không còn QML để parse). Log verified sạch (`grep FAILED|ERROR|Traceback` rỗng).
