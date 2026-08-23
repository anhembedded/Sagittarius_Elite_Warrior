# EPIC-005E — Migrate `data_management` (mật độ form cao nhất)

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** 🟡 Đang làm (2/3 sub-task xong)
**Phụ thuộc:** [`EPIC-005D`](../completed/EPIC-005D_pilot_settings_screen.md) ✅ — user đồng ý
đi tiếp tại điểm quyết định của D

---

## 0. Vì sao là màn hình này, ngay sau pilot

3 file, **1.736 LOC** — trong đó `DatabaseScreen.qml` một mình đã **993 LOC**, file QML lớn
nhất repo. Đây là màn hình *đau nhất* và cũng là nơi QtWidgets *thắng rõ nhất*: toàn bảng,
form, dialog kiểm tra dữ liệu.

| File | LOC | Sub-task |
| :--- | ---: | :--- |
| `DatabaseScreen.qml` | 993 | `EPIC-005E1` ✅ |
| `KLineInspectorModal.qml` | 415 | `EPIC-005E2` (chưa làm) |
| `GapInspectorModal.qml` | 328 | `EPIC-005E3` (chưa làm) |

**Chia nhỏ thành 3 sub-task, làm tuần tự** (quyết định khi bắt đầu E, sau khi thấy quy mô
thật khác hẳn `EPIC-005D`'s Settings — có `QAbstractTableModel` thật, 3 kit component,
2 modal con). Mỗi sub-task tự chạy gate + báo cáo riêng, rollback từng phần được thay vì toàn
bộ.

## 1. Yêu cầu (áp dụng cho cả 3 sub-task)

1. Chuyển sang QtWidgets. **Điều chỉnh so với yêu cầu gốc**: dự kiến ban đầu dùng
   `QTableView` + `QAbstractTableModel`, nhưng `EPIC-005E1` phát hiện
   `DatabaseStatusTableModel` là **1 cột, nhiều role** (không phải N-cột thật) — model được
   thiết kế cho `ListView`'s named-role delegate pattern của QML, không phải cho `QTableView`
   chuẩn. Viết lại thành N-cột thật sẽ đổi model Python (ngoài phạm vi migration này). Dùng
   `QListView` + `setIndexWidget()` per row thay thế — tương đương trực tiếp với QML's
   `Repeater`/`delegate`, không đổi model.
2. Giữ nguyên hành vi. Không "nhân tiện" đổi layout hay thêm tính năng.
3. Vẫn **không xoá** file `.qml`.
4. Mỗi sub-task một commit riêng để revert lẻ được.
5. Ghi vào ADR của `EPIC-005A`: chi phí thực so với dự đoán từ pilot.

## 2. Rủi ro riêng của màn hình này

Đây là màn hình đụng **dữ liệu giao dịch thật** (shard, kline, gap). Một lỗi hiển thị ở đây
có thể dẫn tới quyết định sai về dữ liệu. Cần ít nhất một test khẳng định dữ liệu hiển thị
khớp nguồn — không chỉ "màn hình mở được".

## 3. Xác minh

Gate giữ đúng baseline tự chụp ngay trước khi bắt đầu mỗi sub-task. So bằng log file.

## 4. Sub-tasks

- **[EPIC-005E1](../completed/EPIC-005E1_database_screen_main.md)** — `DatabaseScreen.qml`
  (màn chính: sync controls, status table, log panel, symbol picker, 2 confirm dialog). ✅ Xong.
- **[EPIC-005E2](../completed/EPIC-005E2_kline_inspector_modal.md)** — `KLineInspectorModal.qml`
  (jump-to-date, audit, bảng nến phân trang). ✅ Xong — 0 kit component, cùng quyết định
  `QListView`+`setIndexWidget` như `E1` (model đọc theo role, không theo cột dù
  `columnCount()` trả 11).
- **EPIC-005E3** — `GapInspectorModal.qml`. Chưa làm.
