# BUG-070 — SymbolPicker QML cảnh báo "Could not attach Keys property to: Popup ... is not an Item"

**Reported date:** 2026-08-30  
**Severity:** ⚪ **P4**  
**Status:** 🔴 Open — chỉ ghi nhận hiện tượng và log bằng chứng theo yêu cầu.

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

## 3. Suggested next steps

Di chuyển `Keys.onPressed` vào thẻ `contentItem: ColumnLayout` (vốn là một `Item`) bên trong Popup để phím điều hướng Up/Down/Enter hoạt động chuẩn mà không sinh warning.
