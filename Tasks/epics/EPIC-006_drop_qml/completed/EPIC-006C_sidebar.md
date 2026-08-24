# EPIC-006C — `Sidebar.qml` → QtWidgets

**Thuộc:** [`EPIC-006`](../README.md)
**Trạng thái:** ✅ Xong (2026-08-24)

---

## Phạm vi

`Sidebar.qml` (238 dòng) — chrome always-on của app (navigation rail kiểu VS Code Activity
Bar), 2 chế độ mở rộng (220px)/thu gọn (48px). Không phải "Card" — là window chrome, dùng
`Palette.BG_SIDEBAR` riêng (khác `bgCard`), viền chỉ 1 cạnh phải, không bo góc.

## Quyết định kiến trúc: không ép vào `Surface`/`Card`

`Sidebar` không kế thừa base class mới của Engine (`Card`/`Panel`) — hình dạng thị giác khác
hẳn (không header, không radius, viền 1 cạnh) và nó là window chrome giống `MainWindow` chính
nó, không phải nội dung màn hình. `_NavButton(QPushButton)` cũng không dùng `StyledButton` của
Engine — nút điều hướng cần icon+label tự layout, trạng thái active/tooltip/route riêng, không
khớp 3 role cố định (`PRIMARY`/`SECONDARY`/`DANGER`) của `StyleRole`. Cả hai đọc `Palette` trực
tiếp — đúng escape hatch mà `EPIC-005`'s widget đã dùng (`_StatusRowWidget` và tương tự).

## Bootstrap: sửa nút thắt đã ghi ở `EPIC-006B`

Thêm `get_theme_bridge(Palette.as_ui_dict())` vào `app_bootstrapper.py`, gọi ngay sau
`configure_app_qml()`, độc lập với nó — cần thiết vì Sidebar giờ không đi qua đường
`create_quick_widget()`/`register_theme()` nữa (đường duy nhất trước đây nạp token bridge).

## `SidebarViewModel` — không đổi

Là `QObject` thuần, không phải `BaseQmlViewModel` (không có `uiMode` FSM để bind) — dùng lại y
nguyên cho QtWidgets, không sửa dòng nào.

## Test — viết lại 7 test QML-specific, 12 test logic thuần giữ nguyên

`tests/unit/presentation/ui/components/test_sidebar.py`: các test `qml_item`/`quick_widget`
đổi sang đọc `sidebar._nav_buttons[key]` trực tiếp — thêm 2 accessor công khai trên
`_NavButton` (`display_text`, `is_active`) thay cho `.property("text")`/`.property("isActive")`
của QML. Số lượng test không đổi (19), chỉ đổi cách truy cập widget.

## Phát hiện: `test_sanity_ui_e2e.py` đã hỏng sẵn từ trước

`tests/integration/presentation/ui/test_sanity_ui_e2e.py` (nằm ngoài gate mặc định, `BOT-038`)
đã có **2/8 test fail sẵn** trước khi tôi động vào — từ khi `EPIC-005` migrate Settings/
DataManagement, không ai cập nhật file này. Sidebar cộng thêm 4 fail nữa (tham chiếu
`main_window._sidebar.quick_widget` không còn tồn tại). File này còn đụng Dashboard (sắp
migrate ở `EPIC-006D`) — **cố tình chưa sửa**, để viết lại một lần duy nhất sau khi Dashboard +
Backtest xong, tránh viết lại nhiều lần.

## Guard `EPIC-005B` bắt lại đúng bug cũ

Literal `#5b6270` trong code không trùng token nào (giữ nguyên, hợp lệ — QML gốc cũng dùng màu
riêng này cho section title, khác `Palette.MUTED`). Nhưng comment giải thích ban đầu lại **trích
dẫn** `#848E9C` (giá trị thật của `Palette.MUTED`) để so sánh — bị guard bắt (nó quét cả
comment). Sửa bằng cách không trích hex trực tiếp trong comment — đúng bug pattern đã gặp 3 lần
trước đó trong `EPIC-005`.

## Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`, `1799 passed / 54 sanity`
— khớp chính xác baseline (19 test viết lại, không thêm/bớt).
