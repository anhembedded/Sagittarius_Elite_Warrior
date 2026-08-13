# Nhiệm vụ: "Lưu & Re-Backtest" crash âm thầm — `QJSValue` không tự ép được sang `dict`

> Thuộc Epic [BOT-040 — Backtest Screen Full Feature Set](../backlog/BOT-040_backtest_screen_full_feature_epic.md), Nhóm A. Bug do user báo, phát hiện qua log console thật. Phụ thuộc `BOT-047` ✅.

## 1. Mục tiêu (Objective)

User dán 1 đoạn log console thật của app đang chạy, thấy 2 dòng cảnh báo QML
lạ (`BotParamField.qml:19`/`:59` — "Unable to assign [undefined] to
QString/QColor") và hỏi tôi có nhớ quy trình xử lý bug không (điều tra gốc
rễ, viết test tái hiện trước khi sửa — đúng như
[`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md) yêu cầu).

Điều tra ban đầu qua test tạm (dùng `findChildren(QObject, ...)` để dò cây
đối tượng bên trong `Popup`) khiến tôi **nghi ngờ sai** rằng field trong
modal "Thông số Bot" hoàn toàn không render được gì. Sau khi viết test thật,
dùng đúng helper `qml_item`/`find_qml_item` (đi theo **cây visual**
`childItems()`, không phải cây `QObject` — quy ước đã ghi sẵn trong
`tests/conftest.py`: *"QML items created by a Repeater are NOT QObject-
children of the QML root"*), field **thực ra render đúng, giá trị đúng**. 2
dòng cảnh báo console là nhiễu vô hại lúc parse QML lần đầu (cùng loại với
warning có sẵn từ trước ở `DatabaseScreen.qml` — không liên quan session
này, không sửa).

Nhưng viết test end-to-end thật (gõ giá trị → bấm "Lưu & Re-Backtest") lộ ra
**1 bug thật, nghiêm trọng hơn nhiều**: `requestBotParamsSave()` crash
(bắt bởi `@safe_ui_action` nên không sập app, nhưng **không lưu được gì** —
mọi giá trị user gõ trong modal bị âm thầm vứt bỏ).

## 2. Mô tả (Description)

`BackTestViewModel.requestBotParamsSave()` (`backtest_view_model.py`):

```python
@Slot("QVariant")
def requestBotParamsSave(self, values) -> None:
    self.botParamsSaveRequested.emit(dict(values))
```

QML gọi slot này với 1 JS object literal build trong `BotParamsDialog.
saveAndRerun()` (`values[items[i].fieldName] = items[i].currentValue`).
PySide6 marshal JS object literal vào slot khai `"QVariant"` thành
**`QJSValue`**, không phải `dict` — `dict(values)` raise `TypeError:
'PySide6.QtQml.QJSValue' object is not iterable`. Toàn bộ test cũ của
`BOT-047` **không bao giờ lộ bug này** vì đều gọi thẳng
`presenter._on_bot_params_save_requested(raw_values)` bằng 1 `dict` Python
build tay — bỏ qua hẳn ranh giới QML→Python thật.

## 3. Các bước thực hiện (Action Items)

- [x] `backtest_view_model.py`: `requestBotParamsSave()` kiểm tra
  `isinstance(values, QJSValue)`, gọi `.toVariant()` (đệ quy ép JS object →
  Python dict thật) trước khi `dict(values)`.
- [x] Test regression mới `tests/unit/presentation/ui/screens/
  test_bot_params_dialog_qml.py` — **đi qua QML thật**, không mock ranh giới
  này như test `BOT-047` cũ:
  - `test_opening_bot_params_dialog_renders_a_real_field_widget` — mở dialog
    thật (`btnBacktestBotParams.clicked.emit()`), tìm field bằng `qml_item`
    từ `quickWindow().contentItem()` (Popup content reparent sang
    `Overlay.overlay`, không phải con của `rootObject()`), xác nhận field có
    thật + đúng giá trị mặc định.
  - `test_editing_and_saving_bot_params_sends_the_typed_value` — gõ giá trị
    mới vào field thật, bấm nút Save thật, xác nhận `botParamsSaveRequested`
    nhận đúng `{"period": "42"}` — **test này FAIL trước khi sửa** (đúng quy
    trình: tái hiện bằng test trước, sửa tới khi pass).
- [x] `BotParamField.qml`: bỏ `required` khỏi `property var fieldData` — dư
  thừa (Presenter luôn truyền, không phải hợp đồng cần enforce), và loại bỏ
  1 trong 2 warning console user báo mà không đổi hành vi.
- [x] 754 test pass (752 + 2 mới), coverage 93.55%, `ruff` sạch.

## 4. Rủi ro / Lưu ý (Constraints & Risks)

- **Bài học chính, ghi lại vì có thể lặp**: bất kỳ Slot Python nào nhận 1
  JS object/array literal trực tiếp từ QML (không phải model property đã có
  sẵn) phải tự ép qua `QJSValue.toVariant()` — PySide6 **không** tự động ép
  `QVariant`-typed slot argument built từ JS object literal thành `dict`
  ngay cả khi khai `@Slot("QVariant")`. Đây là ranh giới QML→Python
  **duy nhất trong toàn bộ codebase tính tới giờ** truyền 1 dict động qua —
  không có convention nào có sẵn để theo, phải tự phát hiện qua test thật.
- **Bài học điều tra**: `tests/conftest.py` đã ghi rõ (dòng 58-63) Repeater
  items KHÔNG phải QObject-children của root — chỉ tìm được qua cây visual
  (`childItems()`, tức `qml_item`/`find_qml_item`), không phải qua
  `findChild`/`findChildren` (cây QObject thường). Dùng nhầm cây khi điều
  tra khiến tôi **kết luận sai** ban đầu rằng field không render được gì cả
  — bài học: luôn dùng đúng helper `qml_item` có sẵn, không tự chế cách dò
  khác khi debug QML.
- Không đụng `strategy_engine.py`/`i_strategy.py` — bug này thuần ở ranh
  giới QML↔ViewModel, không liên quan domain/application layer.
