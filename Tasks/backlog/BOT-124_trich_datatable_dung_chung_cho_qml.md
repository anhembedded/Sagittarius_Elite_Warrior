# BOT-124 — Trích `DataTable` dùng chung cho `ui/qml/`, gộp 3 bản sao đang có

- **Trạng thái:** 🔴 Chưa bắt đầu
- **Repo:** Elite
- **Chặn:** [`EPIC-021I`](../epics/EPIC-021_ket_noi_binance_futures_testnet/incomplete/EPIC-021I_man_giao_dich_moi.md) §3.2.2

---

## 1. Vấn đề thật

`src/presentation/ui/qml/` đang có **ba** bảng, mỗi cái là một bản dựng lại của cùng một khung:

| Widget | `.qml` bảng | Row delegate |
| :--- | ---: | ---: |
| `TradeLogTable` | 141 dòng | 245 dòng |
| `KlineInspectorTable` | 139 dòng | 112 dòng |
| `DatabaseStatusTable` | 140 dòng | 148 dòng |

Cùng một khung, cùng thứ tự: root `ColumnLayout` → `readonly property int <x>ColumnWidth` →
`PanelHeader` → `RowLayout` nhãn cột → `Rectangle` kẻ ngang → `ListView { clip; reuseItems;
model: vm.rows; delegate }` → `Text` trạng thái rỗng.

Phần đuôi gần như giống **từng ký tự** — `TradeLogTable.qml:111-141` so với
`KlineInspectorTable.qml:109-139` chỉ khác `objectName`, kiểu delegate, tên property bề rộng
cột, và câu chữ dòng rỗng.

`EPIC-021I` cần thêm hai bảng nữa (vị thế đang mở, lệnh đang chờ). Viết tiếp theo khung cũ sẽ
thành bản sao **thứ 4 và 5**.

## 2. Vì sao là task riêng, không làm kèm `EPIC-021I`

Nó chạm **3 widget đang chạy thật** trên 3 màn (Backtest, Data Management). Trộn vào task dựng
màn mới thì một hồi quy UI sẽ không phân biệt được là do trích xuất hay do màn mới — cùng lý do
`EPIC-021L` tách riêng việc đảo chiều phụ thuộc thay vì làm kèm.

## 3. Luật đã quyết sẵn hướng đi

[`qml-rule.md`](../../.agents/rules/qml-rule.md) §0.2 (quyết định user 2026-08-29):

> *"Cái gì dùng chung được thì phải dựng dùng chung, không viết bản sao 'gần giống'. […] Một hình
> 'gần giống nhưng hơi khác' là tín hiệu để **tổng quát hoá** component có sẵn (thêm cờ, thêm
> callback)"*

Tiền lệ có thật trong repo, không phải suy đoán: `SelectListVM` đã hấp thụ `TimezonePickerVM`,
**xoá** bản gốc chứ không giữ lại làm forwarder (xem docstring `select_list_vm.py`). Đó là hình
mẫu cho task này.

[`ONBOARDING.md`](../../.agents/ONBOARDING.md) §7 nói thêm chiều còn lại: *"đừng ngại redesign
một phần đã có… **'nó đang chạy được' không phải lý do để yên đó**"*.

## 4. Thiết kế đề xuất

`src/presentation/ui/qml/DataTable/` — `DataTable.qml` + `data_table_vm.py` + `NOTES.md` +
`preview.py` + `tests/`, đúng khuôn "1 widget = 1 thư mục" (§1).

Component nhận **mô tả cột** thay vì cột viết cứng: mỗi cột là `{key, label, width, align}`, và
delegate hàng do phía gọi cung cấp (`Component`/`sourceComponent`) — `ui-presentation-rule.md`
đã đòi *"column widths MUST be declared centrally as a Single Source of Truth and bound to both
header and row delegates"*, nên nguồn duy nhất đó chuyển vào `DataTable` là đúng chỗ của nó.

Ba thứ **bắt buộc** giữ, vì cả ba đều là bài học có hồ sơ:

- `textFormat: Text.PlainText` trên mọi `Text` render dữ liệu ngoài (chống UI injection —
  `ui-presentation-rule.md`).
- `elide: Text.ElideRight` **và** `Layout.minimumWidth: 0` cho cột chuỗi dài — thiếu cái thứ hai
  thì `elide` vô hiệu trong `RowLayout` (`BUG-076`).
- `qml/` **không** được import ngược `screens/` — guard
  `tests/unit/presentation/ui/qml/test_qml_library_does_not_import_screens.py` (`BUG-082`,
  `EPIC-021L`).

## 5. Không được tổng quát hoá cái gì

Ba bảng hiện có mỗi cái mang một thứ **riêng** của nó — không kéo vào `DataTable`:

- `TradeLogTable`: dải tab lọc (`vm.filterTabs`).
- `KlineInspectorTable`: dòng subtitle symbol/interval/count.
- `DatabaseStatusTable`: ô tìm kiếm trong `PanelHeader`, và nút hành động trên từng hàng.

Nhét cả ba vào một component là đổi ba bản sao lấy một component có ba nhánh `if` — cùng loại lỗi,
đóng gói khác đi. `DataTable` chỉ nhận **khung**; phần riêng vẫn ở widget gọi nó.

## 6. Kiểm thử

- **VM thuần, không `QApplication`** (§1.2): mô tả cột → hàng render đúng, cột rỗng, hàng rỗng.
- **Không hồi quy 3 màn đang chạy:** `tests/unit/presentation/ui/{qml,screens}/` phải xanh
  **không sửa một assert nào**. Sửa assert để cho qua là dấu hiệu đã đổi hành vi, không phải đã
  trích xuất — cùng tiêu chí `EPIC-021L` đã dùng.
- **`preview.py`** cho chính `DataTable` + 3 preview cũ vẫn chạy sạch offscreen (guard
  `test_preview_fixtures_exist.py` chạy thật `build_preview()`, bắt cả lỗi QML).
- **Guard** `test_qml_library_does_not_import_screens.py` vẫn xanh.

## 7. Xong là gì

3 bảng cũ dùng `DataTable`, tổng số dòng `.qml` giảm thật (đo trước/sau, ghi vào task), 0 assert
bị sửa, cổng bắt buộc xanh — rồi `EPIC-021I` dựng 2 bảng mới mà không thêm bản sao nào.
