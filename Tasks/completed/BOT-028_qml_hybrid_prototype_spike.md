# Nhiệm vụ: QML Hybrid Prototype Spike — Settings Screen

## 1. Mục tiêu (Objective)
Kiểm chứng khả thi của việc chuyển UI sang **QML theo hướng Hybrid** (giữ nguyên `ChartCard`/pyqtgraph, phần còn lại chuyển sang QML nhúng qua `QQuickWidget`) — trước khi rút bất kỳ abstraction nào vào `sagittarius_engine/extensions/pyside_mvc` (shared, dùng chung nhiều app). Dùng Settings Screen (`BOT-017`, chưa triển khai) làm bãi thử: không chart, không realtime binding, rủi ro thấp.

## 2. Mô tả (Description)
Chia làm 4 phase, mỗi phase có test gate riêng, chỉ sang phase sau khi phase trước pass:
- **Phase 0**: Plumbing — `QQuickWidget` load QML placeholder, đăng ký route `"settings"` qua `PresenterManager` hiện có (không sửa `pyside_mvc`), coi có coexist được với Dashboard/DataManagement không, đặc biệt là có render được dưới `QT_QPA_PLATFORM=offscreen` (test headless hiện tại của repo) hay không.
- **Phase 1**: Form thật, one-way binding — `SettingsViewModel` expose `Property` đọc từ `IConfig.get_all()`, QML hiển thị (API Secret masked).
- **Phase 2**: Two-way binding — nút Save gọi `@Slot` validate + `IConfig.set()` (chỉ in-memory, xem mục Rủi ro).
- **Phase 3**: Regression toàn bộ (`ci-local.ps1 -Full`) + viết retro cho quyết định rút abstraction vào `pyside_mvc` sau này.

## 3. Các bước thực hiện (Action Items)
- [x] Phase 0: `settings_view.py` (`SettingsView` host `QQuickWidget`), `settings_presenter.py` (`SettingsPresenter(BasePresenter)`), `settings_screen.qml` placeholder.
- [x] Phase 0: Đăng ký route `"settings"` trong `main_window.py` (`_NAV_ROUTES` + `_setup_router`).
- [x] Phase 0: Sanity test mới trong `test_sanity_ui_e2e.py` — assert `view.quick_widget.status() == QQuickWidget.Status.Ready`.
- [x] Phase 0: Chạy tay (script offscreen tự viết chụp `window.grab()`) + xác nhận CLI headless (`main.py --help`) không bị ảnh hưởng.
- [x] Phase 1: `SettingsViewModel` (Property đọc từ `IConfig`), form QML thật, unit test `test_settings_view_model.py`.
- [x] Phase 2: `save()` slot (validate + `IConfig.set()`), unit test valid/invalid input, banner thông báo "cần khởi động lại" cho các field boot-time.
- [x] Phase 3: `ci-local.ps1 -Full` xanh, chuyển task này sang `Tasks/completed/`.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- **Không có persistence xuống `user_config.json`**: `IConfig.set()` hiện tại (`sagittarius_engine/infrastructure/config/config_manager.py`) chỉ ghi vào cache in-memory, không có đường ghi file nào trong engine. Đây là khoảng cách thật so với spec đầy đủ của `BOT-017` — cố tình để ngoài phạm vi spike này (sửa `IConfig` là thay đổi shared engine, cần quyết định riêng).
- **Không sửa `pyside_mvc`**: `PresenterManager.navigate_to()` chỉ yêu cầu `view` là `QWidget` — `QQuickWidget` thoả điều kiện này sẵn, không cần đổi router.
- **Không làm các màn hình backlog khác** (Watchlist, Notifications, Backtest UI) trong spike này.
- Điểm rủi ro kỹ thuật lớn nhất: chưa rõ `QQuickWidget` có render đúng dưới `QT_QPA_PLATFORM=offscreen` hay cần thêm `QT_QUICK_BACKEND=software` — Phase 0 đã trả lời bằng test thật.

## 5. Ghi chú hoàn thành (Completion Notes)

**Câu hỏi rủi ro lớn nhất đã được trả lời: `QQuickWidget` render đúng dưới `QT_QPA_PLATFORM=offscreen` ngay lập tức**, không cần `QT_QUICK_BACKEND=software` như lo ngại ban đầu. Xác nhận qua `test_sanity_settings_screen_qml_loads` (assert `quick_widget.status() == QQuickWidget.Status.Ready`) và qua screenshot thật (`window.grab()`) chạy trong môi trường offscreen — chữ hiển thị dạng ô vuông (tofu glyph) ở **cả 3 màn hình** kể cả Dashboard/DataManagement thuần Widgets vốn không đụng tới, xác nhận đây là giới hạn font-rendering có sẵn của môi trường offscreen, không phải lỗi do QML gây ra.

**`PresenterManager` (router trong `pyside_mvc`) không cần sửa gì cả** — đây là phát hiện quan trọng nhất của spike. `navigate_to()` chỉ gọi `stacked_widget.addWidget(view)`/`setCurrentIndex()`, và `QQuickWidget` (từ `PySide6.QtQuickWidgets`) tự nó là `QWidget` nên thoả điều kiện sẵn. Route `"settings"` được đăng ký y hệt cú pháp `"data_management"` đã có.

**Gotcha thứ tự đã lường trước và xử lý đúng:** `QQuickWidget.setSource()` phải được gọi **sau** khi `rootContext().setContextProperty("settingsVM", ...)` đã đăng ký xong — nếu không, QML sẽ resolve `settingsVM` thành undefined tại thời điểm parse. `SettingsView` tách `load_qml()` ra khỏi `__init__` chính vì lý do này; `SettingsPresenter` gọi `setContextProperty()` trước, `view.load_qml()` sau.

**Khoảng cách persistence đã xác nhận và giữ nguyên phạm vi:** `save()` chỉ gọi `IConfig.set()` (in-memory) — đã verify bằng cách chạy `save()` thật trên app đang chạy: `IConfig.get_all()` phản ánh giá trị mới ngay lập tức, nhưng `user_config.json` trên đĩa giữ nguyên (`"API_SECRET": ""`) suốt quá trình. Đây là gap thật của `IConfig` (không có method ghi file nào trong toàn bộ `sagittarius_engine`), không phải bug — cần 1 task riêng nếu muốn có persistence thật (mở rộng `IConfig` là thay đổi shared engine).

**Known gap được ghi nhận, không xử lý (đúng phạm vi):** `BaseView.enable_dev_click_logging()` (dev-mode click logging) dò `QPushButton` qua `findChildren` — không thấy được Button bên trong QML scene graph của `QQuickWidget`. Ghi rõ trong docstring `settings_view.py`; không phải regression vì tính năng này vốn opt-in qua `dev.mode` config, không ảnh hưởng hành vi mặc định.

**Đề xuất rút vào `pyside_mvc` (retro — CHƯA làm, để quyết định riêng sau):**
1. **Seam "defer `setSource` tới khi context property đã đăng ký"** — có thể đóng gói thành 1 `QmlHostWidget`/`BaseQmlView` chung, tránh mỗi screen QML mới phải tự nhớ đúng thứ tự.
2. Router **không cần thay đổi gì** — nghĩa là không có nhu cầu rút "QML router" riêng như dự tính ban đầu trong lúc bàn kiến trúc; giả thuyết ban đầu (Python-owns-state vs QML StackView-owns-state) coi như đã ngã ngũ nghiêng về "giữ nguyên Python-owns-state qua `PresenterManager`", vì nó vốn đã tương thích.
3. Pattern `Property` đọc từ `IConfig` + `@Slot` validate + `IConfig.set()` + `saveResult` signal trong `SettingsViewModel` **mới có đúng 1 lần dùng** — theo đúng tinh thần đã thống nhất (prototype trước, rút abstraction sau khi thấy lặp lại thật), **chưa nên** trừu tượng hoá thành base class ngay, chờ có màn hình QML thứ 2 (vd Watchlist/Notifications) mới đủ dữ liệu để thấy đâu là phần chung thật.

**File đã tạo:**
- `src/presentation/ui/screens/settings/{settings_view.py, settings_presenter.py, settings_view_model.py, settings_screen.qml}`
- `tests/unit/presentation/ui/screens/test_settings_view_model.py`

**File đã sửa:**
- `src/presentation/ui/main_window.py` (đăng ký route `"settings"`)
- `tests/integration/presentation/ui/test_sanity_ui_e2e.py` (thêm `test_sanity_settings_screen_qml_loads`)

Verify: `Sagittarius_Elite_Warrior/scripts/ci-local.ps1 -Full` — Ruff Lint ✅, Ruff Format ✅, Pytest ✅ (**218 passed, 2 xfailed** — 2 xfail thuộc `BOT-027`, có từ trước, không liên quan task này), coverage tổng **90.56%** (gate 80%), 3 file mới của Settings đều **100%** coverage.

---

## ⚠️ Cập nhật sau khi hoàn thành (superseded)

Trong lúc làm `BOT-029` (restyle UI), sau khi chạy app thật và trải nghiệm trực tiếp, người dùng nhận thấy màn hình QML (`QQuickWidget`) **có cảm giác chập/giật hơn rõ rệt** so với phần còn lại của UI (thuần QtWidgets) — dù các test tự động (kể cả `test_sanity_settings_screen_qml_loads`) đều pass, vì test chỉ xác nhận QML *render đúng*, không đo được cảm giác mượt/độ trễ tương tác thật. Quyết định: **bỏ QML, chuyển API & Credentials screen về lại QtWidgets thuần** (giữ nguyên thiết kế giao diện đen/gold của `BOT-029`).

Các file QML-specific đã bị xoá (`settings_view_model.py`, `settings_screen.qml`); `settings_view.py`/`settings_presenter.py` viết lại hoàn toàn theo đúng mô hình MVP mà `DataManagementPresenter`/`DataManagementView` đã dùng — không còn `QObject`/`Property`/`Slot` kiểu QML, chỉ còn `QLineEdit`/`QSpinBox`/`QPushButton` thường.

**Kết luận thật sự của epic Hybrid:** giả thuyết kỹ thuật (QQuickWidget coexist được với PresenterManager, không cần sửa `pyside_mvc`) **vẫn đúng** — nhưng trải nghiệm thực tế (độ mượt khi tương tác) không đạt yêu cầu so với QtWidgets thuần, nên hướng Hybrid **không được áp dụng cho bản thật**. Bài học cho tương lai: nếu cân nhắc QML lại, cần đánh giá độ mượt bằng cách tự tay dùng thử app thật (không chỉ dựa vào test tự động/screenshot), càng sớm càng tốt trong quá trình prototype — trước khi đầu tư thêm effort vào Phase tiếp theo.
