# BUG-070 — SymbolPicker QML cảnh báo "Could not attach Keys property to: Popup ... is not an Item"

**Reported date:** 2026-08-30  
**Severity:** ⚪ **P4**  
**Status:** ✅ Fixed 2026-08-31 (root-caused / reproduced / regression-tested / verified)

---

## 1. Hiện tượng (Symptom)

Mỗi lần mở hộp thoại Symbol Picker (trên Backtest hoặc Dev Board), console hiển thị thông báo cảnh báo từ Qt Quick:

```text
Could not attach Keys property to:  Popup_QMLTYPE_14(0x20ac27b9f70, name = "symbolPicker")  is not an Item
```

## 2. Ghi nhận sơ bộ (Initial Observation)

- Trong `src/presentation/ui/qml/SymbolPicker/SymbolPicker.qml` dòng 126:
  ```qml
  Popup {
      id: pickerPopup
      objectName: "symbolPicker"
      ...
      Keys.onPressed: function(event) {
          if (root.handleNavigation(event.key)) event.accepted = true
      }
  ```
- Thuộc tính đính kèm `Keys` trong Qt Quick chỉ hợp lệ trên các đối tượng kế thừa từ `QQuickItem` (như `Item`, `Rectangle`, `FocusScope`).
- `Popup` trong `QtQuick.Controls` kế thừa từ `QQuickPopup` (dẫn xuất từ `QObject`, không phải `Item`), do đó Qt không thể đính kèm `Keys` vào Popup và in cảnh báo ra console.

## 3. Cách khắc phục (Fix) — 2026-08-31

Di chuyển `Keys.onPressed` từ `pickerPopup` (một `Popup`, không phải `Item`) sang
`contentItem: ColumnLayout` (một `Item` thật) trong
[`SymbolPicker.qml`](../../../src/presentation/ui/qml/SymbolPicker/SymbolPicker.qml) — đúng
hướng "Suggested next steps" ban đầu. Không đổi hành vi: `searchField` (một `TextField` bên
trong `contentItem`) đã có sẵn `Keys.onPressed` giống hệt và luôn giữ `activeFocus` thật (do
`onOpened: searchField.forceActiveFocus()`), nên nó vẫn bắt phím Up/Down/Enter trước; handler ở
`contentItem` chỉ là lưới an toàn dự phòng cho trường hợp focus rơi vào chỗ khác trong popup —
y hệt vai trò cũ của handler trên `pickerPopup`, chỉ khác chỗ đặt.

## 4. Kiểm thử xác minh (Verification)

Thêm `test_opening_the_popup_does_not_warn_that_keys_cannot_attach_to_it` vào
[`test_symbol_picker_qml.py`](../../../src/presentation/ui/qml/SymbolPicker/tests/test_symbol_picker_qml.py)
— dùng `qInstallMessageHandler` bắt mọi message Qt lúc mở popup thật (`root.openPicker()`), assert
không có `"Could not attach Keys property"`.

Chạy thật trên Linux (PySide6 6.11.1 + `sagittarius_engine`, offscreen):
- **Trước sửa** (`git stash` chỉ file `.qml`): **1 failed** — đúng lý do, bắt được đúng dòng
  `Could not attach Keys property to: Popup_QMLTYPE_21(...) is not an Item`.
- **Sau sửa**: cả file `test_symbol_picker_qml.py` — **7 passed**. Chạy rộng hơn (Dev Board panel
  dùng chung SymbolPicker + symbol picker modal host): **51 passed**.
- `ruff check`/`ruff format --check`: sạch.
