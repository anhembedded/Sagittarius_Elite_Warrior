# Nhiệm vụ: Danh sách chọn Indicator Script cho màn Backtest (như Dev Board)

> Phụ thuộc `BOT-060` ✅ (chart Backtest hiện vẽ đúng indicator của
> **strategy** đang chọn). Task này bổ sung khả năng bật thêm **indicator
> script** tham khảo (RSI, MACD, EMA Ribbon...) — độc lập với strategy,
> giống hệt "CUSTOM SCRIPTS" checklist bên Dev Board.

## 1. Mục tiêu

User phát hiện: màn Backtest hiện **không có cách nào bật thêm 1 indicator
script tham khảo** trong lúc backtest (vd bật RSI để tự confirm tín hiệu
strategy). Chart chỉ vẽ được: (1) indicator riêng của strategy đang chọn —
tự động, không tắt được (`BOT-060`), (2) Volume, (3) Buy/Sell flags. Dev
Board có hẳn 1 checklist "CUSTOM SCRIPTS" cho việc này
(`IndicatorScriptListModel`/`DevBoardPanel.qml`) nhưng Backtest chưa từng có
tương đương.

Đối chiếu mockup gốc (`BOT-040`): mục "Toggle 4 EMA" trong spec chỉ định
nghĩa **1 overlay cố định**, chưa bao giờ có ý định làm cả danh sách script
chọn được — đây là tính năng mới, không phải việc bị bỏ sót từ `BOT-022`/
`BOT-056`.

## 2. Đã có sẵn để tái dùng (không viết lại)

- **`IndicatorScriptListModel`** (`presentation/ui/screens/dashboard/
  indicator_script_list_model.py`) — `QAbstractListModel` đọc từ
  `IndicatorScriptRegistry.available()`, không gắn riêng với Dashboard, có
  thể tạo thêm 1 instance riêng cho `BackTestViewModel` (không share
  instance với Dev Board — 2 màn bật/tắt độc lập nhau).
- **`IndicatorScriptRunner`** (`presentation/ui/screens/dashboard/
  indicator_script_runner.py`) — đã hỗ trợ sẵn `rebuild()`/`feed_all()`
  (chế độ batch, đúng cái Backtest cần) từ hồi `BOT-056` (đã bị **gỡ khỏi
  `backtest_presenter.py` ở `BOT-060`** vì lúc đó dùng sai mục đích — vẽ
  `ema_ribbon` cố định thay vì indicator của strategy. Giờ đưa lại đúng
  mục đích: vẽ **thêm** script user tự chọn, **song song** với
  cơ chế `strategy_indicator_lines.py` của `BOT-060`, không thay thế nó.
- Namespace tên đường đã tách sẵn, không đụng nhau: `IndicatorScriptRunner`
  dùng `qualified_line_name(script_key, line_name)` (có dấu `:`), còn
  `strategy_indicator_lines.py` (`BOT-060`) dùng tên trần (`ema_fast`...) —
  2 tập tên không thể trùng.
- Checklist UI mẫu: `DevBoardPanel.qml` dòng ~295-338 (`Repeater { model:
  viewModel.scriptModel }`, mỗi dòng 1 `StyledCheck`).

## 3. Các bước thực hiện (Action Items)

- [ ] `BackTestViewModel`: thêm `self._script_model =
  IndicatorScriptListModel(self)`, property `scriptModel` (đúng pattern
  `DashboardQmlViewModel.scriptModel`).
- [ ] `BackTestPresenter`: gọi `self._script_model.set_available(
  self._script_registry.available())` lúc khởi tạo (như Dashboard làm).
  Thêm lại `IndicatorScriptRunner` (đã gỡ ở `BOT-060`) — nhưng lần này để
  vẽ **script user chọn**, feed qua `feed_all(raw_klines)` trong
  `_fetch_and_emit_chart_data` **cạnh** `_emit_strategy_indicator_lines()`
  đã có, không thay thế.
- [ ] Đọc `enabled_keys` **tại thời điểm bấm "Chạy Backtest"** — đúng quy
  ước "không hồi tố" TC-GAP-07 đã áp dụng cho Dev Board, không tự chế quy
  tắc khác.
- [ ] `BackTestTopPanel.qml` (hoặc 1 panel riêng cạnh chart controls): thêm
  section "CHỈ BÁO THAM KHẢO" tái dùng `Repeater { model:
  viewModel.scriptModel }` y hệt `DevBoardPanel.qml`.
- [ ] `_start_backtest_run`: clear cả 2 tập đường (strategy lines hiện có +
  script lines mới) trước khi chạy lại — không chỉ 1 tập như hiện tại.
- [ ] Test: bật 1 script (vd `rsi_14`) → chạy backtest → đường RSI xuất
  hiện trên chart cùng lúc với đường của strategy, không đụng tên nhau; tắt
  hết script → chỉ còn đường strategy; DI sanity cho `scriptModel`.

## 4. Rủi ro / Lưu ý

- **Không lặp lại sai lầm của `BOT-056`/`BOT-060`**: đây LÀ đúng chỗ dùng
  `IndicatorScriptRunner` (script user tự chọn, không liên quan gì tới
  strategy) — khác hẳn việc `BOT-056` từng dùng nó để giả lập "indicator
  của strategy" (sai, đã sửa ở `BOT-060`). Đọc kỹ `BOT-060`'s task file
  trước khi bắt đầu để không lẫn lại 2 khái niệm này.
- Không đụng `strategy_indicator_lines.py`/`_emit_strategy_indicator_lines`
  — 2 cơ chế chạy song song, độc lập.
- Subplot vs overlay: script không phải lúc nào cũng `overlay=True` (vd
  `rsi_14`/`macd_full` là subplot riêng, `min_warmup_bars` khác nhau) —
  `IndicatorScriptRunner.draw()` đã tự xử lý đúng, không cần code thêm.
- **Gap đã ghi rõ, không làm**: chuyển sang chế độ "Đường Vốn" (Equity-solo)
  hiện chỉ ẩn/disable đúng "Chỉ báo Chiến lược" (`BOT-060`'s
  `_on_ema_toggled`/`set_ema_enabled`) — script overlay tự chọn ở task này
  **chưa** được ẩn theo, nên 1 script `overlay=True` (vd EMA Ribbon) vẫn có
  thể kéo lệch auto-range của trục Equity giống lỗi `BOT-060` từng sửa cho
  strategy lines. Không thuộc scope task này (mockup gốc chưa yêu cầu),
  nhưng nếu làm sau: lặp lại đúng cách `_on_ema_toggled` đã làm, áp dụng
  cho `self._chart_script_runner.active[key].registered_lines`.

## 5. Phụ thuộc

- `BOT-032` ✅ — indicator script + `IndicatorScriptRunner`/
  `IndicatorScriptListModel` gốc (viết cho Dev Board).
- [`BOT-060`](BOT-060_backtest_chart_draws_strategy_own_indicators.md)
  — cơ chế vẽ indicator của strategy, phải giữ nguyên, chạy song song.
