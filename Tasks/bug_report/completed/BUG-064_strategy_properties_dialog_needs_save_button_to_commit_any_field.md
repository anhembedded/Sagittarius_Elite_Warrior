# BUG-064 — Dialog "Cài đặt Chiến lược" chỉ commit giá trị khi bấm nút Lưu, không phản hồi Enter/mất focus

| Trường | Giá trị |
| :--- | :--- |
| **Trạng thái** | ✅ **Đóng 2026-08-27 — root cause tìm ra và đo được, tái hiện bằng test thật** |
| **Mức độ** | 🟡 P2 — không mất dữ liệu vĩnh viễn (giá trị chỉ chưa từng được lưu), nhưng gây hiểu nhầm "chỉnh sửa bị revert" |
| **Phát hiện** | 2026-08-27, user báo trực tiếp: "thay đổi kích thước lệnh thành 10, nhấn Enter, nơi vẫn hiện số 100" |

## Symptom

User mô tả và gửi ảnh chụp dialog "Cài đặt Chiến lược" (`StrategyPropertiesDialog`,
BOT-104), tab "Đặc tính": gõ giá trị mới vào ô "Giá trị kích thước"
(`propOrderSizeValue`), nhấn Enter — ô vẫn hiện lại giá trị cũ (`100`) khi mở lại
dialog. Ban đầu bị nhầm với 2 giả thuyết khác (tham số chiến lược không ảnh hưởng
kết quả backtest; dialog hiện sai tên chiến lược) — cả hai đều **bị loại bằng test
thật** trước khi tìm đúng root cause:

- Test tái hiện chính xác round-trip `VolumeSpikeFlowStrategy` (đổi
  `trailing_stop_pct`/`fade_mode`, bấm Lưu, dựng lại strategy) → **pass ngay**, chứng
  minh cơ chế lưu tham số chiến lược hoạt động đúng.
- Test tái hiện chính xác thao tác Enter trên `propOrderSizeValue` → **pass ngay ở
  lần chạy đầu (trước khi sửa)**, tức là bug **có thật**, không phải cảm giác.

## Root cause

`src/presentation/ui/screens/backtest/backtest_modals/strategy_properties_dialog.py`
— mọi `QLineEdit` trong cả 2 tab ("Các đầu vào" lẫn "Đặc tính") được tạo ra **không
kèm bất kỳ kết nối signal nào** (`returnPressed`/`editingFinished`). Cơ chế lưu duy
nhất là `save_and_rerun()`, chỉ được gọi khi bấm nút "Lưu & Chạy lại". Gõ giá trị
mới rồi nhấn Enter không kích hoạt gì cả — giá trị chỉ tồn tại trên mặt widget, chưa
từng được ghi vào `BackTestViewModel`. Lần mở dialog kế tiếp, `_sync_properties()`
đọc lại đúng giá trị cũ từ ViewModel (chưa đổi) → trông như bị "revert".

**Phát hiện thứ hai trong lúc sửa (user chỉ ra, không phải tôi tự thấy):** phần
`save_and_rerun()`/`_sync_properties()` đọc/ghi 12 widget bằng tay
(`self._prop_order_size_value.text()`, `.currentData()`, `.value()`,
`.isChecked()`...) — đúng loại "hot fix nhân bản" mà `bug-fix-rule.md`/§12.5 cấm.
Cùng một tập "12 broker property" bị khai 2 lần độc lập: 1 lần ở
`StrategyConfigCoordinator._BROKER_PROPERTIES` (áp giá trị vào ViewModel), 1 lần rải
rác trong `StrategyPropertiesDialog` (đọc/ghi widget) — thêm 1 property mới mà quên
1 trong 3 chỗ là bug y hệt BUG-064 lặp lại.

## Fix

1. **`_wire_line_edits_to_save_on_focus_lost()`** (dialog) — một vòng lặp chung
   dùng `findChildren(QLineEdit)`, nối `editingFinished` (bắt cả Enter **và** mất
   focus, đúng yêu cầu "lost focus thì update") tới `save_and_rerun()`. Áp dụng
   1 lần cho tab Đặc tính (widget tĩnh, xây 1 lần ở `__init__`) và mỗi lần
   `_sync_inputs()` rebuild tab Các đầu vào (widget động theo từng chiến lược) — field
   mới thêm vào sau này tự động được nối, không cần sửa thêm dòng nào.
2. **Guard chống gọi lặp** (`self._saving`) — rebuild tab Đầu vào sau khi lưu có thể
   khiến 1 widget đang giữ focus bắn thêm `editingFinished` trong lúc bị huỷ
   (deferred `deleteLater()`), gọi lại `save_and_rerun()` lần 2 nếu không chặn.
3. **`src/presentation/ui/screens/backtest/logic/broker_properties_schema.py`
   (file mới)** — `BROKER_PROPERTY_FIELDS`: bảng khai báo DUY NHẤT "khoá payload ↔
   thuộc tính ViewModel ↔ hàm ép kiểu", dùng chung bởi cả Coordinator lẫn Dialog.
   `StrategyConfigCoordinator._BROKER_PROPERTIES` (khai trùng) đã xoá, đọc thẳng từ
   schema chung.
4. **`_build_property_bindings()`** (dialog) — bảng "khoá ↔ widget ↔ đọc/ghi", dùng
   5 hàm dựng theo loại widget (`_line_edit_binding`, `_spin_box_binding`,
   `_check_box_binding`, `_combo_box_data_binding`, `_combo_box_text_binding`).
   `save_and_rerun()` và `_sync_properties()` giờ chỉ lặp qua bảng này — không còn
   `.text()`/`.currentData()`/`.value()`/`.isChecked()` viết tay cho từng field.
   Thêm 1 broker property mới từ giờ chỉ cần **1 dòng** ở `BROKER_PROPERTY_FIELDS` +
   **1 dòng** ở `_build_property_bindings()` (thay vì sửa 3 nơi độc lập như trước).
   Tác dụng phụ tích cực: xoá luôn bảng index combo hard-code riêng
   (`{"fixed_cash": 1, "fixed_contracts": 2}`) từng phải khớp tay với thứ tự
   `addItem()` — `_combo_box_data_binding` dùng `findData()`, không giả định thứ tự.

**Phạm vi cố ý không đụng:** tham số chiến lược ("Các đầu vào" tab) không cần sửa gì
— cơ chế `ScriptInput`/`input_*()` đã tự động hoàn toàn từ trước (chứng minh bằng
test `VolumeSpikeFlowStrategy`). Dev Board và Data Management **không dính bug
này** — cả hai đã dùng `textEdited` (commit theo từng ký tự gõ), một cơ chế khác,
đúng đắn theo cách khác: hành động đi kèm ở 2 màn đó rẻ (chỉ cập nhật UI/filter),
trong khi ở dialog Backtest mỗi lần commit gắn với **chạy lại cả backtest** — dùng
`textEdited` ở đây sẽ kích backtest chạy lại theo từng ký tự gõ, sai hoàn toàn.

## Regression test

`tests/unit/presentation/ui/screens/test_strategy_properties_modal.py` — 6 test mới:

- `test_editing_a_strategy_input_field_and_saving_uses_the_typed_value` — chứng
  minh cơ chế lưu tham số chiến lược (đường có sẵn) hoạt động đúng, loại trừ giả
  thuyết sai đầu tiên.
- `test_editing_volume_spike_flow_strategy_trailing_stop_and_saving_uses_the_typed_value`
  — round-trip đầy đủ với `VolumeSpikeFlowStrategy` (field có `group`, mix
  int/float/bool), loại trừ khả năng lỗi riêng ở chiến lược mới.
- `test_pressing_enter_in_order_size_field_commits_the_typed_value` — tái hiện
  đúng kịch bản user báo; **pass ngay ở lần chạy đầu (trước fix)** với assertion mô
  tả đúng bug (`orderSizeText == "100"` sau Enter), sau đó đảo lại thành assertion
  đúng hành vi mong muốn (`== "10"`) sau khi sửa code — verify cả 2 chiều.
- `test_tabbing_away_from_a_field_without_pressing_enter_also_commits_it` — mất
  focus mà không có Enter cũng phải commit.
- `test_editing_a_strategy_input_field_and_losing_focus_also_commits_it` — cùng cơ
  chế áp dụng cho tab Đầu vào, không chỉ tab Đặc tính.

Cập nhật `modal_presenter` fixture: đăng ký thêm `VolumeSpikeFlowStrategy` vào
`StrategyRegistry` test double.

**Verify đầy đủ trên máy thật** (venv `uv` Python 3.12.3, Engine repo clone riêng):
- `ruff check`/`format --check` `src tests`: sạch.
- `mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases
  src scripts`: sạch, 155 file.
- 16 test liên quan (modal + coordinator) pass, bao gồm
  `test_broker_properties_are_applied_with_their_declared_types` (test cũ, xác nhận
  schema chung mới không đổi hành vi coordinator).
- Full unit + sanity: **2355 passed**, 0 dòng `FAILED|ERROR|Traceback|ResourceWarning`
  trong log đầy đủ. 1 `RuntimeWarning` còn lại đã xác nhận có sẵn từ trước
  (`test_log_panel.py`, không liên quan).
