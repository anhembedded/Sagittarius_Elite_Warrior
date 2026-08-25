# EPIC-006F — Tháo dỡ kit QML của Engine + xoá QML chết ở Elite

**Thuộc:** [`EPIC-006`](../README.md) · **Repo:** `Sagittarius_Engine` **và** `Sagittarius_Elite_Warrior`
**Trạng thái:** ✅ Xong (2026-08-25) — phần Elite; phần Engine tách ra task riêng
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

## 2. Phần Engine — **không làm được trong epic này** (đã kết luận, không còn là câu hỏi mở)

Kit QML của Engine ở `extensions/pyside_mvc/Sagittarius/UI/`: **14 component** (`ActionCard`,
`AppDataTable`, `AppModal`, `BaseCard`, `DateTimePicker`, `FieldBackground`, `FormCard`,
`Gallery`, `LogPanel`, `StatefulButton`, `StreamCard`, `StyledCheck`, `TableCard`,
`TimeRangeCard`) + `qmldir`, cộng `QmlHostView`, `OverlayHost`, `qml_style`, `configure_app_qml`.

**Câu hỏi này đã có lời giải — bằng chính README của epic, không phải theo ý ai.**

Đo thật: cả hai file `.qml` của sample app đều mở đầu bằng

```qml
import Sagittarius.UI 1.0
```

tức sample app **cần** kit. Mà §5 của [`README`](../README.md) đã chốt sẵn:

> *"`examples/student_management` (Engine sample app) **không bị xoá QML** — nó là ví dụ minh
> hoạ cách dùng framework QML […]. Quyết định số phận của nó thuộc về Engine repo, không phải
> epic này. `EPIC-006F` chỉ cần đảm bảo **không xoá nhầm thứ nó cần**."*

Hai điều đó cộng lại: **kit QML không tháo được trong phạm vi epic này.** Tháo kit chính là
"xoá nhầm thứ sample app cần" — đúng thứ §5 cấm.

Sample app còn có hai backend chọn bằng config (`roster_view_factory.py`:
`use_qtwidget = bool(config.get("ui.qtwidget", False))`) và **QML là mặc định**, nên kể cả về
mặt hành vi thì tháo kit cũng làm hỏng đường mặc định.

### Hệ quả: `006F` thu hẹp lại, và nên đổi tên

Việc thật còn lại **chỉ là phần Elite** ở mục 1. Tên "tháo dỡ kit QML" không còn mô tả đúng việc
— đề nghị đổi thành *"xoá QML chết ở Elite"*.

Muốn thật sự tháo kit của Engine thì đó là **một task riêng ở repo Engine**, và phải quyết trước:
đảo mặc định của sample app sang qfluentwidgets, hay tách kit thành extension tuỳ chọn. Không
thuộc `EPIC-006`.

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

---

## Xong 2026-08-25 — phần Elite. Phần Engine **không thuộc epic này** (xem §2)

**Gate:** `RESULT: PASS`, **1734 passed** (baseline trước khi xoá: 1741).

### Đã xoá

- **22 file `.qml`** trong `src/` — `find src -name '*.qml'` giờ trả về **0**.
- **2 file test** (7 test): `test_app_progress_bar.py` (nạp `AppProgressBar.qml` của Elite),
  `test_qml_imports_match_engine_qmldir.py` (quét import trong `.qml` của Elite — hết `.qml`
  thì hết đối tượng canh, guard `BUG-035` không còn gì để bảo vệ).

Tổng **4.978 dòng**. `1741 − 7 = 1734` khớp chính xác, và **không test nào khác vỡ** — bằng chứng
mạnh nhất cho việc 22 file kia thật sự chết.

### Sửa một giả định sai của chính file task này

Mục 1 ở trên (viết trước khi làm) liệt kê **4 file test, 24 test** sẽ chết theo. **Sai.** Kiểm
từng file thì chỉ **2 file, 7 test** phụ thuộc `.qml` của Elite:

| File | Đọc gì | Kết luận |
| :--- | :--- | :--- |
| `test_qml_shared_foundation.py` (6) | tự viết `_PROBE_QML` vào tmp, kiểm **kit của Engine** | **GIỮ** |
| `test_shared_ui_state_foundation.py` (11) | tự viết `_PROBE_QML`, kiểm token + component **Engine** | **GIỮ** |
| `test_app_progress_bar.py` (4) | nạp `src/.../AppProgressBar.qml` của Elite | xoá |
| `test_qml_imports_match_engine_qmldir.py` (3) | quét `.qml` trong `src/` của Elite | xoá |

Hai file giữ lại kiểm **kit QML của Engine — thứ vẫn còn nguyên** (§2). Xoá chúng là mất phần
kiểm cho một thứ đang sống. Ghi lại vì đây đúng loại nhầm mà "đếm rồi xoá theo danh sách" hay
mắc: tên file có chữ `qml` không có nghĩa nó phụ thuộc `.qml` của app.

### Việc còn lại, **không** thuộc epic này

Kit QML của Engine (14 component + `QmlHostView`/`OverlayHost`/`configure_app_qml`) **ở lại**,
vì `examples/student_management` `import Sagittarius.UI 1.0` và §5 của README cấm xoá thứ sample
app cần. Muốn tháo thật thì mở **task riêng ở repo Engine**, sau khi quyết: đảo mặc định sample
app sang qfluentwidgets, hay tách kit thành extension tuỳ chọn.
