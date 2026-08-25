# EPIC-006F — Tháo dỡ kit QML của Engine + xoá QML chết ở Elite

**Thuộc:** [`EPIC-006`](../README.md) · **Repo:** `Sagittarius_Engine` **và** `Sagittarius_Elite_Warrior`
**Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `006A`–`006E` ✅ (Elite đã hết consumer QML thật)

> **File này được tạo 2026-08-25.** `006F` tồn tại suốt epic dưới dạng **một dòng trong bảng
> §3 của README**, không có file task — nên không ai thấy phạm vi thật của nó. Số liệu dưới đây
> đo trực tiếp trên đĩa cùng ngày, không chép từ trí nhớ.

---

## 1. Phần Elite — 22 file `.qml` chết

`find src -name '*.qml'` → **22 file**. Đã kiểm chứng **không `.py` nào nạp chúng**: mọi hit
`load_qml`/`QQuickWidget`/`QmlHostView` trong `src/` giờ đều là docstring, và chính các docstring
đó ghi *"kept on disk, unloaded"* — đây đúng là **commit dọn dẹp đã hoạch định** từ chiến lược
rollback của `EPIC-005` (*"Không xoá file `.qml` ở commit migrate. Chỉ ngừng nạp nó. Xoá dồn vào
một commit dọn dẹp riêng ở cuối"*).

Chúng tự tham chiếu lẫn nhau nên phép dò "file mồ côi" thông thường **không** phát hiện; phải
kiểm từ phía Python.

### Kéo theo: 4 file test, 24 test — gate của thời QML

| File | Số test | Là gì |
| :--- | ---: | :--- |
| `test_qml_shared_foundation.py` | 6 | Phase-0 gate của `BOT-030`, chứng minh 2 tiền đề của cả kế hoạch migrate QML |
| `test_shared_ui_state_foundation.py` | 11 | Gate cho token UI-state + component `Sagittarius.UI` dựng trên chúng |
| `test_app_progress_bar.py` | 4 | Unit test cho `AppProgressBar` QML |
| `test_qml_imports_match_engine_qmldir.py` | 3 | Guard sinh ra từ `BUG-035` (engine đổi `QmlShared` → `Sagittarius.UI` làm 69 test đỏ) |

**Không xoá thẳng cả 4.** Ba cái đầu là gate cho một cuộc migrate **đã hoàn thành** → hết đối
tượng, xoá kèm ghi lý do. Cái thứ tư (`BUG-035` guard) đáng cân nhắc riêng: nó chặn một lớp lỗi
thật (engine đổi tên module QML), nhưng nếu Elite hết `.qml` thì nó không còn gì để canh — khi đó
xoá là đúng, **không phải** giữ cho có.

## 2. Phần Engine — câu hỏi mở, cần user quyết

Kit QML của Engine ở `extensions/pyside_mvc/Sagittarius/UI/`: **14 component** (`ActionCard`,
`AppDataTable`, `AppModal`, `BaseCard`, `DateTimePicker`, `FieldBackground`, `FormCard`,
`Gallery`, `LogPanel`, `StatefulButton`, `StreamCard`, `StyledCheck`, `TableCard`,
`TimeRangeCard`) + `qmldir`, cộng `QmlHostView`, `OverlayHost`, `qml_style`, `configure_app_qml`.

**Vướng mắc thật:** sample app `examples/student_management` **vẫn dùng QML**, và nó có **hai
backend chọn bằng config**:

```python
# roster_view_factory.py
use_qtwidget = bool(config.get("ui.qtwidget", False))
```

Tức QML là **đường mặc định** ở đó (`ui.qtwidget` mặc định `False`), còn qfluentwidgets là đường
opt-in. Xoá kit là sample app mất backend mặc định.

`EPIC-006`'s README ghi `examples/student_management` **ngoài phạm vi** epic, nhưng dòng `006F`
lại yêu cầu "xử lý `RosterScreen.qml`". Hai câu đó không thể cùng đúng.

**Ba lựa chọn, cần user chốt trước khi động vào Engine:**

1. **Đảo mặc định của sample app sang qfluentwidgets**, rồi xoá kit QML + cả 2 file `.qml` của
   sample. Sạch nhất; nhưng sample app mất khả năng minh hoạ backend QML, mà đó có thể chính là
   giá trị của nó với người dùng engine khác.
2. **Giữ kit QML ở Engine**, chỉ làm phần Elite (mục 1). Engine vẫn là framework hỗ trợ cả hai
   backend — hợp lý cho một thư viện có người dùng ngoài Elite. `006F` khi đó thu hẹp lại, và
   nên đổi tên cho đúng việc.
3. **Tách kit QML thành extension tuỳ chọn** — ai cần thì cài. Đúng nhất về kiến trúc, đắt nhất
   về công.

Nghiêng về **2**: Engine là thư viện, Elite chỉ là một consumer. Việc Elite bỏ QML **không** đủ
lý do để tước một backend của framework, nhất là khi sample app đang dùng nó làm mặc định.

## Bằng chứng phải nộp

- `find src -name '*.qml'` ở Elite → rỗng.
- Nêu rõ số test giảm và **vì sao từng file bị xoá là hết đối tượng**, không phải "xoá cho xanh".
- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`.
- Nếu chọn phương án 1: gate của **Engine** cũng phải xanh, và sample app chạy được bằng
  `--qtwidget`.

## Rủi ro

Xoá `.qml` là thao tác một chiều với 22 file. Nhánh `epic/EPIC-006-drop-qml` đã merge vào
`master-warrior` (`f4076a7`) nên **không còn nhánh rollback rẻ** như các sub-task trước — làm
trên nhánh riêng, hoặc chấp nhận rollback bằng revert commit.
