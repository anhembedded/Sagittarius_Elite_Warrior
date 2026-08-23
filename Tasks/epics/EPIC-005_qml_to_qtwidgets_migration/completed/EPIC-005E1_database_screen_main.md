# EPIC-005E1 — `DatabaseScreen.qml` (màn chính) → QtWidgets

**Thuộc:** [`EPIC-005E`](../incomplete/EPIC-005E_data_management.md)
**Trạng thái:** ✅ Xong (2026-08-24)
**Phụ thuộc:** `EPIC-005D` ✅

---

## Phạm vi

`DatabaseScreen.qml` (993 dòng) — không bao gồm `KLineInspectorModal`/`GapInspectorModal`
(2 modal con, để lại `EPIC-005E2`/`E3`). Header (Vacuum/Purge), 2 stat tile, sync controls
card (symbol/interval combo, `TimeRangeCard`, 5 nút hành động, progress+cancel), status table
(search + bảng + 4 nút hành động/hàng), `LogPanel`, `SymbolPickerModal`, 2 confirm dialog
(Clear/Purge).

**3 kit component phải port** (khác Settings, vốn N=0): `TimeRangeCard`, `LogPanel`,
`FieldBackground`. Cộng `AppProgressBar` (từ `components/`, không phải kit engine) và
`SymbolPickerModal`/`ModalDialogCard` (pattern confirm dialog).

## Quyết định thiết kế chính: bảng dùng `QListView` + `setIndexWidget`, không phải `QTableView`

`DatabaseStatusTableModel` là **`QAbstractTableModel` 1 cột, nhiều role** — thiết kế riêng cho
`ListView`'s named-role delegate của QML (`columnCount()` luôn trả `1`, dữ liệu đọc qua
`SymbolRole`/`FirstRecordRole`/... không phải qua cột thật). Requirement gốc của
`EPIC-005E` dự kiến `QTableView` + `QAbstractTableModel` — không khả thi mà không đổi model
Python (ngoài phạm vi migration).

Chọn `QListView` + `setIndexWidget()` mỗi hàng — widget con (`_StatusRowWidget`) đọc đúng 7
role qua `DatabaseStatusTableModel`'s class constants, tương đương trực tiếp QML's
`Repeater`/`delegate: Rectangle {...}`. Model, filter proxy (`DatabaseStatusFilterProxy`,
`QSortFilterProxyModel` chuẩn) — **không đổi gì**, dùng thẳng.

## Phát hiện quan trọng nhất: `apply_ui_mode` bị thiếu, suýt lọt lưới

`BasePresenter._bind_fsm_to_ui`'s FSM callback gọi `view.apply_ui_mode(mode)` qua
`hasattr()` duck-type — **không raise nếu thiếu**, chỉ log warning âm thầm. `QmlHostView`
(class cha cũ) có override method này; `BaseView` (class cha mới) thì không. Thiếu nó nghĩa
là FSM transition thật (Vacuum/Sync/Scan chạy nền) **sẽ không bao giờ** cập nhật
`viewModel.uiMode` — mọi nút gate theo `uiMode === "IDLE"` sẽ đứng yên ở trạng thái lúc màn
hình mở, vĩnh viễn.

**Smoke test tay ban đầu không bắt được bug này** — tôi gọi trực tiếp `vm.set_ui_mode(...)`
thay vì đi qua FSM thật, nên wiring nhìn có vẻ đúng. Bug lộ ra khi chạy gate đầy đủ: 3 test có
sẵn (`test_database_progress_cancel_qml.py`, integration `test_database_user_flow.py`) dùng
FSM thật, và 1 trong số đó thất bại theo cách chỉ để lộ nếu đọc kỹ — phải port sang QtWidgets
mới thấy rõ khoảng trống. Đã thêm override `apply_ui_mode` (port nguyên văn từ
`QmlHostView`), cộng **1 test guard mới**
(`test_fsm_transition_alone_reaches_ui_mode_without_a_manual_set_ui_mode_call`) chặn tái
phát — cố tình KHÔNG gọi `set_ui_mode` thủ công song song với `fsm.transition_to`, chỉ dựa
vào cơ chế tự động.

## Test — 3 file phải viết lại, 1 test tạm hoãn

- `tests/unit/presentation/ui/screens/test_database_progress_cancel_qml.py` → đổi tên
  `test_database_progress_cancel_widget.py`, viết lại qua `view._btn_cancel_sync` thật thay
  vì `qml_item()`/`quick_widget.rootObject()`. Thêm test guard `apply_ui_mode` ở trên.
- `tests/integration/presentation/test_database_user_flow.py::test_database_cancel_button_cancels_active_sync_flow`
  — sửa tại chỗ, cùng lý do.
- `tests/unit/presentation/ui/screens/test_gap_inspector_presenter.py::test_database_screen_loads_gap_inspector_modal_with_zero_qml_errors`
  — **skip có lý do rõ**, không xoá. Test này kiểm tra `GapInspectorModal`/
  `KLineInspectorModal` load sạch bên trong `DatabaseScreen.qml`'s `quick_widget` — nhưng màn
  chính giờ không còn `quick_widget`. Không có gì tương đương để assert cho tới khi 2 modal đó
  tự migrate (`E2`/`E3`). Phục hồi/viết lại khi đó.
- `tests/unit/presentation/ui/screens/test_data_management_presenter.py` (662 dòng, business
  logic Presenter/Coordinator thuần) — **không đổi 1 dòng nào**, không tham chiếu QML.

`data_management_presenter.py`: `view.load_qml("DatabaseScreen.qml")` xoá (view tự dựng
QtWidgets trong `set_view_model`); thứ tự gọi `set_view_model` **không đổi** (khác Settings)
— `DataManagementViewModel`'s field đã có giá trị mặc định ngay từ `__init__`, không đợi load
config nào, nên gọi sớm hay muộn đều an toàn.

## Guard `EPIC-005B` bắt 2 bug thật trong lúc viết

`#1f2127` (copy trực tiếp từ QML cho hover state) trùng `Palette.STATE_HOVER_BG`; `#15171d`
(màu nền column header) trùng `Palette.BG_CARD_HEADER`. Cả hai sửa dùng token thay vì literal.

## So sánh thị giác

`preview.py` viết lại dùng `DataManagementView` thật thay vì `QQuickWidget`. Ảnh trước
(QML)/sau (QtWidgets) cùng dữ liệu mẫu đã gửi user — bố cục, bảng, log panel khớp.

## Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`, verify qua log file.
Baseline `1791 passed / 54 sanity` → `1792 passed, 1 skipped / 54 sanity` (+1 đổi tên file
test, +2 test mới, +1 skip có lý do — accounted for đầy đủ).
