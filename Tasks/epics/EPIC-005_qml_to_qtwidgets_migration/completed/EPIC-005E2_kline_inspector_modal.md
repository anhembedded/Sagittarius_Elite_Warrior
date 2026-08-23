# EPIC-005E2 — `KLineInspectorModal.qml` → QtWidgets

**Thuộc:** [`EPIC-005E`](../incomplete/EPIC-005E_data_management.md)
**Trạng thái:** ✅ Xong (2026-08-24)
**Phụ thuộc:** `EPIC-005E1` ✅

---

## Phạm vi

`KLineInspectorModal.qml` (415 dòng) — modal tra cứu nến thô: jump-to-date, nút Audit +
banner kết quả, bảng nến phân trang (7 cột: thời gian/open/high/low/close/volume/biến
động/số lệnh), thanh phân trang (page-size 50/100/200/500, điều hướng trang).

**0 kit component** phải port (khác `DatabaseScreen.qml`'s 3) — modal này chỉ dùng
`ModalDialogCard` (đã có pattern `ConfirmDialog`/`SymbolPickerDialog` từ `EPIC-005E1` để
tham chiếu phong cách, không tái sử dụng trực tiếp vì shape khác hẳn — dialog dữ liệu, không
phải confirm/picker).

## Quyết định thiết kế: `KLineInspectorTableModel` — vẫn dùng `QListView` + `setIndexWidget`

`KLineInspectorTableModel.columnCount()` trả về `11` (không phải `1` như
`DatabaseStatusTableModel`), nhưng `data(index, role)` **chỉ đọc theo `role`, bỏ qua hoàn
toàn `index.column()`** — model vẫn được thiết kế cho `ListView`'s named-role delegate (mỗi
`index.row()` là một nến, các "cột" trong `columnCount()` không tương ứng với cách `data()`
thực sự trả dữ liệu). Dùng `QTableView` chuẩn trực tiếp sẽ đọc sai (mỗi ô cột sẽ nhận
`DisplayRole`, không phải role riêng, nên `data()` trả `None`). Giữ đúng quyết định của
`EPIC-005E1`: `QListView` + `setIndexWidget()` mỗi hàng (`_KLineRowWidget`), đọc đủ 8 field
hiển thị qua `KLineInspectorTableModel`'s class constants.

Model tự gọi `beginResetModel()`/`endResetModel()` ở mọi thao tác
(`set_klines`/`set_page`/`set_page_size`/`jump_to_date`) — không chỉnh sửa. `QAbstractItemView`
tự dọn các `indexWidget` cũ khi nhận `modelReset` (hành vi built-in của Qt, xác nhận qua
`_rebuild_rows()` không leak/duplicate widget sau nhiều lần đổi trang trong test tay và test
tự động). `_rebuild_rows()` lắng nghe `modelReset` để build lại toàn bộ hàng.

## Dialog sống suốt vòng đời màn hình, không tạo lại mỗi lần mở

Giống `SymbolPickerDialog`, `KLineInspectorDialog` được tạo lười (lazy, ở lần mở đầu tiên)
rồi giữ nguyên — wiring signal (`klineInspectorChanged`/`auditResultChanged`/model's
`modelReset`) nằm trong `__init__`, không phải nối lại mỗi lần `.open()`. Mở qua
`view_model.openKlineInspectorRequested` (được `set_kline_inspector_data()` emit sau khi có
dữ liệu — đúng luồng gốc: bấm "KLines" trên 1 hàng status table → coordinator chạy nền → data
về → `viewModel.openKlineInspectorRequested.emit()` → QML cũ gọi `klineInspectorModal.open()`
qua `Connections{}`; bản QtWidgets nối trực tiếp `signal.connect(self._open_kline_inspector)`
trong `set_view_model()`).

## Test — dữ liệu hiển thị khớp nguồn, không chỉ "mở được"

`EPIC-005E`'s risk note yêu cầu rõ: đây là màn hình đụng dữ liệu giao dịch thật, cần ít nhất
1 test khẳng định dữ liệu hiển thị khớp nguồn. `tests/unit/presentation/ui/screens/
test_kline_inspector_widget.py` (mới, 3 test):

- `test_inspect_klines_opens_dialog_and_first_row_matches_source_data` — set dữ liệu qua
  đúng API `view_model.set_kline_inspector_data()` (không set thẳng vào widget), rồi so sánh
  từng field hiển thị (`_time_label`/`_open_label`/`_close_label`/`_trades_label`) với giá trị
  đọc trực tiếp từ model qua role — chứng minh không có sai lệch giữa nguồn và hiển thị.
- `test_pagination_changes_table_contents_to_match_the_requested_page` — đổi page size,
  nhảy trang 2, xác nhận hàng đầu tiên hiển thị đúng nến thứ 51 (không phải nến thứ 1).
- `test_audit_result_updates_banner_text_and_color` — audit running → nút disable + đổi text;
  audit xong → banner hiện đúng message.

Không sửa test nào có sẵn (khác `EPIC-005E1`, vốn phải sửa 3 file) — modal này chưa có test
nào tham chiếu QML trước đó (`test_gap_inspector_presenter.py`'s skip vẫn giữ nguyên, chờ
`E3`).

## Guard `EPIC-005B` — sạch, không phát hiện trùng lặp

`Palette.SUCCESS`/`Palette.DANGER` dùng cho màu nến tăng/giảm và audit banner (khớp đúng hex
QML gốc: `#0ecb81`/`#f6465d`). Hai màu nền banner `#0d2818`/`#381214` (audit pass/fail) không
trùng token `Palette` nào có sẵn — giữ nguyên, không đổi thành token giả.

## Giới hạn khi so sánh thị giác

Không chụp được ảnh QML gốc để so sánh trực tiếp: root của `KLineInspectorModal.qml` là
`ModalDialogCard` (dẫn xuất `Popup`), và `QQuickWidget` **chỉ chấp nhận root item kế thừa
`Item`** — giới hạn kiến trúc Qt, không phải lỗi của lần render này (`QQuickWidget: invalid
root object`). Đã gửi ảnh chụp bản QtWidgets (`KLineInspectorDialog`, dữ liệu mẫu BTCUSDT) cho
user xem trực tiếp thay vì so sánh cạnh nhau.

## Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`, verify qua log file
(`grep FAILED|ERROR|Traceback|ResourceWarning` — sạch). Baseline `1792 passed, 1 skipped / 54
sanity` → `1795 passed, 1 skipped / 54 sanity` (+3 test mới, accounted for đầy đủ, không có
gì bị xoá hay sửa ngoài dự kiến).
