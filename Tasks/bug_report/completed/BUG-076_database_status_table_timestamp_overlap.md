# BUG-076 — Cột FIRST RECORD/LAST RECORD chồng chéo chữ trên Database Status Table

**Reported date:** 2026-09-01
**Fixed date:** 2026-09-01
**Severity:** Trung bình — chỉ hỏng hiển thị (đọc không nổi ngày giờ), không mất
dữ liệu, không crash
**Status:** ✅ Fixed 2026-09-01 — root-caused, regression-tested
**Found by:** User báo trực tiếp kèm ảnh chụp màn hình thật của app đang chạy
("bug UI bị chồng chéo")

---

## Hiện tượng

Ảnh chụp màn hình thật (Database screen, bảng "DATABASE STATUS"): mỗi dòng ở
2 cột **FIRST RECORD** và **LAST RECORD** hiện ra như một chuỗi ký tự dính
chồng lên nhau hoàn toàn không đọc được, ví dụ trông giống
`2026-07-2213245-19846120063H700+00` thay vì 2 ngày giờ tách biệt rõ ràng.

User báo ban đầu là "bug UI bị chồng chéo" xảy ra ở **mọi màn hình**
("mang hinh nao cung co"). Ảnh chụp thứ 2 (màn Backtest) không cho thấy
chồng chéo nào — nên phạm vi thực tế của bug này chỉ xác nhận được ở màn
Database.

Ảnh chụp đầu tiên còn có 1 vùng nghi ngờ thứ 2 (progress bar "Đang đồng bộ
ETHUSDT 1m..." + "100%" + nút Hủy nhìn có vẻ chồng nhau) — **đã điều tra và
loại trừ**: viết regression test dùng đúng chiều rộng thật (292px,
`_PROGRESS_BANNER_HEIGHT`'s comment) và đúng nội dung thật (caption dài +
`_CANCEL_LABEL = "Hủy Tiến Trình (Cancel)"`), test **pass ngay cả khi chưa
sửa gì** — chứng minh giả thuyết "thiếu `Layout.minimumWidth: 0`" sai, nên
không sửa phần đó theo `bug-fix-rule.md` §1 (không đoán root cause). Nếu bug
này vẫn còn xảy ra ở progress bar, cần ảnh chụp riêng để điều tra tiếp.

## Root cause

`DatabaseStatusRow.qml` (`src/presentation/ui/qml/DatabaseStatusTable/`) có
6 cột trong 1 `RowLayout`: 4 cột đầu/cuối (`symbol`/`tf`/`status`/`actions`)
dùng `Layout.preferredWidth` cố định (qua các property
`symbolWidth`/`tfWidth`/`statusWidth`/`actionsWidth`), còn 2 cột giữa
(`firstRecord`/`lastRecord`) dùng `Layout.fillWidth: true` — chia đều phần
không gian còn lại, một cách bố trí tĩnh, xác định, không phụ thuộc nội
dung.

Vấn đề: `database_status_table_model.py::upsert_row()` lưu
`first_record=str(first_record)` — với một `datetime` có `tzinfo`, `str()`
ra chuỗi dạng `"2026-07-22 13:24:51.198461+00:00"` (32 ký tự). Cả 2 `Text`
hiển thị `firstRecord`/`lastRecord` **không có `elide` lẫn `clip`** — QML
`Text` mặc định vẽ tràn ra ngoài khung hình học của nó khi nội dung dài hơn
`width` đã cấp, thay vì bị cắt. Chuỗi 32 ký tự đó rộng hơn hẳn phần không
gian `fillWidth` được chia (~120-150px ở độ rộng cửa sổ thông thường), nên
`firstRecord` tràn thẳng đè lên `lastRecord` ngay bên phải nó — đúng hình
dạng "2 chuỗi ngày giờ chồng lên nhau" trong ảnh chụp.

Đây **không phải** lỗi bố cục động ("chạy theo resize") — 2 cột này đã dùng
công thức chia không gian tĩnh sẵn từ đầu; lỗi đơn thuần là nội dung không
được cắt (`elide`) theo đúng biên cột tĩnh đã cấp.

## Fix

`DatabaseStatusRow.qml` — thêm vào cả 2 `Text` (`firstRecord`/`lastRecord`):
- `elide: Text.ElideRight` — cắt chuỗi quá dài bằng "…" thay vì tràn ra
  ngoài.
- `Layout.minimumWidth: 0` — bắt buộc phải có cùng `elide`: minimum width
  mặc định của một `Layout.fillWidth` item lấy từ `implicitWidth` **chưa
  cắt** của nó, nên nếu không set về 0, `RowLayout` không bao giờ co được
  cột này xuống dưới độ rộng chuỗi đầy đủ — `elide` sẽ vô tác dụng dưới áp
  lực không gian hẹp.
- Thêm `objectName` cho cả 2 `Text` (`databaseStatusFirstRecord_<symbol>_
  <interval>`/`databaseStatusLastRecord_<symbol>_<interval>`) để test có
  thể định vị chúng — trước đó chỉ cột `symbol` có `objectName`.

## Regression test

`src/presentation/ui/qml/DatabaseStatusTable/tests/test_database_status_qml.py::test_a_full_iso_timestamp_does_not_overflow_into_the_next_column`
— dựng 1 hàng với `first_record`/`last_record` đúng định dạng `str(datetime)`
dài thật (kèm microseconds + tz offset, lấy đúng từ ảnh chụp), load ở độ
rộng mặc định của bộ test (900px, đã đủ hẹp để 2 cột fillWidth chỉ còn
~120px mỗi cột — tràn ngay cả ở độ rộng "bình thường" này), rồi assert:
1. `firstRecord.width < firstRecord.implicitWidth` — chứng minh layout thực
   sự co được cột xuống dưới độ rộng tự nhiên của chuỗi (đúng thứ
   `Layout.minimumWidth: 0` còn thiếu ngăn cản).
2. `firstRecord.x + firstRecord.width <= lastRecord.x` — chứng minh 2 cột
   không còn chiếm không gian ngang chồng lên nhau.

Xác nhận fail đúng lý do trước fix (`git stash` riêng file QML, chạy lại:
`AttributeError: 'NoneType' object has no attribute 'property'` — vì
`objectName` chưa tồn tại), pass sau khi thêm fix.

`pytest src/presentation/ui/qml/DatabaseStatusTable/tests/ -q` — 12/12 pass.
