# EPIC-006D — `DevBoardPanel.qml` → QtWidgets

**Thuộc:** [`EPIC-006`](../README.md)
**Trạng thái:** ✅ Xong (2026-08-24)

---

## Phạm vi

`DevBoardPanel.qml` (385 dòng) — nửa phải của màn Dashboard (Dev Board): top status bar
(title/price ticker/WS badge/Reload), System Controls (Market/Symbol/Strategy combo, Data
Range, 3 nút hành động), Indicators checklist, System Monitor log. Nửa trái (`ChartCard`,
pyqtgraph) **không đổi** — đã là QtWidgets từ trước, `DashboardView` là layout hybrid
(`QSplitter`) nối 2 nửa lại.

## Quyết định thiết kế: giữ nguyên bộ màu riêng của "Live Testbed", không ép qua `Surface`/`Card`

Đo được: màu của `DevBoardPanel` (`#12141d` nền card, `#222533` viền, `#181a24` nền field...)
**khác** — dù gần giống — các token `Palette` dùng ở màn hình khác (`BG_CARD=#111318`,
`BORDER=#23262e`...). Xác nhận không cái nào trùng token thật (nếu trùng đã tự động là bug
theo guard `EPIC-005B`). `DevBoardPanel.qml`'s docstring tự gọi đây là *"Live Testbed"* — một
bộ nhận diện thị giác cố ý tách biệt phần còn lại của app, không phải màu bị trôi dạt cần "tiện
thể" sửa. Giữ nguyên y hệt bằng literal riêng (`_CARD_BG`, `_FIELD_BG`...), **không** dùng
`Card`/`Panel` mới của Engine (`apply_role(SURFACE)` sẽ đổi sang đúng `Palette.BG_CARD` — sai
màu). Đây là ví dụ ngược lại với `Sidebar` — không phải mọi Rectangle bo góc đều nên ép qua
base class chung.

## Bug thật tìm được: `BaseQmlViewModel.set_ui_mode()` bắn `uiModeChanged` **trước** khi cập nhật `controlsEnabled`

Phát hiện khi smoke-test tay: nút "Start Live" **không disable** đúng lúc `uiMode == "LIVE"`.
Điều tra bằng code thật (không đoán): `set_ui_mode()` gọi `uiModeChanged.emit()` **trước** dòng
tính lại `_controls_enabled`. Với QML, không lộ ra — binding khai báo của QML tự re-evaluate
lười, đọc state cuối cùng sau khi `set_ui_mode()` return hoàn toàn, bất kể thứ tự emit. Với
Qt signal/slot nối trực tiếp (như `DevBoardPanel`), slot chạy đồng bộ **bên trong** `.emit()`,
nên đọc phải giá trị `controlsEnabled` **cũ** — chậm một nhịp.

**Đây là bug thật trong Engine**, không phải trong Elite — sửa tại nguồn
([`Sagittarius_Engine` commit `9ba0041`](../../../../../Sagittarius_Engine/sagittarius_engine/extensions/pyside_mvc/runtime/base_view_model.py),
merge `main` tại `8aae646`): tính và ghi `_controls_enabled` **trước** khi emit bất kỳ signal
nào. Kèm 7 test mới ở Engine, 2 trong đó cố tình đọc `controlsEnabled` **từ bên trong** listener
của `uiModeChanged` để khoá chặt chính xác race này. Gate Engine: `890 → 897 passed`.

`DevBoardPanel` là **consumer imperative đầu tiên** của `controlsEnabled` trong toàn bộ 2 repo
— mọi Elite ViewModel trước đó (`DataManagementViewModel`, `SettingsViewModel`) tự hand-check
`uiMode == "IDLE"` trực tiếp, không dùng `controlsEnabled` phái sinh. Bug tồn tại từ lâu nhưng
chưa từng bị kích hoạt.

## Sự cố môi trường: `pip install -e` kiểu PEP 660 làm mypy mù

Để nạp `pyside_mvc.widgets` mới (từ `EPIC-006B`) vào `.venv` của Elite, cài lại
`sagittarius_engine` bằng `pip install -e ../Sagittarius_Engine`. Bản cài mặc định của
`setuptools>=64` dùng cơ chế **import-hook finder** (PEP 660) — `import sagittarius_engine`
chạy đúng, nhưng **mypy không thực thi import hook**, chỉ quét thư mục tĩnh → toàn bộ 39 lỗi
`Cannot find implementation ... sagittarius_engine` xuất hiện, không liên quan gì tới code vừa
sửa. Sửa bằng cài lại với `--config-settings editable_mode=compat` — buộc pip tạo `.pth` cổ
điển (chỉ chứa đường dẫn thư mục thật), mypy quét được bình thường.

## Test — viết lại 2 test QML-specific, thêm 15 test mới cho `DevBoardPanel`

`test_dashboard_view.py`: 2 test dùng `quick_widget`/`qml_item` viết lại dùng `view._panel`
thật. `test_dev_board_panel.py` (mới, 15 test): price ticker/WS status khớp nguồn, checklist
indicator round-trip, `controlsEnabled` gating đúng ở `LIVE`/`LOCKED`/quay lại `IDLE` (khoá
chặt đúng bug vừa sửa), history-loading label, request signal (Load/Start/Stop), đồng bộ 2
chiều field ngày tháng, log panel bind đúng model.

## Phát hiện: `test_sanity_ui_e2e.py` cộng thêm lỗi — vẫn cố tình chưa sửa

Đúng như dự đoán ở `EPIC-006C`: file này (ngoài gate mặc định) giờ hỏng thêm ở phần Dashboard.
Chưa sửa — dời sang một lần viết lại duy nhất sau khi `EPIC-006E` (Backtest) xong, vì file còn
đụng cả Backtest.

## Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` (cả 2 repo) — `RESULT: PASS`. Elite:
`1800 passed / 54 sanity` → `1815 passed / 54 sanity` (+15 test mới, khớp chính xác). Engine:
`890 → 897 passed` (bug fix `controlsEnabled`).
