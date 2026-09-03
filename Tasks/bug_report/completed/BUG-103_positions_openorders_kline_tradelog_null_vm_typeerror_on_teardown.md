# BUG-103 — `PositionsTable`/`OpenOrdersTable`/`KlineInspectorTable`/`TradeLogTable` quăng `TypeError` khi ViewModel bị huỷ lúc thoát app — cùng lớp lỗi `BUG-069` chưa được lan rộng

**Reported date:** 2026-09-03
**Severity:** 🟡 **P3** — không crash tiến trình, không mất dữ liệu; chỉ đổ log lỗi lúc thoát app,
đúng lớp "vô hại nhưng gây nhiễu" `BUG-069` đã ghi.
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

Log thật do user gửi lúc thoát ứng dụng:

```text
2026-09-03 12:38:37,033 - App - INFO - App stopped.
file:///.../src/presentation/ui/qml/PositionsTable/PositionsTable.qml:38: TypeError: Cannot read property 'rows' of null
file:///.../src/presentation/ui/qml/PositionsTable/PositionsTable.qml:39: TypeError: Cannot read property 'rows' of null
file:///.../src/presentation/ui/qml/OpenOrdersTable/OpenOrdersTable.qml:35: TypeError: Cannot read property 'rows' of null
file:///.../src/presentation/ui/qml/OpenOrdersTable/OpenOrdersTable.qml:36: TypeError: Cannot read property 'rows' of null
```

Bốn dòng lỗi xuất hiện **sau** dòng `"App stopped."` — QML engine chưa giải phóng hoàn toàn dù
Python-side app đã báo dừng xong.

## 2. Nguyên nhân gốc rễ (Root cause)

Đúng cơ chế đã root-cause ở `BUG-069` (đóng 2026-08-30) cho `DatabaseStatusTable.qml`, nhưng
**chưa từng được áp dụng** cho 4 widget bảng khác dùng chung `DataTable.qml`:

- `PositionsPanel`/`OpenOrdersPanel` (`trading_widgets/*.py`) tạo `PositionsVM`/`OpenOrdersVM` với
  `parent=self` (chính Panel) rồi gán qua `root_context.setContextProperty("vm", self._vm)`. Lúc
  teardown, nếu QObject `vm` bị huỷ **trước** khi QML engine của `QQuickWidget` giải phóng xong,
  Qt Quick tự động gán mọi context property tham chiếu QObject đó thành `null` — mọi binding còn
  sống đọc `vm.rows` lập tức ném `TypeError`.
- `PositionsTable.qml:38-39` (`rowsModel: vm.rows`, `isEmpty: vm.rows.length === 0`) và
  `OpenOrdersTable.qml:35-36` (y hệt) đọc `vm.rows` trực tiếp, không có null-safe guard —
  khớp chính xác 4 dòng log user gửi.
- Điều tra mở rộng phát hiện **2 file khác cùng thư mục `qml/` cũng mắc y hệt lỗi**, chưa từng
  xuất hiện trong log của phiên này chỉ vì màn hình tương ứng không mở lúc thoát app:
  - `KlineInspectorTable.qml:39,61,62` — **có thể tái hiện trong production thật**, vì
    `KlineInspectorDialogWidget` (`data_management_widgets/kline_inspector_dialog.py`) là dialog
    thật, mở được từ màn Data Management.
  - `TradeLogTable.qml:34,57,78,79` — hiện **chưa nối vào bất kỳ màn hình sản xuất nào** (Backtest
    dùng bảng Trade Log kiểu QtWidgets riêng, `TradeLogTable.qml` chỉ được `preview.py`/test của
    chính nó load) — sửa cho nhất quán và phòng ngừa khi widget này được nối dây thật sau này.

## 3. Cách khắc phục (Fix)

Áp đúng pattern `BUG-069` đã dùng cho `DatabaseStatusTable.qml`/`DatabaseStatusRow.qml` — null-safe
guard tại mọi điểm đọc `vm.*`:

- `PositionsTable.qml`: `rowsModel: vm ? vm.rows : null`, `isEmpty: vm ? vm.rows.length === 0 : false`.
- `OpenOrdersTable.qml`: y hệt.
- `KlineInspectorTable.qml`: thêm 3 chỗ — dòng subtitle (`vm.symbol + ... + vm.rowCount`) bọc
  `vm ? (...) : ""`, cộng `rowsModel`/`isEmpty` như trên.
- `TradeLogTable.qml`: 4 chỗ — `model: vm ? vm.filterTabs : []`, `onClicked: if (vm)
  vm.chooseFilter(modelData.id)`, cộng `rowsModel`/`isEmpty` như trên.

## 4. Regression test

Test mới cho cả 4 file, cùng một khuôn: load QML với `vm` thật (có dữ liệu), gắn
`qInstallMessageHandler` bắt console QML, gọi `quick.rootContext().setContextProperty("vm", None)`
để mô phỏng đúng thời điểm teardown thật (Qt Quick tự null-hoá context property khi QObject bị
huỷ), rồi assert không có `TypeError` nào trong message bắt được:

- `src/presentation/ui/qml/PositionsTable/tests/test_positions_qml.py::
  test_the_vm_becoming_null_after_load_does_not_throw`
- `src/presentation/ui/qml/OpenOrdersTable/tests/test_open_orders_qml.py::
  test_the_vm_becoming_null_after_load_does_not_throw`
- `src/presentation/ui/qml/KlineInspectorTable/tests/test_kline_inspector_qml.py::
  test_the_vm_becoming_null_after_load_does_not_throw`
- `src/presentation/ui/qml/TradeLogTable/tests/test_trade_log_qml.py::
  test_the_vm_becoming_null_after_load_does_not_throw`

Xác nhận đỏ trước fix — mỗi test bắt được đúng nguyên văn `TypeError` khớp với dòng/file log user
gửi (`PositionsTable.qml:38`/`:39`, `OpenOrdersTable.qml:35`/`:36`), cộng 2 `TypeError` mới lộ ra ở
`KlineInspectorTable.qml` (`vm.symbol`) và `TradeLogTable.qml` (`vm.filterTabs`) không nằm trong
log gốc nhưng cùng cơ chế. Xanh sau fix, toàn bộ 4 bộ test liên quan (46 test) pass.
