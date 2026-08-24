# EPIC-005E3 — `GapInspectorModal.qml` → QtWidgets

**Thuộc:** [`EPIC-005E`](../README.md) — sub-task cuối, `EPIC-005E` đóng lại sau task này.
**Trạng thái:** ✅ Xong (2026-08-24)
**Phụ thuộc:** `EPIC-005E2` ✅

---

## Phạm vi

`GapInspectorModal.qml` (328 dòng) — modal chi tiết lỗ hổng dữ liệu: thanh timeline coverage
(các đoạn tô màu theo tỷ lệ), bảng danh sách gap (6 cột: #/START/END/DURATION/MISSING/ACTION),
nút vá từng gap + vá toàn bộ, footer tổng số nến thiếu.

**0 kit component** phải port, giống `E2`.

## Khác biệt lớn nhất so với `E1`/`E2`: không có `QAbstractItemModel` nào cả

`DatabaseStatusTableModel` (`E1`) và `KLineInspectorTableModel` (`E2`) đều là
`QAbstractTableModel` thật (dù đọc theo role). `gapList`/`coverageSegments` ở màn này chỉ là
**`Property("QVariantList", ...)`** — `list[dict]` Python thuần, không kế thừa
`QAbstractItemModel` nào. Vì vậy không dùng `QListView`/`setIndexWidget` — build lại đúng theo
kiểu QML `Repeater`: xoá sạch widget cũ, dựng lại toàn bộ hàng từ `list[dict]` mỗi khi
`gapListChanged`/`coverageSegmentsChanged` bắn. Danh sách gap luôn nhỏ (số lỗ hổng thực tế
của 1 symbol/interval), nên rebuild toàn bộ mỗi lần không phải vấn đề hiệu năng — khác hẳn
`E1`'s status table hay `E2`'s bảng nến hàng trăm/nghìn dòng, nơi *có* incremental
`QAbstractItemModel` để tận dụng.

Thanh coverage cũng dùng `QHBoxLayout` với stretch-factor tỷ lệ theo `ratio` mỗi segment thay
vì tính `width: parent.width * ratio` bằng tay — Qt layout tự phân bố theo stretch, tương
đương chính xác hành vi QML gốc mà không cần `resizeEvent` custom.

## uiMode gating: nối trực tiếp vào `view_model.uiModeChanged`, không qua `apply_ui_mode`

Khác các control ở màn chính (`DatabaseScreen`) vốn được `DataManagementView._sync_ui_mode()`
gate tập trung, các nút Repair trong modal này tự nối `view_model.uiModeChanged` ngay trong
`GapInspectorDialog.__init__` — modal sống độc lập, không phải một phần cây widget mà
`_sync_ui_mode()` duyệt qua. Test tay xác nhận: chuyển `SYNCING` → cả nút "Vá Toàn Bộ" lẫn nút
"Vá Gap" từng hàng disable đúng; quay lại `IDLE` → enable lại đúng.

## Test — dữ liệu hiển thị khớp nguồn + phục hồi test đã skip ở `E1`

`tests/unit/presentation/ui/screens/test_gap_inspector_widget.py` (mới, 4 test):

- `test_inspect_gaps_opens_dialog_and_rows_match_source_data` — subtitle/coverage%/tổng nến
  thiếu/objectName từng nút Repair (`btnRepairGap_0`, `btnRepairGap_1`) đúng theo dữ liệu gốc.
- `test_repair_gap_click_emits_the_source_gaps_fetch_window` — bấm nút hàng thứ 2, xác nhận
  `repairGapRequested` phát đúng `fetch_start_time`/`fetch_end_time` của **đúng gap đó** (không
  lẫn sang gap khác — khẳng định closure đúng biến trong vòng lặp dựng hàng).
- `test_repair_buttons_disabled_outside_idle_mode` — gate theo `uiMode`.
- `test_zero_gaps_shows_empty_state_and_disables_repair_all` — 0 gap → empty label hiện, nút
  Repair All tắt.

`tests/unit/presentation/ui/screens/test_gap_inspector_presenter.py`'s
`test_database_screen_loads_gap_inspector_modal_with_zero_qml_errors` — **skip từ `E1` đã được
gỡ**, viết lại thành `test_database_screen_constructs_both_inspector_modals_with_the_right_object_names`:
kiểm tra cả 2 dialog (`gapInspectorModal`/`klineInspectorModal`) chưa tồn tại trước khi có dữ
liệu (lazy construction), và tồn tại đúng `objectName` sau khi `set_gap_inspector_data`/
`set_kline_inspector_data` được gọi — tương đương trực tiếp bài kiểm tra QML gốc ("cả hai load
sạch, tìm được bằng objectName"), chỉ khác cơ chế truy cập (`view._gap_inspector`/
`view._kline_inspector` thay vì `root_obj.findChild`).

## Guard `EPIC-005B` — sạch

Không có màu literal trùng `Palette` nào mới. Màu alpha của coverage segment
(`Palette.DANGER`/`Palette.SUCCESS` + suffix hex `"e6"`/`"bf"`) là ghép chuỗi từ token, không
phải literal trùng lặp, guard không (và không nên) bắt trường hợp này.

## Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`, verify qua log file
(sạch, không `FAILED`/`ERROR`/`Traceback`/`ResourceWarning`). Baseline `1795 passed, 1 skipped
/ 54 sanity` → `1800 passed, 0 skipped / 54 sanity`: +4 test mới (`test_gap_inspector_widget.py`)
+1 test skip được gỡ và viết lại thành pass (`test_gap_inspector_presenter.py`) = +5 passed,
-1 skipped — khớp chính xác, không có gì lệch ngoài dự kiến.

## `EPIC-005E` đóng lại

Cả 3 sub-task (`E1`/`E2`/`E3`) đều xong. Xem [`EPIC-005E_data_management.md`](../EPIC-005E_data_management.md)
để tổng kết. Chi phí thực tế (theo mục 1.5 của `E`'s yêu cầu): 3 kit component ở `E1`, 0 ở
`E2`/`E3` — thấp hơn ước lượng ban đầu, khớp với kết luận đã ghi ở ADR `EPIC-005A`.
