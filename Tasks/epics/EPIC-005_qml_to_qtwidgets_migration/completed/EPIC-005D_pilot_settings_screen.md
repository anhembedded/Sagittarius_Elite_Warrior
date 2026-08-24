# EPIC-005D — Pilot: `SettingsScreen` — đo chi phí thật

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** ✅ Xong (2026-08-24)
**Phụ thuộc:** `EPIC-005A` ✅, `EPIC-005B` ✅, `EPIC-005C` ✅

---

## Kết quả — trả lời đúng câu hỏi task đặt ra

> Một màn hình QtWidgets có đạt parity thị giác chỉ với `Palette` + QSS, **không cần** bộ
> kit QML (`BaseCard`, `StatefulButton`, `FieldBackground`, `StyledCheck`…), hay không?

**Có — và câu hỏi hoá ra dễ hơn dự kiến.** Đọc `SettingsScreen.qml` (363 dòng) trước khi
viết code phát hiện: màn hình này **chưa từng dùng bộ kit engine**. Mọi thứ tự vẽ bằng
`Rectangle` thô + restyle `Button`/`TextField`/`SpinBox` thủ công (background/border/radius
riêng từng control). Không có `BaseCard`, không có `StatefulButton`. Nên N (số component kit
phải viết lại) = **0**, không phải vì migrate dễ mà vì kit chưa từng chạm màn này.

## Thực hiện

- `settings_view.py` viết lại hoàn toàn: `SettingsView(BaseView)` thay vì
  `SettingsView(QmlHostView)`, tự build cây `QFrame`/`QGridLayout`/`QLineEdit`/`QSpinBox`
  bằng tay, giữ nguyên mọi `objectName` (`txtApiKey`, `btnRevealSecret`,
  `spinDefaultSyncDays`…) — automation contract không đổi.
- Wiring 2 chiều tự tay nối Qt signal thay cho QML property binding: `textEdited`/
  `valueChanged` → setter ViewModel; mỗi `*Changed` signal của ViewModel → cập nhật lại
  widget. `SettingsViewModel`/`SettingsPresenter` **không đổi** — migration khoanh đúng vào
  lớp render.
- `SettingsScreen.qml` **không xoá**, chỉ ngừng nạp (`settings_presenter.py` đổi
  `view.load_qml(...)` → `view.set_view_model(...)`, và di chuyển lời gọi này xuống **sau**
  `_load_from_config()` — thứ tự cũ đúng cho QML (set context property trước, parse sau) mà
  sai cho QtWidgets (đọc giá trị ngay lúc gọi); phát hiện lúc smoke-test tay, sửa trước khi
  chạy gate).
- `preview.py` đổi sang dựng `SettingsView` thật thay vì `QQuickWidget`.

## Chỗ QtWidgets tốt hơn thấy rõ

- `echoMode` đọc được trực tiếp trên `QLineEdit` thật — bản QML cũ phải né việc này
  (comment cũ trong test: *"PySide6 has no converter for QQuickTextInput::EchoMode"*), giờ
  assert thẳng `secret_field.echoMode() == QLineEdit.EchoMode.Password`.
- Tab-order/focus/keyboard nav có sẵn theo thứ tự thêm widget — QML bản cũ không có gì
  tương đương, đúng như dự đoán trong ADR.
- Bug lịch sử của bản QML (status label kẹt ở y=0 vì `ColumnLayout` bỏ qua child ẩn) **không
  tồn tại** ở QtWidgets — `QVBoxLayout` luôn layout mọi widget đã thêm, không phụ thuộc
  `visible`. Test regression riêng cho bug đó (`test_status_line_is_laid_out_below...`) bị bỏ
  vì không còn gì để test — thay bằng test khác có giá trị hơn (màu status theo lỗi/thành
  công).

## Chỗ QtWidgets không tốt hơn / trung tính

- QSS string ghép tay (`f"QPushButton {{ ... }}"`) không kém dài dòng hơn QML property
  gán trực tiếp — không phải thắng rõ rệt, chỉ là cách khác.
- Layout lồng nhau (`QVBoxLayout` trong `QFrame` trong `QVBoxLayout`...) verbose hơn khai
  báo QML tương đương — bù lại bằng việc không cần JS engine.

## Phát hiện ngoài dự tính: guard `EPIC-005B` bắt được bug thật của chính migration này

Viết `_FIELD_BG = "#17181d"` (copy trực tiếp từ QML để giữ parity màu) — guard
`test_no_second_hardcoded_copy_of_a_palette_color_exists_in_presentation_ui` (từ
`EPIC-005B`) bắt được ngay: giá trị đó đã tồn tại là `Palette.STATE_IDLE_BG`. Sửa dùng
`Palette.STATE_IDLE_BG`/`STATE_HOVER_BG` trực tiếp. Guard cũng bắt luôn 2 hex đó xuất hiện
lại trong **comment** giải thích (regex quét toàn văn bản, không phân biệt code/comment) —
phải viết lại comment không nhắc hex trần. Guard hoạt động đúng như thiết kế, hai lần liền.

## So sánh thị giác

Ảnh chụp trước (QML, `SettingsScreen.qml` render qua `QQuickWidget`) và sau (QtWidgets,
cùng dữ liệu, cùng `Palette`) đã gửi trực tiếp cho user — bố cục, màu sắc, spacing khớp.

## Test

Chưa có test nào phủ layer render trước migration này — test cũ (`test_settings_presenter.py`)
chỉ phủ Presenter/ViewModel qua `qml_item()`/`quick_widget.rootObject()`. Viết lại phần
"QML rendering" thành "Widget rendering", assert qua `findChild(QLineEdit, objectName)` thật
thay vì truy vấn QML runtime. Phần test Presenter/ViewModel logic (không phụ thuộc QML hay
QtWidgets) giữ nguyên 100%, không đổi.

Net: 1790 → 1791 (+1) — bỏ 1 test (bug-QML-specific, không còn áp dụng), thêm 2 test mới
(`test_editing_a_widget_reaches_the_view_model`, `test_status_label_reflects_success_and_error_colour`).

## Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`, verify qua log file.
Baseline tự chụp trước khi sửa dòng đầu tiên: `1790 passed / 54 sanity`. Sau: `1791 passed /
54 sanity`, không `FAILED`/`ResourceWarning`/`Traceback`.

## Điểm quyết định

Chi phí thấp hơn nhiều so với lo ngại ban đầu — không có component kit nào phải viết lại vì
`SettingsScreen` chưa từng dùng kit. Khuyến nghị: đi tiếp `EPIC-005E` (`DatabaseScreen` —
có khả năng cũng không dùng kit, cần kiểm tra thật trước khi giả định lại chi phí = 0).
