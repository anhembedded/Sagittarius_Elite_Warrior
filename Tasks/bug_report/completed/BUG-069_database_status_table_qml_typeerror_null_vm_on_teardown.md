# BUG-069 — DatabaseStatusTable QML quăng hàng loạt TypeError khi ViewModel bị huỷ lúc thoát app

**Reported date:** 2026-08-30  
**Severity:** 🟡 **P3**  
**Status:** ✅ Fixed 2026-08-30 (root-caused / reproduced / verified)

---

## 1. Hiện tượng (Symptom)

Khi người dùng đóng ứng dụng hoặc chuyển/giải phóng màn hình Data Management, console xuất hiện hơn 20 dòng lỗi `TypeError` liên tục từ QML:

```text
file:///.../src/presentation/ui/qml/DatabaseStatusTable/DatabaseStatusTable.qml:134: TypeError: Cannot read property 'rowCount' of null
file:///.../src/presentation/ui/qml/DatabaseStatusTable/DatabaseStatusTable.qml:114: TypeError: Cannot read property 'rowsModel' of null
file:///.../src/presentation/ui/qml/DatabaseStatusTable/DatabaseStatusTable.qml:28: TypeError: Cannot read property 'rowCount' of null
file:///.../src/presentation/ui/qml/DatabaseStatusTable/DatabaseStatusRow.qml:130: TypeError: Cannot read property 'actionsEnabled' of null
file:///.../src/presentation/ui/qml/DatabaseStatusTable/DatabaseStatusRow.qml:123: TypeError: Cannot read property 'actionsEnabled' of null
file:///.../src/presentation/ui/qml/DatabaseStatusTable/DatabaseStatusRow.qml:116: TypeError: Cannot read property 'actionsEnabled' of null
file:///.../src/presentation/ui/qml/DatabaseStatusTable/DatabaseStatusRow.qml:108: TypeError: Cannot read property 'actionsEnabled' of null
(lặp lại cho từng hàng)
```

---

## 2. Nguyên nhân gốc rễ (Root Cause)

- Trong quá trình teardown (đóng app), `DatabaseStatusPanel` và ViewModel phía Python (`DatabaseStatusVM`) bị thu hồi bộ nhớ trước khi QML engine giải phóng hoàn toàn các visual elements.
- Trong `DatabaseStatusTable.qml` và `DatabaseStatusRow.qml`, các biểu thức binding đọc trực tiếp `vm.rowCount`, `vm.rowsModel`, `vm.actionsEnabled` mà không có null-safe guard (`vm ? vm.rowCount : 0`). Khi `vm` chuyển thành `null`, Qt Quick binding tự động tính lại và ném ra hơn 20 ngoại lệ `TypeError`.

---

## 3. Cách khắc phục (Fix)

1. Trong [`DatabaseStatusTable.qml`](file:///c:/Users/hoang/Documents/Gemini/Sagittarius-Elite-Warrior/src/presentation/ui/qml/DatabaseStatusTable/DatabaseStatusTable.qml):
   - Thay `vm.rowCount` bằng `(vm ? vm.rowCount : 0)`.
   - Thay `model: vm.rowsModel` bằng `model: vm ? vm.rowsModel : null`.
   - Thay `visible: vm.rowCount === 0` bằng `visible: vm ? vm.rowCount === 0 : false`.
   - Bổ sung `if (vm)` trước `vm.setSearchText(text)`.
2. Trong [`DatabaseStatusRow.qml`](file:///c:/Users/hoang/Documents/Gemini/Sagittarius-Elite-Warrior/src/presentation/ui/qml/DatabaseStatusTable/DatabaseStatusRow.qml):
   - Thay `enabled: vm.actionsEnabled` bằng `enabled: Boolean(vm && vm.actionsEnabled)`.
   - Bổ sung `if (vm)` trước `vm.requestAction(...)`.

---

## 4. Kiểm thử xác minh (Verification)

Bộ test `src/presentation/ui/qml/DatabaseStatusTable/tests/` gồm 22 tests vượt qua 100% không có bất kỳ ngoại lệ nào:
```text
22 passed in 0.42s
```
