# BOT-124 — Trích `DataTable` dùng chung cho `ui/qml/`, gộp 3 bản sao đang có

- **Trạng thái:** ✅ **Hoàn thành (2026-09-02)**
- **Repo:** Elite
- **Chặn:** [`EPIC-021I`](../epics/EPIC-021_ket_noi_binance_futures_testnet/completed/EPIC-021I_man_giao_dich_moi.md) §3.2.2 — hết chặn, `EPIC-021I` dựng 2 bảng mới trên `DataTable` này

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


---

## 8. Kết quả (2026-09-02)

### 8.1 Lệch so với thiết kế đề xuất ở §4 — bỏ `data_table_vm.py`

§4 giả định `DataTable.qml` + `data_table_vm.py`. Khi thiết kế thật, `DataTable` hoá ra
**không có gì để dẫn xuất** — `columns`/`rowsModel`/`rowDelegate`/`isEmpty`/`emptyText` đều là
property truyền thẳng, không tính toán, không lọc, không validate. `qml-rule.md` §1.3 nói đúng
trường hợp này: *"một widget mà toàn thân chỉ là copy state, không có gì để dẫn xuất, không được
viết VM"* — và repo **đã có tiền lệ thật** cho đúng hình dạng này: `qml/kit/` (7 component,
`PanelHeader`/`Button`/`StatCard`/...), *"Pure QML, no Python VM for any of the six"*.
`DataTable` đi theo đúng khuôn đó: `__init__.py` chỉ để `tests/` có package riêng, không có
`_vm.py`. Quyết định tại chỗ theo `ONBOARDING.md` §7 (tiền lệ đã kiểm chứng ngay trong repo),
không hỏi lại.

### 8.2 `width: rowsView.width` → `width: ListView.view.width`

Ba bảng gốc định vị delegate bằng cách tham chiếu thẳng `id` của `ListView` cùng file
(`delegate: TradeLogRow { width: rowsView.width }`). Sau khi `ListView` chuyển vào bên trong
`DataTable.qml`, `id: rowsView` không còn nằm trong phạm vi nhìn thấy được của file gọi (nơi
`rowDelegate: Component { ... }` được viết). Thay bằng `ListView.view.width` — attached property
Qt Quick gắn cho **mọi** delegate bất kể `Component` được viết ở file nào, vì việc gắn xảy ra lúc
khởi tạo (do `ListView` tạo ra), không phải theo phạm vi từ vựng. Không phải hack — đây là idiom
đúng hơn bản gốc. `TradeLogRow.qml`/`KlineInspectorRow.qml`/`DatabaseStatusRow.qml` **không sửa
một dòng nào**.

### 8.3 Kiểm chứng "0 assert bị sửa" — đo, không suy đoán

`git stash`-diff `--collect-only` trên đúng target cổng bắt buộc quét (`Sagittarius_Elite_Warrior/tests`):
**0** test ID thêm/bớt/đổi tên. Số dòng passed chênh +5 chỉ vì
`tests/unit/test_logging_namespace_guard.py` tham số hoá theo **từng file** trong `src/`, và 5
file `.py` mới của `DataTable` (không file nào gọi `logging.getLogger()`) tự động cộng vào —
không phải hành vi mới.

| Bộ test | Trước | Sau |
| :--- | :---: | :---: |
| `qml/TradeLogTable/tests/` | 17/17 | 17/17, **0 assert sửa** |
| `qml/KlineInspectorTable/tests/` | 8/8 | 8/8, **0 assert sửa** |
| `qml/DatabaseStatusTable/tests/` (gồm regression `BUG-076`) | 23/23 | 23/23, **0 assert sửa** |
| `tests/unit/presentation/ui/qml/` (mọi guard) | xanh | xanh |
| `tests/unit/presentation/ui/screens/` (2 màn nhúng thật) | 819 xanh | 819 xanh |
| `DataTable` (mới) | — | 9/9 |

### 8.4 Dòng `.qml` — đo trước/sau

| File | Trước | Sau |
| :--- | ---: | ---: |
| `TradeLogTable.qml` | 141 | 91 |
| `KlineInspectorTable.qml` | 139 | 74 |
| `DatabaseStatusTable.qml` | 140 | 88 |
| **3 wrapper, tổng** | **420** | **253** |
| + `DataTable.qml` (mới, dùng chung) | — | 127 |
| **Tổng cả 4 file** | **420** | **380** |

Giảm thật kể cả tính gộp cả component dùng chung; bảng thứ 6 sau này chỉ còn tốn cột + delegate,
không tốn lại phần khung.

### 8.5 Cổng bắt buộc

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, `FAILED_STEPS: none`,
quét `LOG_FILE` sạch (không khớp `FAILED|ERROR|Traceback|ResourceWarning` thật — khớp duy nhất
là tên tham số hoá `[ERROR]` của một test không liên quan, đã xác nhận từ trước).
