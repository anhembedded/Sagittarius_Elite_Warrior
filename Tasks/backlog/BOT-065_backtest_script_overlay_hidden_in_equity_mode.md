# Nhiệm vụ: Ẩn overlay của Indicator Script khi Backtest chuyển sang "Đường Vốn" (Equity-solo)

> Gap tự phát hiện lúc làm [`BOT-064`](../completed/BOT-064_backtest_screen_indicator_script_picker.md)
> (danh sách chọn indicator script cho Backtest), user yêu cầu đánh giá và
> tách thành task riêng thay vì chỉ ghi chú.

## 1. Mục tiêu (Objective)

Khi user bật 1 indicator script kiểu overlay (vẽ chung trục giá với nến,
vd `ema_20`) qua "Chỉ báo" (`BOT-064`), rồi chuyển chart sang chế độ
**"Đường Vốn"** (Equity-solo — main plot đổi từ giá nến sang equity curve),
đường overlay đó **vẫn hiển thị, không tự ẩn** — kéo auto-range của trục
dùng chung về thang giá (hàng chục nghìn), làm đường Equity **bẹp dí/vô
hình**. Đây đúng loại bug `BOT-060` đã sửa cho "Chỉ báo Chiến lược" (đường
riêng của strategy), nhưng lần này tái diễn ở nhóm đường mới của `BOT-064`.

## 2. Mức độ nghiêm trọng — không phải edge case hiếm

4 trong số các script mặc định (`ema_20`, `ema_50`, `ema_100`, `ema_200`)
có `default_enabled = True` (kế thừa từ hành vi Dev Board) — nghĩa là **lần
đầu mở màn Backtest, cả 4 đường này đã tự bật sẵn**, tất cả đều
`overlay = True`. User chỉ cần bấm nút "Đường Vốn" 1 lần (không cần tự bật
gì thêm) là gặp bug này ngay. **Không phải trường hợp hiếm — gần như mặc
định.**

## 3. Cách sửa (đã phác thảo lúc đóng `BOT-064`)

`_on_chart_mode_changed` (`backtest_presenter.py`) hiện chỉ xử lý 2 việc khi
đổi `is_price_scale`:
```python
controls.set_trade_flags_enabled(is_price_scale)
controls.set_ema_enabled(is_price_scale)
self._on_ema_toggled(is_price_scale and controls.is_ema_checked())
```
`_on_ema_toggled` chỉ lặp `self._active_strategy_lines` (đường của
strategy, `BOT-060`) — **chưa đụng gì tới `self._chart_script_runner`**
(đường của script, `BOT-064`). Cần thêm 1 bước tương tự, lặp qua
`self._chart_script_runner.active` (dict `key -> ActiveScript`, có sẵn
`.registered_lines: set[str]` — tên đường trần, chưa qua
`qualified_line_name`) và gọi `card.set_indicator_visible(
qualified_line_name(key, line_name), visible)` cho từng đường, y hệt cách
`ema_ribbon` cũ từng bị ẩn/hiện trước khi `BOT-060` xoá cơ chế đó.

## 4. Các bước thực hiện (Action Items)

- [ ] Test tái hiện trước (đúng [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md)):
  bật 1 script overlay, chuyển "Đường Vốn", xác nhận đường script **vẫn
  hiện** (`card.set_indicator_visible` không được gọi cho đường đó) — bug
  thật, không phải giả định.
- [ ] `backtest_presenter.py`: thêm hàm `_set_script_lines_visible(visible:
  bool)` (mirror `_on_ema_toggled`), gọi từ `_on_chart_mode_changed` cạnh
  `self._on_ema_toggled(...)` đã có — **không** gộp chung 1 hàm với strategy
  lines (2 khái niệm khác nhau, `_on_ema_toggled` tên gắn với checkbox "Chỉ
  báo Chiến lược" cụ thể).
- [ ] Cân nhắc: script kiểu subplot (`overlay=False`, vd `rsi_14`) có cần ẩn
  theo không? Subplot không share trục giá với main plot nên **không** gây
  bug auto-range — có thể loại trừ khỏi vòng lặp (chỉ ẩn `active.overlay ==
  True`), tránh ẩn nhầm thứ không cần ẩn. Xác nhận lại bằng cách đọc
  `ChartCard.add_subplot_indicator` trước khi quyết.
- [ ] Test lại sau khi sửa: bật 1 script overlay + 1 script subplot, chuyển
  Equity — overlay ẩn, subplot vẫn hiện (nếu quyết theo hướng loại trừ ở
  trên); chuyển lại OHLC — overlay hiện lại đúng trạng thái checkbox.

## 5. Rủi ro / Lưu ý

- Không đụng `_on_ema_toggled`/`_active_strategy_lines` — cơ chế `BOT-060`
  giữ nguyên, chỉ thêm nhánh xử lý mới cho `BOT-064`.
- Không đụng `strategy_indicator_lines.py`.

## 6. Phụ thuộc

- [`BOT-060`](../completed/BOT-060_backtest_chart_draws_strategy_own_indicators.md)
  — mẫu đúng cách đã sửa bug tương tự cho strategy lines.
- [`BOT-064`](../completed/BOT-064_backtest_screen_indicator_script_picker.md)
  — nguồn phát sinh `self._chart_script_runner`.
