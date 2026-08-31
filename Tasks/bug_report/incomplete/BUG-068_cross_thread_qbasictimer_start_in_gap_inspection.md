# BUG-068 — QBasicTimer::start: Timers cannot be started from another thread trong quá trình kiểm tra Database Gaps

**Reported date:** 2026-08-30  
**Severity:** 🟠 **P2**  
**Status:** 🔴 Open — đã điều tra 2026-08-31, root cause **chưa xác nhận được**: tái hiện sống
thật (app boot thật, DB seed gap thật, không mock) trên `offscreen` cho **0 cảnh báo**, nghi
thuộc lớp lỗi chỉ tồn tại trên nền tảng có cửa sổ thật (xem §3). Cần tái hiện trên Windows thật
để đi tiếp — không đoán fix khi chưa xác nhận được cơ chế.

---

## 1. Hiện tượng (Symptom)

Khi kích hoạt tính năng kiểm tra khoảng trống dữ liệu (Inspect Gaps) trên màn hình Data Management / Storage Vault, log ghi nhận 4 cảnh báo vi phạm Qt thread affinity:

```text
2026-08-30 17:33:14,602 - App - INFO - Executing query: GetDatabaseGapsQuery
QBasicTimer::start: Timers cannot be started from another thread
QBasicTimer::start: Timers cannot be started from another thread
QBasicTimer::start: Timers cannot be started from another thread
QBasicTimer::start: Timers cannot be started from another thread
```

## 2. Ghi nhận sơ bộ (Initial Observation)

- Lỗi xảy ra ngay sau khi `GetDatabaseGapsQuery` bắt đầu thực thi trên luồng nền của `ThreadManager`.
- Trong Qt/PySide6, `QTimer` và `QBasicTimer` có thread affinity gắn chặt với thread tạo ra nó. Nếu một phương thức chạy trên worker thread cố gắng gọi `start()` một timer (hoặc kích hoạt animation / transition có timer ngầm của Qt Quick / QtWidgets), Qt sẽ từ chối và in cảnh báo `Timers cannot be started from another thread`.
- Đây là biến thể của lớp lỗi `BUG-031` (từng làm đóng băng UI hoặc crash event loop).

## 3. Điều tra 2026-08-31 — không tái hiện được từ môi trường hiện có

**Đã loại trừ, bằng đọc code + tái hiện sống thật** (boot app thật qua `create_app()`,
container/DI thật, `ThreadManager` thật (không mock), DB seed 2 dải nến lệch nhau để
`GetDatabaseGapsQuery` tìm ra gap thật, `DataManagementView`/`DataManagementPresenter` thật,
bắt mọi message Qt bằng `qInstallMessageHandler` — không phải suy đoán tĩnh):

- **`GetDatabaseGapsQueryHandler`** (`get_database_gaps/handler.py`): thuần Python + SQLAlchemy,
  không chạm Qt object nào — không phải nguồn.
- **`Dispatcher.dispatch()`** (engine, `kernel/dispatcher.py`): chỉ gọi `logger.info(...)`, không
  có `QTimer`/`QMetaObject`.
- **`SignalLogHandler`** (`signal_log_handler.py`, gắn vào logger `"App"` — mọi `logger.info()`
  trong toàn app, kể cả dòng "Executing query" chạy trên worker thread của `GapCoordinator`, đều
  đi qua `emit()` → `self.signal.emit(text)`): đây LÀ signal cross-thread, nhưng cùng đúng pattern
  `SyncMarketDataCommand`/`SyncProgressFeed` toàn app đang dùng ở khắp nơi khác không hề gây ra
  cảnh báo này — loại trừ vì không đặc thù riêng cho Inspect Gaps.
- **`ui_gap_inspector_signal`** (`Signal(object)` thật trên `DataManagementPresenter`, nối
  `Auto/QueuedConnection` mặc định tới `_on_gap_inspector_payload` → `set_gap_inspector_data()` →
  `openGapInspectorRequested.emit()` → `GapInspectorDialog` mở lần đầu qua `_open_gap_inspector()`
  bên `data_management_view.py`): tái hiện sống đủ toàn bộ đường này (DB rỗng lẫn DB có gap thật,
  dialog mở, `DatabaseStatusTable`/`DatabaseStatusRow`/`ProgressBanner`/`GapInspectorDialog` render
  đầy đủ) — **0 cảnh báo `QBasicTimer` nào xuất hiện**, kể cả khi ép
  `QSG_RENDER_LOOP=threaded`.

**Giả thuyết mạnh nhất còn lại, chưa xác nhận được:** Qt Quick trên nền tảng có cửa sổ thật
(`windows`/`xcb`, đúng môi trường user gửi log — `Qt platform=windows` trong log gốc) mặc định
dùng **threaded render loop** (một `QThread` render riêng đồng bộ scenegraph với GUI thread) —
đây là cơ chế Qt tự quản lý bên trong `QQuickWidget`, không phải code app này gọi trực tiếp.
Nền tảng `offscreen` (bắt buộc cho mọi test/tái hiện tự động trong repo này) không có compositor
thật nên rơi về **basic (single-thread) render loop** — `QSG_RENDER_LOOP=threaded` không ép được
gì trên `offscreen` (đã thử, không đổi hành vi). Nếu đúng, cảnh báo này thuộc lớp lỗi **chỉ tồn
tại trên nền tảng thật**, giống hệt khoảng trống môi trường mà `BUG-016`/Desktop E2E tier của
repo này đã ghi nhận trước đó — không phải bug này bị bỏ qua, mà là loại bug tầng Sanity/offscreen
**không có khả năng nhìn thấy được**, đúng lý do tầng Desktop E2E tồn tại.

## 4. Suggested next steps

1. **Tái hiện lại trên máy Windows thật** (không phải `offscreen`) — chỉ ở đó threaded render
   loop mới chạy thật. Khi tái hiện được, bật `QT_LOGGING_RULES="qt.qml.*=true"` hoặc gắn debugger
   ngay lúc cảnh báo in ra để bắt call stack C++ thật — `qInstallMessageHandler` tự nó không kèm
   stack trace, chỉ có `context.file`/`context.line` (thường trỏ vào file nguồn Qt, không phải
   code app).
2. Nếu tái hiện lại được ở Windows: thử tắt threaded render loop có chủ đích
   (`QSG_RENDER_LOOP=basic` set trước khi `QApplication` khởi tạo) — nếu cảnh báo biến mất, xác
   nhận đúng giả thuyết §3, và hướng sửa sẽ là quyết định có chấp nhận đổi render loop toàn app
   hay không (đánh đổi hiệu năng chart/QML khác), không phải sửa 1 chỗ code cụ thể.
3. Việc điều tra 2026-08-31 (script tái hiện, kết quả, giả thuyết) không đưa vào test tự động
   được vì không tái hiện được trên `offscreen` — không có gì để viết assertion "phải thấy cảnh
   báo X" khi biết chắc offscreen sẽ không bao giờ tạo ra nó.
