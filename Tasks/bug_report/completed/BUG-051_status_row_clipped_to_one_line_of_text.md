# BUG-051 — Mọi dòng của bảng Database Status bị cắt còn 14px, nút hành động render thành viền rỗng

**Trạng thái:** ✅ Đã sửa — 2026-08-26
**Phát hiện:** 2026-08-26, trong lúc làm [`EPIC-007F`](../../epics/EPIC-007_chuan_hoa_card_dung_chung/incomplete/EPIC-007F_migrate_4_man_hinh.md) — **không phải user báo**; lộ ra khi chụp ảnh trước/sau theo đúng yêu cầu "bằng chứng phải nộp" của task đó
**Nguồn gốc:** `EPIC-005E` — bản port `DatabaseScreen.qml` sang QtWidgets, tức là lỗi đã sống từ ngày màn này ra đời

---

## 1. Triệu chứng

Bảng **DATABASE STATUS** của màn Storage Vault: mỗi dòng cao đúng **14px**, trong khi nội dung
của nó cần **23px**. Nhãn 11px vẫn đọc được (vừa khít), nhưng 4 nút hành động
`KLines`/`Gaps`/`Sync`/`Clear` — `setFixedHeight(22)` — bị cắt cụt: **chỉ còn thấy viền bo, chữ
bên trong mất hẳn**.

Người dùng thấy 4 viên thuốc rỗng ở cột ACTIONS, không biết nút nào là nút nào.

Không ai báo vì bảng chỉ có dòng **sau khi** quét shard; mọi ảnh chụp màn này từ trước tới nay
đều chụp lúc `0 tables`, và bộ test thì assert vào widget/objectName chứ không đọc pixel.

## 2. Nguyên nhân gốc

`_refresh_status_rows()` gắn widget vào từng dòng bằng
`QListView.setIndexWidget(index, widget)`.

**`setIndexWidget()` không nói cho list biết widget của nó cao bao nhiêu.** Chiều cao ô vẫn do
delegate quyết định, và delegate mặc định (`QStyledItemDelegate`) trả về chiều cao của **một
dòng text** — 14px với font mặc định. Widget bị ép vào đúng 14px đó và nội dung tràn ra bị clip.

`DatabaseStatusTableModel` không trả `Qt.SizeHintRole` (nó là model thuần dữ liệu, đẻ ra cho
delegate QML đọc theo role tên), nên không có nguồn nào khác cấp chiều cao.

Đo trực tiếp, trước khi sửa:

```
widget.geometry()  -> QRect(0, 0, 1200, 14)
widget.sizeHint()  -> QSize(308, 23)
button.sizeHint()  -> QSize(54, 23)
```

## 3. Cách sửa

`_RowWidgetDelegate(QStyledItemDelegate)` trong `data_management_view.py`: `sizeHint()` đọc
`view.indexWidget(index).sizeHint().height()` và lấy giá trị lớn hơn.

**Đọc `sizeHint()` của chính widget thay vì ghi cứng một con số** — ghi cứng thì lần sau có ai
thêm control cao hơn vào dòng, dòng lại bị cắt và không có gì báo. Model **không** bị đụng tới:
chiều cao dòng là việc của view, và `_StatusRowWidget` đã ghi rõ model này nằm ngoài phạm vi
migrate.

## 4. Regression test

`test_status_rows_are_not_clipped_to_one_line_of_text` — dựng view + presenter, đẩy một dòng vào
`status_model`, rồi assert `visualRect(index).height() >= indexWidget(index).sizeHint().height()`.

Đã kiểm **đỏ trước, xanh sau**: gỡ dòng `setItemDelegate(...)` thì test báo `14 < 23`, đúng con
số của bug.

## 5. Vì sao lỗi này sống lâu vậy

Cùng một họ với `BUG-008`, `BUG-012` và chỗ `StatCard` thiếu cỡ chữ: **không ai nhìn thứ mình
ship**. Ở đây là hai lớp che nhau — bảng thường trống lúc chụp ảnh, và test thì hỏi "widget có
tồn tại không" chứ không hỏi "nó có nhìn thấy được không".

Bài học ghi lại: **một assert "widget tồn tại" không nói gì về việc widget có hiển thị được
không.** Test mới ở trên hỏi đúng câu hỏi thứ hai.
