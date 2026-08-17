# Hoàn thành: BOT-097 — Backtest: Chọn múi giờ hiển thị (UTC vs Giờ hệ thống)

**Trạng thái:** ✅ Hoàn thành
**Ngày hoàn thành:** 2026-08-17
**Loại tác vụ:** Backtest Screen / UX & Presentation Time Formatting
**Độ phức tạp:** 🟢 S (Fast Agent)

---

## 1. Vấn đề giải quyết

Dữ liệu Binance và Backtest engine luôn dùng UTC tuyệt đối để bảo toàn tính toàn vẹn dữ liệu `[start, end)` và nến lịch sử. Tuy nhiên, người dùng Việt Nam khi quan sát biểu đồ, tooltip, và bảng Trade Logs cần đọc thời gian theo giờ địa phương (GMT+7) một cách trực quan mà không phải tự nhẩm quy đổi.

`BOT-097` giải quyết vấn đề này ở tầng **Presentation Layer** (Display Concern):
1. Không thay đổi dữ liệu UTC trong DB, cache, use case hay engine PnL.
2. Thêm selector múi giờ trên toolbar Backtest (`UTC`, `Giờ hệ thống`, `Asia/Ho_Chi_Minh`,...).
3. Đồng bộ chuyển đổi múi giờ tức thì trên trục biểu đồ (`DateAxisItem.utcOffset`), tooltip crosshair, và bảng Trade Logs entry/exit.
4. Đổi múi giờ chỉ re-render presentation, không làm dirty `BacktestRunConfig`, không kích hoạt chạy lại backtest hay dispatch query ngầm.

---

## 2. Các thay đổi đã thực hiện

1. **`src/presentation/ui/services/display_timezone_service.py`**:
   - Service xử lý chuyển đổi và định dạng múi giờ dựa trên `zoneinfo.ZoneInfo` chuẩn của Python.
   - Hỗ trợ `UTC`, `SYSTEM` (tự động nhận diện múi giờ hệ điều hành), và các IANA zone chuẩn (`Asia/Ho_Chi_Minh`, `Asia/Tokyo`, `Europe/London`, `America/New_York`).
   - Xử lý đúng Daylight Saving Time (DST) và fallback an toàn về `UTC` nếu zone không hợp lệ.
   - Hàm `get_utc_offset_seconds()` tính toán offset theo giây cho `DateAxisItem`.

2. **`src/presentation/ui/components/TimezonePickerModal.qml`**:
   - Modal chọn múi giờ hiển thị kế thừa `ModalDialogCard.qml`, hiển thị danh sách trực quan có dấu tick đánh dấu múi giờ hiện hành.

3. **`src/presentation/ui/screens/backtest/BackTestTopPanel.qml` & `BackTestModals.qml`**:
   - Thêm nút `btnTimezone` (`objectName: "btnBacktestTimezone"`) trên toolbar Backtest cạnh TimeRange button.
   - Tích hợp `TimezonePickerModal` vào `BackTestModals.qml` kết nối với overlay host.

4. **`src/presentation/ui/screens/backtest/backtest_view_model.py`**:
   - Khai báo properties `displayTimezone`, `displayTimezoneLabel`, `displayTimezoneOptions`.
   - Signals `displayTimezoneChanged`, `openTimezonePickerRequested`.
   - Slots `@Slot() requestOpenTimezonePicker()` và `@Slot(str) setDisplayTimezone()`.

5. **`src/presentation/ui/screens/backtest/backtest_view.py` & `backtest_presenter.py`**:
   - `BackTestPresenter` lắng nghe `displayTimezoneChanged`: cập nhật `view.set_display_timezone(tz_name)` và làm mới bảng `_refresh_trade_log()`.
   - `BackTestView` chuyển tiếp múi giờ tới toàn bộ `ChartCard`s.
   - Loại bỏ local import trong `backtest_view.py` theo quy tắc PEP 8.

6. **`src/presentation/ui/components/chart_card/`**:
   - `CrosshairController`: định dạng timestamp crosshair label và OHLC theo `display_timezone`.
   - `ChartPlotLayout`: cập nhật `utcOffset` cho toàn bộ các `DateAxisItem` của main plot và sub plots.
   - `ChartCard`: expose `set_display_timezone(tz_name)`.

---

## 3. Bộ kiểm thử 4 tầng (Test Pyramid Verification)

1. **Tầng 1 — Static Quality (Lint & Format)**:
   - `ruff check src tests`: ✅ 0 lỗi.
   - `ruff format --check src tests`: ✅ 331 files clean.

2. **Tầng 2 — Unit Tests (`tests/unit/`)**:
   - [`tests/unit/presentation/ui/services/test_display_timezone_service.py`](file:///c:/Users/hoang/Documents/Sagittarius-Elite-Warrior/tests/unit/presentation/ui/services/test_display_timezone_service.py): 10 unit tests kiểm thử độ chính xác UTC, naive fallback, Asia/Ho_Chi_Minh (+7h), DST America/New_York (EDT vs EST), offset seconds, và danh sách supported timezones.
   - [`tests/unit/presentation/ui/screens/test_trade_log_row.py`](file:///c:/Users/hoang/Documents/Sagittarius-Elite-Warrior/tests/unit/presentation/ui/screens/test_trade_log_row.py): 15 unit tests kiểm thử chuyển đổi định dạng Trade Logs rows sang các múi giờ khác nhau.
   - [`tests/unit/presentation/ui/screens/test_backtest_timezone_presenter.py`](file:///c:/Users/hoang/Documents/Sagittarius-Elite-Warrior/tests/unit/presentation/ui/screens/test_backtest_timezone_presenter.py): 2 unit tests xác thực ViewModel signals/properties, và xác nhận thay đổi timezone KHÔNG dirty config, KHÔNG trigger dispatch/FSM.

3. **Tầng 3 — Application & Integration Tests (`tests/integration/`)**:
   - [`tests/integration/presentation/test_backtest_timezone_integration.py`](file:///c:/Users/hoang/Documents/Sagittarius-Elite-Warrior/tests/integration/presentation/test_backtest_timezone_integration.py): Kiểm thử tích hợp toàn diện luồng thay đổi timezone qua Presenter và View, xác nhận giờ Trade Logs cập nhật chính xác giữa UTC ↔ Asia/Ho_Chi_Minh ↔ America/New_York, trong khi dữ liệu domain `Trade.entry_time` vẫn bảo toàn UTC bất biến 100%.

4. **Tầng 4 — Sanity Tests (`tests/sanity/`)**:
   - [`tests/sanity/test_backtest_screen_ui_sanity.py`](file:///c:/Users/hoang/Documents/Sagittarius-Elite-Warrior/tests/sanity/test_backtest_screen_ui_sanity.py): Xác thực khởi tạo View + Presenter với DI container thật và QML parse sạch sẽ 0 lỗi cho toàn bộ toolbar + popup modals mới.
   - [`tests/sanity/test_view_model_thread_affinity_sanity.py`](file:///c:/Users/hoang/Documents/Sagittarius-Elite-Warrior/tests/sanity/test_view_model_thread_affinity_sanity.py): Bảo đảm mọi mutator trên ViewModel đều được bảo vệ bởi `@Slot` tránh race conditions đa luồng.
