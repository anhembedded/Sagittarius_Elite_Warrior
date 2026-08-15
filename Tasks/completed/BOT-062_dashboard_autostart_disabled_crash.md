# Nhiệm vụ: Dev Board crash khi tick đầu tiên tới với auto-start đang tắt

> Bug lộ ra khi merge `master-warrior` (remote đã thêm cờ config `DEV_BOARD_AUTOSTART_ENABLED`, mặc định tắt, nhưng bỏ sót 1 chỗ dùng `self._autostart` không guard). Không thuộc Epic Backtest — Dev Board/Dashboard.

## 1. Mục tiêu (Objective)

Sau khi resolve merge conflict cho `BotParamsDialog.qml`/`BackTestTopPanel.qml`
(nhánh remote mang theo tính năng Currency + cờ config mới cho Dev Board),
chạy full test suite phát hiện `test_dashboard_presenter.py` fail hàng loạt
(63 error + 3 fail) — hoàn toàn không liên quan gì tới Backtest/Currency.
Điều tra lộ ra: `dashboard_presenter.py` giờ đọc cờ config mới
`DEV_BOARD_AUTOSTART_ENABLED` (mặc định `False` — Dev Board không tự động
kết nối live nữa trừ khi user bật) để quyết định có tạo
`self._autostart = AutoStartController(...)` hay không, **nhưng
`_on_ui_chart_update()` vẫn gọi `self._autostart.on_market_tick()` không
điều kiện** — nếu autostart tắt, `self._autostart` không tồn tại, nên
**bất kỳ tick live nào tới cũng crash `AttributeError`**. Với default mới
(tắt), đây là crash chắc chắn xảy ra ngay khi có dữ liệu WS đầu tiên.

## 2. Mô tả (Description)

`dashboard_presenter.py`, trong `__init__`:
```python
is_autostart_enabled = self.config.get(
    _AUTOSTART_ENABLED_CONFIG_KEY, _DEFAULT_AUTOSTART_ENABLED, cast=bool
)
if is_autostart_enabled:
    self._autostart = AutoStartController(...)
    self._autostart.begin()
```
`self._autostart` chỉ được gán khi `is_autostart_enabled` — nếu tắt,
attribute không tồn tại. `_on_ui_chart_update()` (chạy trên Main UI Thread
mỗi khi 1 tick live tới):
```python
self._autostart.on_market_tick()
```
gọi thẳng, không kiểm tra tồn tại.

66 test cũ của `test_dashboard_presenter.py` cũng fail theo — không phải vì
logic sai, mà vì fixture `presenter`/`mock_container` giả định hành vi CŨ
(auto-start luôn bật khi construct → FSM về `LOCKED`), viết từ trước khi
cờ config này tồn tại; giờ default đã đổi thành tắt, fixture "reset FSM
LOCKED→IDLE" (`p.fsm.transition_to(UIMode.ERROR)`) tự nó raise
`InvalidStateTransitionError` vì FSM đã ở `IDLE` sẵn rồi.

## 3. Các bước thực hiện (Action Items)

- [x] Test tái hiện trước (đúng [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md)):
  `test_a_market_tick_does_not_crash_when_autostart_is_disabled` — construct
  presenter với config mặc định (autostart tắt), gọi `_on_ui_chart_update()`,
  xác nhận không raise. **Fail đúng lý do** (`AttributeError`) trước khi sửa.
- [x] `dashboard_presenter.py`: khai `self._autostart: AutoStartController |
  None = None` **trước** nhánh `if is_autostart_enabled`, và guard
  `_on_ui_chart_update()`'s lời gọi bằng `if self._autostart is not None:`.
- [x] `test_dashboard_presenter.py`:
  - Tách `mock_config` thành fixture riêng (trước đây build tay bên trong
    `mock_container`) để test autostart-cụ thể override được config mà
    không phải viết lại toàn bộ `mock_container`.
  - Fixture `presenter` dùng chung: xoá dòng
    `p.fsm.transition_to(UIMode.ERROR)` (không còn cần thiết — FSM không
    còn tự chuyển `LOCKED` lúc construct với default mới), cập nhật
    docstring phản ánh đúng hành vi hiện tại.
  - 3 test dành riêng cho auto-start
    (`test_construction_auto_starts_immediately`,
    `test_starting_live_manually_while_autostart_pending_is_rejected`,
    `test_a_market_tick_cancels_the_autostart_fallback_timer`): thêm helper
    `_enable_autostart(mock_config)` bật tường minh
    `DEV_BOARD_AUTOSTART_ENABLED=True` trước khi construct — trước đây các
    test này ngầm dựa vào default cũ (luôn bật), giờ default đã đổi nên
    phải tự bật.
- [x] Dọn 2 lint pre-existing không liên quan (import order ở
  `dashboard_presenter.py`, `UIMode` import thừa/redefine ở file test) —
  tiện thể vì đang đụng cả 2 file này.
- [x] 768 test toàn repo pass (tests/unit + tests/sanity), coverage 93.31%,
  `ruff` sạch.

## 4. Rủi ro / Lưu ý (Constraints & Risks)

- Đây KHÔNG phải bug do session này gây ra — cờ `DEV_BOARD_AUTOSTART_ENABLED`
  đến từ nhánh `master-warrior` trên remote (merge vào cùng lúc với
  `BOT-047`/`BOT-060`/`BOT-061`), thuộc phạm vi Dev Board/Dashboard, không
  phải Epic Backtest. Chỉ sửa đúng phần bị crash + test liên quan trực
  tiếp, không đổi lại default `_DEFAULT_AUTOSTART_ENABLED = False` (quyết
  định sản phẩm của thay đổi đó, không phải của task này).
- Không đổi hành vi khi autostart **bật** — chỉ thêm nhánh an toàn cho
  trường hợp **tắt**, vốn giờ là default thật.
