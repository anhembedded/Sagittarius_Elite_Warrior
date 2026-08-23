# EPIC-005E — Migrate `data_management` (mật độ form cao nhất)

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** [`EPIC-005D`](EPIC-005D_pilot_settings_screen.md) **và** user đã đồng ý đi tiếp
tại điểm quyết định của D

---

## 0. Vì sao là màn hình này, ngay sau pilot

3 file, **1.736 LOC** — trong đó `DatabaseScreen.qml` một mình đã **993 LOC**, file QML lớn
nhất repo. Đây là màn hình *đau nhất* và cũng là nơi QtWidgets *thắng rõ nhất*: toàn bảng,
form, dialog kiểm tra dữ liệu.

| File | LOC |
| :--- | ---: |
| `DatabaseScreen.qml` | 993 |
| `KLineInspectorModal.qml` | 415 |
| `GapInspectorModal.qml` | 328 |

Đây cũng là nơi câu hỏi "`QTableView` có hơn `AppDataTable` không" được trả lời bằng code
thật thay vì tranh luận: shard/kline là dữ liệu bảng đúng nghĩa, cần sort, resize cột, cuộn
lượng lớn dòng.

## 1. Yêu cầu

1. Chuyển 3 màn hình/modal trên sang QtWidgets, dùng `QTableView` + `QAbstractTableModel` cho
   phần bảng (**không** `QTableWidget` — dữ liệu đến từ DB, model/view mới đúng và mới ảo hoá
   được lượng dòng lớn).
2. Giữ nguyên hành vi. Không "nhân tiện" đổi layout hay thêm tính năng — trộn vào là mất khả
   năng khẳng định không regression.
3. Vẫn **không xoá** file `.qml`.
4. Mỗi màn hình một commit riêng để revert lẻ được.
5. Ghi vào ADR của `EPIC-005A`: chi phí thực so với dự đoán từ pilot. Nếu lệch nhiều — đó là
   tín hiệu phải xem lại điều kiện dừng, không phải cắm đầu chạy tiếp.

## 2. Rủi ro riêng của màn hình này

Đây là màn hình đụng **dữ liệu giao dịch thật** (shard, kline, gap). Một lỗi hiển thị ở đây
có thể dẫn tới quyết định sai về dữ liệu. Cần ít nhất một test khẳng định dữ liệu hiển thị
khớp nguồn — không chỉ "màn hình mở được".

Lưu ý `data_management` mới vừa bị ảnh hưởng bởi EPIC-004 (persistence chuyển sang
`SqliteShardManager`). Chụp lại baseline ngay trước khi bắt đầu, đừng dùng lại con số cũ.

## 3. Xác minh

Gate giữ đúng baseline tự chụp ngay trước khi bắt đầu (`EPIC-005D` nhiều khả năng đã thêm
test — ghi rõ mốc mới là bao nhiêu và vì sao). So bằng log file.
