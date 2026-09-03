# BUG-102 — Every `Overlay`/`QmlOverlay` dialog's SURFACE background never actually painted, letting `QmlOverlay` dialogs render see-through

**Reported date:** 2026-09-03
**Fixed date:** 2026-09-03
**Severity:** 🟡 P2 — no crash, no data loss, but a modal dialog (`TimeframePicker`, and by the same
mechanism every other `QmlOverlay`-hosted dialog: `SymbolPicker`, `TimezonePicker`, `TimeRangePicker`,
Capital, …) is unreadable, with the main window's own content bleeding through it.
**Status:** ✅ Fixed — see §3.

---

## 1. Hiện tượng (Symptom)

User gửi screenshot ứng dụng thật trên Linux/Wayland: mở `TimeframePicker` (dialog "CHỌN KHUNG
THỜI GIAN") từ màn Giao dịch — dialog hiện lên nhưng **thấy xuyên qua nó**: chữ/label của màn hình
chính phía sau ("PHIÊN GIAO DỊCH", nội dung Nhật ký giao dịch, tiêu đề cột "SYMBOL"/"THỜI GIAN"...)
chồng lấp trực tiếp lên grid chọn khung thời gian, không đọc được.

## 2. Root cause

Hai điều kiện cộng dồn:

1. `Overlay(QDialog)` (`kit/overlay.py`) tự style mình bằng
   `apply_role(self, StyleRole.SURFACE)` — đặt QSS `.Overlay { background-color: ...; }` (hoặc
   subclass name thật) qua `setStyleSheet()` **trực tiếp trên chính `self`**.
2. `QDialog` **không** kế thừa `QFrame` — nó là `QWidget` trần. Theo đúng tài liệu Qt style sheet:
   một `QWidget` subclass không phải `QFrame` "needs to set the `Qt::WA_StyledBackground`
   attribute for the style sheet to have an effect". `Surface`/`Panel`/`Card` (đều kế thừa
   `QFrame`) không cần cờ này — nền của chúng luôn vẽ đúng, đó là lý do bug này **không** lộ ra ở
   những widget đó. `Overlay` là nơi DUY NHẤT trong package tự style chính mình mà KHÔNG phải
   `QFrame`, và cờ đó chưa từng được set.

Hệ quả: nền SURFACE của `Overlay` **chưa bao giờ thực sự được vẽ** — với dialog chỉ chứa
QtWidgets thường (`ConfirmOverlay`, v.v.), lỗi này gần như vô hình vì Qt vẫn tự tô nền mặc định từ
palette. Nhưng `QmlOverlay` (host.py) đặt `self._quick.setClearColor(Qt.GlobalColor.transparent)`
cho thân QML **có chủ đích** — với lý do ghi rõ trong comment: *"Transparent so `Overlay`'s own
SURFACE styling shows behind the QML body"*. Giả định đó chỉ đúng nếu nền SURFACE thật sự được vẽ.
Vì nó không được vẽ, và một `QQuickWidget` với clear color trong suốt buộc cửa sổ top-level chứa
nó phải có alpha channel thật, toàn bộ dialog trở thành một bề mặt trong suốt thật (không chỉ vùng
canvas QML) — thấy xuyên tới bất cứ thứ gì nằm phía sau nó trong ngăn xếp hiển thị.

Đây **không phải** lỗi riêng của `TimeframePicker.qml` — mọi `QmlOverlay` subclass dùng chung
`host.py` đều mắc lỗi này; `TimeframePicker` chỉ là cái đầu tiên user chụp ảnh gặp phải.

## 3. Fix

`Overlay.__init__` (`kit/overlay.py`): thêm
`self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)` ngay trước
`apply_role(self, StyleRole.SURFACE)`. Một dòng, đúng lớp `QWidget` (không phải `QFrame`) Qt tài
liệu hoá rõ ràng — không đoán, không suy diễn thêm.

## 4. Regression test (viết trước, xác nhận đỏ đúng lý do trước khi sửa)

`tests/unit/presentation/ui/kit/test_overlay.py::test_the_surface_background_is_actually_paintable`
— assert `overlay.testAttribute(Qt.WidgetAttribute.WA_StyledBackground) is True`.

Trước khi sửa: **đỏ đúng lý do** — `AssertionError: assert False is True`. Sau khi sửa: xanh.

`tests/unit/presentation/ui/kit/` + `tests/unit/presentation/ui/kit/overlays/`: **289/289 xanh**.
`mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases src scripts` →
`Success: no issues found in 245 source files`.

## 5. Ghi chú xác minh

Sandbox này không có màn hình thật (`QT_QPA_PLATFORM=offscreen` only) — không tự chụp lại ảnh app
thật để xác nhận trực quan trên Wayland được. Test unit xác nhận đúng CƠ CHẾ Qt tài liệu hoá (cờ
được set), nhưng **user nên tự mở lại app thật** (`scripts/run-ui.ps1 -dev` hoặc tương đương) và mở
lại `TimeframePicker`/`SymbolPicker`/bất kỳ dialog QML nào khác để xác nhận nền đã đặc trở lại.
