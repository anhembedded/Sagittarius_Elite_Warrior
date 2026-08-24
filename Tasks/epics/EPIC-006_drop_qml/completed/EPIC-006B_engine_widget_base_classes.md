# EPIC-006B — Engine: xây base class QtWidgets (`Surface`/`Card`/`Overlay`/`Styled*`)

**Thuộc:** [`EPIC-006`](../README.md)
**Trạng thái:** ✅ Xong (2026-08-24)
**Thực hiện tại:** `Sagittarius_Engine` repo — `TASK-038`
([`Tasks/completed/TASK-038_qtwidgets_base_classes_surface_overlay_controls.md`](../../../../../Sagittarius_Engine/Tasks/completed/TASK-038_qtwidgets_base_classes_surface_overlay_controls.md)
trong repo Engine), commit `b1b90ee` trên `main`.

---

## Phạm vi

Xây `pyside_mvc/widgets/` (Engine) theo đúng
[`DECISION_2026-08-24_widget_architecture.md`](../DECISION_2026-08-24_widget_architecture.md):
4 chuỗi kế thừa đơn tuyến (`Surface→Card/Panel`, `Overlay`, mỗi `Styled*` đúng 1 gốc Qt riêng),
styling dùng chung qua composition (`apply_role()`), 2 guard mới thay guard QML cũ, 41 test.

## Diễn biến quan trọng: phát hiện `TASK-037` (qfluentwidgets) đang chạy song song

Trước khi viết dòng code nào, phát hiện `origin/main` của Engine đã vượt trước 8 commit không
biết tới — trong đó có `TASK-037`: một nhánh công việc **đã hoàn thành cùng ngày**, làm đúng
việc thoát QML nhưng bằng `qfluentwidgets` (thư viện Fluent Design bên thứ 3), đã có prototype
chạy thật, và ghi rõ user (ở phiên đó) **thích giao diện QWidget hơn QML**. Đây là mâu thuẫn
trực tiếp với hướng vừa duyệt (tự viết base class) — dừng lại, hỏi lại user trước khi viết code.
User chọn **đi tiếp theo ADR** (tự viết, không dùng qfluentwidgets). `IView` protocol từ
`TASK-037` được giữ lại làm công cụ tham khảo cho `EPIC-006C+`, không dùng ngay.

## Phát hiện kỹ thuật: `@abstractmethod` không có tác dụng thật với Qt widget

Kiểm chứng bằng code trước khi tin: `class Surface(QFrame, metaclass=_QtABCMeta)` với
`@abstractmethod` chưa implement **vẫn khởi tạo được bình thường** — Shiboken's metaclass không
hợp tác đúng với cơ chế chặn của `ABCMeta`. Thay bằng `type(self) is Surface: raise TypeError`
— đã verify hoạt động đúng.

## Phát hiện thứ 2: sơ đồ ban đầu (đã sửa trước khi code) có lỗi lineage

`DateTimeField` không thể kế thừa `StyledField(QLineEdit)` — `QDateTimeEdit` thật ra extends
`QAbstractSpinBox`, không phải `QLineEdit`. Bắt được và sửa **trước khi viết code**, cùng loại
lỗi với `Overlay(QDialog + QFrame)` bị bắt ở vòng duyệt ADR trước đó.

## Nút thắt bootstrap: `configure_app_qml()` không tự nạp `get_theme_bridge()`

`get_theme_bridge()`'s singleton chỉ được nạp palette khi có màn QML nào đó khởi tạo
(`register_theme()` gọi từ `create_quick_widget()`). Một app thuần QtWidgets sẽ không bao giờ
kích hoạt đường đó. **Chưa sửa trong task này** (nằm ngoài phạm vi — chỉ cần singleton có
palette trong lúc test riêng lẻ) — ghi lại rõ trong `apply_role()`'s docstring:
`EPIC-006C+` (khi Elite thật sự dựng màn hình 0% QML) sẽ cần thêm 1 dòng gọi
`get_theme_bridge(Palette.as_ui_dict())` trực tiếp trong `app_bootstrapper.py`, độc lập với
`configure_app_qml()`.

## Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` (Engine repo) — `RESULT: PASS`,
`890 passed, 5 skipped` (từ baseline 849, +41 test mới). `ruff`/`mypy` sạch trên mọi file mới.
2 guard mới tự kiểm trên chính `widgets/` — 0 vi phạm.

## Việc cần làm tiếp (`EPIC-006C`)

- Thêm bootstrap trực tiếp `get_theme_bridge(Palette.as_ui_dict())` vào Elite's
  `app_bootstrapper.py` (không phụ thuộc `configure_app_qml()`).
- Bắt đầu migrate `Sidebar.qml` (238 dòng) lên `widgets/` — pilot đầu tiên, always-on nên lỗi lộ
  ngay lập tức.
