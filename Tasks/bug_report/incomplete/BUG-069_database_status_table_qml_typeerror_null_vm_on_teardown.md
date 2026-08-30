# BUG-069 — DatabaseStatusTable QML quăng hàng loạt TypeError khi ViewModel bị huỷ lúc thoát app

**Reported date:** 2026-08-30  
**Severity:** 🟡 **P3**  
**Status:** 🔴 Open — chỉ ghi nhận hiện tượng và log bằng chứng theo yêu cầu.

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

## 2. Ghi nhận sơ bộ (Initial Observation)

- Trong quá trình teardown (đóng app), ViewModel phía Python (`DatabaseStatusViewModel`) bị thu hồi bộ nhớ hoặc gán về `None`/`null` trước khi QML engine giải phóng hoàn toàn các visual element.
- Trong `DatabaseStatusTable.qml` và `DatabaseStatusRow.qml`, các biểu thức binding đọc trực tiếp `vm.rowCount`, `vm.rowsModel`, `vm.actionsEnabled` mà không có null-safe guard (`vm ? vm.rowCount : 0` hoặc `vm?.rowCount`). Khi `vm` biến thành `null`, Qt Quick binding tự động tính lại và ném ra các ngoại lệ này.

## 3. Suggested next steps

1. Thêm toán tử null-safe guard (`vm ? vm.xxx : ...`) cho tất cả các điểm truy cập `vm` trong `DatabaseStatusTable.qml` và `DatabaseStatusRow.qml`.
2. Đảm bảo quy trình teardown của QML host ngắt binding hoặc unmount trước khi giải phóng ViewModel Python.
