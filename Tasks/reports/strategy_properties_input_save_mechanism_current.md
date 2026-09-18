# Cơ chế lưu input hiện tại — Strategy Properties dialog

Tài liệu này mô tả **nguyên trạng** của dialog **Cài đặt Chiến lược** sau
`BUG-064` (`fc3fcc4`). Nó không đề xuất sửa; mục đích là cung cấp bản đồ trước
khi thiết kế lại.

## Phạm vi

Dialog `StrategyPropertiesDialog` có hai vùng dữ liệu:

| Vùng | Nguồn field | Ví dụ |
| :--- | :--- | :--- |
| **Các đầu vào** | Schema của strategy, dựng động | EMA period, trailing stop |
| **Đặc tính** | 12 broker properties, dựng tĩnh | vốn, order size, commission, leverage, take profit |

File điều phối UI là
[`strategy_properties_dialog.py`](../../src/presentation/ui/screens/backtest/backtest_modals/strategy_properties_dialog.py).

## Hai trigger hiện tại — nhưng cùng một hành động

Hiện tại **nút `Lưu & Chạy lại`**, **Enter**, và **mất focus của bất kỳ
`QLineEdit` nào** đều đi tới cùng `save_and_rerun()`.

```text
QLineEdit.editingFinished
   ├─ nhấn Enter
   └─ chuyển focus/click sang control khác
            │
            ▼
StrategyPropertiesDialog.save_and_rerun()
            │
            ▼
BackTestViewModel.requestStrategyPropertiesSave(payload)
            │ strategyPropertiesSaveRequested
            ▼
BackTestPresenter._on_strategy_properties_save_requested()
            │
            ▼
StrategyConfigCoordinator.apply_strategy_properties(payload)
   ├─ validate strategy inputs
   ├─ ghi broker properties vào ViewModel
   └─ _finish_save()
       ├─ refresh bot-parameter schema/rows
       ├─ emit botParamsSaved
       └─ mark config changed
            │
            ├─ StrategyPropertiesDialog.accept() → dialog đóng
            └─ Presenter._start_run_after_config_save() → Backtest chạy lại
```

Nút **Lưu & Chạy lại** cũng gọi chính `save_and_rerun()`, do đó hiện không có
khác biệt ngữ nghĩa giữa “commit field” và “finalize + đóng + chạy lại”.

## Wiring cụ thể

| Điểm | Cơ chế hiện tại | Hệ quả |
| :--- | :--- | :--- |
| Static Properties tab | `_wire_line_edits_to_save_on_focus_lost(self._properties_tab)` một lần khi tạo dialog | Mọi `QLineEdit` static phát `editingFinished` sẽ save toàn bộ form |
| Dynamic Inputs tab | Cùng wiring sau mỗi `_sync_inputs()` rebuild | Field strategy mới tự được nối nhưng save toàn form |
| Dialog close | `view_model.botParamsSaved.connect(self.accept)` | Mọi save thành công đóng dialog |
| Start run | Presenter xử lý `strategyPropertiesSaveRequested` rồi gọi `_start_run_after_config_save()` | Mọi save thành công cố gắng chạy Backtest |
| Invalid input | Coordinator trả `False`, set `botParamsError` | Không emit `botParamsSaved`, nên dialog không đóng/rerun |

## Payload và nguồn dữ liệu

`save_and_rerun()` luôn đọc **tất cả fields**, không chỉ textbox vừa mất focus:

```python
{
  "inputs": {
    "<strategy-input-name>": "<raw widget value>",
  },
  "properties": {
    "initial_capital": "...",
    "currency": "...",
    "order_size_type": "...",
    "order_size_text": "...",
    "pyramiding": "...",
    "commission_type": "...",
    "commission_text": "...",
    "slippage_ticks": "...",
    "long_leverage": "...",
    "short_leverage": "...",
    "take_profit_enabled": "...",
    "take_profit_pct_text": "...",
  }
}
```

`BROKER_PROPERTY_FIELDS` trong
[`broker_properties_schema.py`](../../src/presentation/ui/screens/backtest/logic/broker_properties_schema.py)
là source of truth cho `payload key → ViewModel property → coercion`.
Dialog vẫn có bảng `_property_bindings` riêng cho `payload key → widget
read/write`.

## Các side effect cần biết

1. Mất focus từ field A sang field B làm toàn bộ form validate/lưu, đóng dialog
   rồi bắt đầu Backtest. Field B không nhận được cơ hội chỉnh sửa trong dialog đó.
2. Bấm **Hủy** sau khi một field đã mất focus không còn là discard thuần túy,
   bởi save đã xảy ra trước khi click Hủy được xử lý.
3. Save thành công refresh schema; với field dynamic, widget được rebuild. Cờ
   `_saving` chỉ ngăn `editingFinished` deferred gây save lặp.
4. Nếu FSM không cho `RUN_REQUESTED`, giá trị vẫn đã được lưu và dialog vẫn đã
   đóng; chỉ Backtest không khởi chạy.
5. Chỉ `QLineEdit` auto-save. `QSpinBox`, `QComboBox`, và `QCheckBox` không
   tự nối commit; nhưng chúng được đọc vào payload nếu một `QLineEdit` khác
   phát `editingFinished` hoặc người dùng bấm nút Save.

## Ranh giới lớp hiện tại

```text
Dialog/View                 ViewModel             Presenter              Coordinator
-----------                 ---------             ---------              -----------
đọc widget ──payload──► request signal ─────► UI action ─────► validate/apply
botParamsSaved ◄──────────────────────────────────────────────── _finish_save
accept() + close
```

Dialog không tự ghi trực tiếp vào ViewModel hay screen state. Presenter giữ FSM
và quyền khởi chạy Backtest. Coordinator giữ validation, parse strategy inputs,
ép kiểu broker properties, refresh schema, và dirty-state notification.

## Các quyết định cần chốt khi thiết kế lại

- Enter có nghĩa là **commit field**, **save form**, hay **save + run**?
- Focus loss có được commit không? Nếu có, nó phải giữ dialog mở hay không?
- Nút Hủy có phải thực sự rollback mọi edit chưa finalise không?
- Có cần autosave từng field cho `QSpinBox`, `QComboBox`, `QCheckBox` để hành vi
  nhất quán với textbox không?
- Refresh schema lúc nào là an toàn để không phá focus/widget dynamic?
- Có cần tách rõ ba command: `CommitDraft`, `Save`, `SaveAndRun`?
- Lỗi validation nên hiển thị ở field nào và draft hợp lệ một phần có được giữ
  lại không?

## Test hiện có

[`test_strategy_properties_modal.py`](../../tests/unit/presentation/ui/screens/test_strategy_properties_modal.py)
đã kiểm tra save bằng nút, Enter, và focus loss commit. Tuy nhiên test focus
loss hiện chỉ assert ViewModel được cập nhật; nó không coi dialog đóng là lỗi.
Đây là test nên thay đổi đầu tiên khi chốt thiết kế mới.
