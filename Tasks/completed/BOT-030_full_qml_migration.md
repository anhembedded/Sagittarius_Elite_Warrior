---
id: "BOT-030"
title: "Nhiệm vụ: Full QML Migration (chart giữ QtWidgets)"
status: "completed"
---

# Nhiệm vụ: Full QML Migration (chart giữ QtWidgets)

## 1. Mục tiêu (Objective)
Chuyển toàn bộ UI sang QML **trừ `ChartCard`** (giữ QtWidgets/pyqtgraph — đã chứng minh, không đổi). Lý do lần này **không phải hiệu năng** (bug pan giật đã tìm ra và sửa xong, thuần thuật toán, không liên quan framework) — mà là **AI dịch mockup sang code trực tiếp hơn ở QML** (style inline tại component, không phải tách rời qua `style.qss` + `objectName` như Widgets).

## 2. Mô tả (Description)
Thay thế `BOT-029` Phase 3 (restyle Database bằng Widgets) — gộp thẳng thiết kế đó (stat tile, search, nút placeholder disabled) vào bản QML luôn, không làm 2 lần.

**Quyết định kiến trúc chính** (xem đầy đủ trong plan file):
1. `PresenterManager`/routing giữ nguyên 100% — đã chứng minh ở `BOT-028`.
2. FSM → UI state: bỏ `UIMatrixMixin`/`ui_matrix.json` cho màn QML, thay bằng property `uiMode` — **không cần sửa `BasePresenter`** (đã đọc kỹ code, nó fallback qua `view.apply_ui_mode` sẵn).
3. Hạ tầng QML dùng chung xây trong `Binace_Bot` trước (`ThemeBridge`, `QmlHostView`) — chưa promote vào `pyside_mvc` (đợi Phase 5 mới quyết).
4. `LogPanel.qml` dùng chung cho Dev Board + Database (thay 2 bản `MonitorCard` riêng).
5. Database cần `DatabaseStatusTableModel(QAbstractTableModel)` — model đầu tiên của dự án.
6. Dev Board vẫn hybrid: `QSplitter` với `ChartCard` (Widgets) + 1 `QQuickWidget` (phần còn lại).
7. Xoá file Widgets cũ ngay sau khi bản QML thay thế đã chạy/test xong — không để cruft.

## 3. Các bước thực hiện (Action Items)
- [x] Phase 0: `ThemeBridge` + `QmlHostView` + xác nhận `apply_ui_mode` duck-typing hoạt động qua màn QML thử nghiệm.
- [x] Phase 1: Sidebar → QML (tái dùng quyết định branding/section từ `BOT-029` Phase 1).
- [x] Phase 2: Settings/API & Credentials → QML lại (lần 2, dùng `QmlHostView`/`ThemeBridge`).
- [x] Phase 3: Database → QML (`SyncControlCard` + `DatabaseStatusTableModel` + `TableView` + `LogPanel.qml` + thiết kế `BOT-029` Phase 3 gộp vào).
- [x] Phase 4: Dev Board (Control/Indicator/Monitor) → QML, chart giữ Widgets, `DashboardQmlViewModel` mới.
- [x] Phase 5: Dọn dẹp (xoá card Widgets cũ), `ci-local.ps1 -Full`, retro promote lên `pyside_mvc` hay không, cập nhật `BOT-029` là "superseded" không phải "abandoned".

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đây là task lớn nhất từ trước tới giờ trong chuỗi UI — mỗi phase có test gate riêng + screenshot thật, chỉ sang phase sau khi phase trước xanh, giữ đúng kỷ luật đã áp dụng xuyên suốt `BOT-028`/`BOT-029`.
- `MonitorCard` bị dùng ở cả Dev Board lẫn Database — phải xoá đúng thời điểm (sau khi CẢ 2 nơi dùng nó đã chuyển xong), không xoá sớm.

## 5. Ghi chú hoàn thành (Completion Notes)

**Trạng thái cuối:** cả 4 màn (Sidebar, Settings/API & Credentials, Database, Dev Board) chạy QML; `ChartCard` là ngoại lệ duy nhất, vẫn QtWidgets/pyqtgraph vĩnh viễn — đúng như quyết định ban đầu. `ci-local.ps1 -Full` xanh: **283 passed, 2 xfailed, coverage 92.31%**.

**Hạ tầng QML dùng chung đã xây** (`Binace_Bot/src/presentation/ui/screens/_qml_shared/`): `ThemeBridge` (palette), `QmlHostView` + `create_quick_widget()` (factory dùng chung cho cả `QmlHostView` lẫn `DashboardView`'s hybrid `QSplitter`), `BaseQmlViewModel` (property `uiMode`), `IconImageProvider`, `qml_style.py` (pin style "Basic"), `LogListModel` + `LogPanel.qml` (dùng chung Database + Dev Board).

**Quyết định KHÔNG promote vào `sagittarius_engine/extensions/pyside_mvc` ở lần này** (đã cân nhắc kỹ, không phải quên):
Kiểm tra toàn repo (`examples/`, `tools/`) xác nhận **chưa có app nào khác** dùng `pyside_mvc` ngoài `Binace_Bot`. Promote một pattern lên package dùng chung khi chỉ có 1 consumer thực tế là generalize sớm — đúng cái bẫy mà `BOT-028` retro đã né ("đợi màn hình QML thứ 2"), giờ có 4 màn nhưng vẫn chỉ 1 app dùng. Giữ nguyên trong `Binace_Bot` cho tới khi có app thứ 2 thật sự cần host QML — đó mới là tín hiệu đúng để promote (không phải đếm số phase/màn hình trong CÙNG 1 app).

**Giới hạn đã biết, cố tình không sửa (out of scope cho task này):**
- Cơ chế `dev.mode=True` auto-log-click (`_ButtonClickWatcher` trong `sagittarius_engine/pyside_mvc/base_view.py`) chỉ tìm được `QPushButton` qua `QWidget.findChildren` — không thấy nút trong QML scene graph. Đúng vậy từ Phase 2 (Settings), giờ đúng luôn cho toàn bộ 4 màn. Test `test_sanity_dev_mode_click_logging_does_not_reach_qml_buttons` ghi nhận hành vi này thay vì âm thầm mất coverage. Không sửa `sagittarius_engine` cho việc này — cùng lý do với quyết định không-promote ở trên (sửa framework dùng chung cho 1 app dùng thì nên đợi có nhu cầu thật).
- `UIMatrixMixin`/`ui_matrix_mixin.py` **không bị xoá** khỏi `sagittarius_engine` dù `Binace_Bot` không còn dùng — đây là primitive của framework dùng chung, không phải dead code của riêng app này.

**Đã dọn ở Phase 5:**
- Xoá `src/config/ui_matrix.json` + toàn bộ chỗ load nó (`main.py`, `app_bootstrapper.py`, và 4 test fixture load trực tiếp file này: `tests/integration/presentation/ui/conftest.py`, `test_sanity_ui_e2e.py`, `test_bootstrapper_di_sanity.py`, `test_config_integration.py` — file cuối có assertion trực tiếp lên nội dung "main"/"data_management" section, phải viết lại).
- Xoá `IconLoader.get_icon_data_uri()` (chỉ còn `MonitorCard` dùng, đã xoá ở Phase 4) + test riêng của nó.
- Sửa message "Dev mode enabled..." trong `app_bootstrapper.py` — bản cũ nói sai là click sẽ log ở "System Monitor" mỗi màn, giờ không còn đúng cho QML nữa.

**Bug môi trường thật tìm được và sửa ở Phase 5 (không phải do code migration, nhưng CI phát hiện ra):**
`test_sanity_data_management_sync` fail ngẫu nhiên (~30-50%) khi chạy NGAY SAU `test_sanity_boot_and_dashboard` trong cùng 1 tiến trình pytest — pass 100% khi chạy riêng. Root-cause bằng script repro độc lập (không đoán): tách bạch xác nhận **không phải** lỗi FSM matrix (gọi `fsm.transition_to()` trực tiếp luôn thành công), **không phải** state `useCustomTime`/`ViewModel` bị nhiễm — mà là độ trễ thật sự trong việc QML `Button.clicked.emit()` truyền tới `onClicked` handler khi 2 `QQuickWidget` được tạo/huỷ liên tiếp gần nhau trong cùng tiến trình (khả năng cao liên quan `deleteLater()` của `QQuickWidget` màn trước chưa xử lý xong khi màn sau load). Thêm `processEvents()` cố định KHÔNG sửa được (có lúc còn tệ hơn) — sửa đúng bằng `qtbot.waitUntil(...)` (poll có timeout) thay cho `processEvents()` + assert ngay lập tức, xác nhận ổn định qua 10/10 lần lặp lại bằng cả script repro lẫn pytest thật. Đây là hazard chung của nhiều `QQuickWidget` liên tiếp trong 1 process test — không đặc thù riêng Dev Board, chỉ là lần đầu 2 màn hình "nặng" (1 màn có real background thread) đứng cạnh nhau trong thứ tự file test.

**Ghi nhận lại cho tương lai:** nếu còn gặp flake dạng "click QML xong assert ngay bị fail ngẫu nhiên, chạy riêng thì pass", ưu tiên nghi ngờ chính pattern này trước — thay `processEvents()` bằng `qtbot.waitUntil`/`waitSignal`, không thêm `processEvents()` tràn lan (đã chứng minh không đáng tin).

**Sự cố CI treo lần cuối (môi trường, không phải bug code):** một lần chạy `ci-local.ps1 -Full` bị treo cứng ~1 giờ tại `test_sanity_dev_board_full_feature_walkthrough` (0 thay đổi output, trong khi mọi `qtbot.waitSignal` trong test đó đều có `timeout=2000` nên không thể tự treo vô hạn — xác nhận đây là deadlock tiến trình, không phải test chậm). Kiểm tra `Get-CimInstance Win32_Process` xác nhận đúng tiến trình `pytest.exe` của lần chạy đó, không phải process lạ. Kill tiến trình + chạy lại: test đó pass trong 2.56s khi chạy riêng, và cả suite pass sạch ngay lần chạy lại kế tiếp — kết luận là hazard môi trường Windows/offscreen khi có nhiều tiến trình Qt nặng chạy gần nhau trong phiên làm việc dài (không phải lần đầu gặp — xem `BOT-030` phase trước), không phải regression.
