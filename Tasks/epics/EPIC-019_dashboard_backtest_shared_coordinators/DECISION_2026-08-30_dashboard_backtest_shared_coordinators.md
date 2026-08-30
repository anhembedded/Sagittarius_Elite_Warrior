# ADR — Dashboard/Backtest: gộp logic Presenter trùng lặp thành Coordinator dùng chung

**Thuộc Epic:** [`EPIC-019`](README.md)
**Ngày:** 2026-08-30
**Trạng thái:** 🟢 **Approved** — 2 finding verify chắc, quyết theo phương
châm "best design/pattern đã kiểm chứng, tham chiếu dự án lớn khi phân vân"
(`architecture-rule.md`, callout đầu file, user chốt 2026-08-30).

---

## 1. Bối cảnh

Một báo cáo ngoài (Gemini) nhận định `presentation/ui/screens/` bị *Shotgun
Surgery*: nhiều màn hình có tính năng chung nhưng không có lớp cha/chỗ dùng
chung để cài chúng, nên thêm 1 tính năng nhỏ phải sửa nhiều file. Báo cáo đó
**không được tin theo** — đã verify độc lập từng claim bằng cách đọc code
thật (đúng phương pháp `EPIC-017`/`EPIC-018` đã dùng). Kết quả: một số claim
**đúng**, một số **bịa** (file không tồn tại, tính năng không tồn tại).

## 2. Bảng verify (tóm tắt)

| # | Claim | Verdict | Ghi chú |
| :-: | :--- | :--- | :--- |
| 1 | `DashboardPresenter`/`BackTestPresenter` trùng lặp gần 100% 4 method fetch/cache symbol options | ✅ **Đúng** | `dashboard_presenter.py:599-630` vs `backtest_presenter.py:1378-1409` — cùng tên method, cùng cấu trúc, chỉ khác dòng emit log cuối |
| 2 | `_trigger_initial_health_check`/`_on_health_report`/`HealthFeed` wiring trùng lặp 2 Presenter | ✅ **Đúng** | `dashboard_presenter.py:781-796` vs `backtest_presenter.py:572-583` — chính comment trong `dashboard_presenter.py:777-780` đã tự thừa nhận "Backtest cũng vậy" |
| 3 | `DashboardSymbolPickerSource` (56 dòng) trùng gần 100% với `BacktestSymbolPickerSource` (73 dòng) | ❌ **Bịa** | Grep toàn repo: `DashboardSymbolPickerSource` **không tồn tại**. Dashboard/Data Management vẫn dùng `SymbolPickerOverlay` (QtWidgets) chung — cố ý, đã ghi rõ trong `backtest_modals/symbol_picker_dialog.py:3`: "Data Management and Dev Board keep `SymbolPickerOverlay` for now — deliberate staged rollout" |
| 4 | Nút "Refresh Symbol" tạo chuỗi lan truyền 14 mắt xích, dùng `force_refresh=True` | ❌ **Bịa** | Grep `force_refresh`/`refresh_requested` trong cả 2 Presenter: 0 kết quả. Tính năng này không tồn tại trong code hiện tại |
| 5 | Dashboard dùng `QComboBox` tự chế cho Timeframe, không có control dùng chung | ❌ **Sai** | Dashboard đã dùng `ChartToolbar`/`TimeframeToolbar` dùng chung (`EPIC-015` Phase 4, đã xong) — cùng cơ chế Backtest dùng |
| 6 | Data Management dùng `TimeRangeCard` riêng, Settings dùng `SettingsViewIntervalPicker` riêng cho Timeframe | ❌ **Sai** | Cả 2 file import thẳng `TimeframePicker`/`TimeframeToolbar` dùng chung (`EPIC-014`, đã xong) |
| 7 | `BaseQmlViewModel` không cung cấp gì cho boilerplate Property, mỗi ViewModel tự tay viết getter/setter/`Property()` | ✅ **Đúng** (tự phát hiện, độc lập với báo cáo Gemini) | 133 method `_get_*`/`_set_*` trên toàn `screens/`; `BaseQmlViewModel` (engine, `pyside_mvc/runtime/base_view_model.py`) chỉ có `uiMode`/`controlsEnabled`, không có factory nào cho property khác |

**Kết luận về báo cáo Gemini:** 2/7 claim đúng, đáng làm; 4/7 claim sai hoặc
bịa (không có bằng chứng trong code thật); 1 claim đúng nhưng do agent tự
tìm ra trước, không phải nhờ báo cáo. Không dùng báo cáo này làm nguồn cho
quyết định — chỉ 2 finding đã verify độc lập (#1, #2) và 1 finding tự phát
hiện (#7) mới được đưa vào epic này.

## 3. Quyết định từng điểm

### D1 — `SymbolOptionsCoordinator` dùng chung cho Dashboard + Backtest 🔵 Proposed → `EPIC-019A`

Tách 4 method trùng lặp (`_on_symbol_picker_open_requested`,
`_fetch_symbol_options`, `_on_symbol_options_ready`,
`_on_symbol_options_failed`) + field `_symbol_options_cache` thành một
Coordinator dùng chung.

**Vì sao Coordinator, không phải base class Presenter mới** (đúng phương
châm "tham chiếu dự án lớn/pattern đã kiểm chứng" — không tự sáng chế): repo
này đã tự chứng minh hướng "base Presenter dày" (`God Presenter`) là sai —
`EPIC-003`/`EPIC-013` tồn tại chính vì lý do đó, và quyết định đã ghi thành
luật (`architecture-rule.md`): composition qua Coordinator tiêm vào
`__init__`, không kế thừa sâu. `ActionOwnershipTracker`, `HealthFeed`,
`IndicatorCoordinator` (`EPIC-003G`) đều đã theo đúng hình dạng này. Coordinator
pattern (tách logic dùng chung khỏi object điều phối, không đụng vào hợp
đồng Presenter↔View) là pattern có tên, có tiền lệ rộng (ASP.NET MVC
Controller/Service pattern, Android ViewModel+UseCase, chính codebase này
đã dùng 8+ lần) — đúng tinh thần "pattern được dùng ở dự án lớn" hơn là một
lớp trung gian tự chế.

**Hình dạng:** plain Python class (không `QObject`, đúng quy ước Coordinator
đã có), nhận `dispatcher`, `thread_manager`, `emit_ready: Callable[[list[str]], None]`,
`emit_failed: Callable[[str], None]` qua constructor — không giữ tham chiếu
Presenter/View. Expose `request_open()` (check cache, submit fetch) và
`_fetch()` (worker thread, dispatch `ListAvailableSymbolsQuery`). Cache
(`_symbol_options_cache`) chuyển vào Coordinator.

### D2 — `HealthCheckCoordinator` dùng chung cho Dashboard + Backtest 🔵 Proposed → `EPIC-019B`

Tách `_trigger_initial_health_check`, `_on_health_report`, và việc dựng
`HealthFeed`+connect thành Coordinator riêng, cùng lý do/hình dạng D1.
Điểm khác biệt duy nhất giữa 2 Presenter hiện tại (Dashboard gọi
`self.ui_log_signal.emit(...)`, Backtest gọi
`self._emit_ui_log(..., "info", is_dev=False)`) chuyển thành tham số
`emit_log: Callable[[str], None]` tiêm lúc khởi tạo — đúng cách
`ScanCoordinator`/`SyncCoordinator` (Data Management, `EPIC-003B`) đã nhận
`ui_log_signal.emit`/`ui_error_log_signal.emit` làm callback thay vì tự giữ
signal.

### D3 — Factory cho Qt `Property` boilerplate ở ViewModel 🔵 Proposed → `EPIC-019C`

133 method `_get_*`/_set_*` là con số lớn nhất trong 3 finding nhưng cũng
**rủi ro cao nhất** nếu đổi hàng loạt — nhiều property có validate/normalize
riêng (vd. `DataManagementViewModel.selectedSymbol` tự `.strip().upper()`,
`BackTestViewModel.selectedSymbol` thì không). Quyết định: viết một factory
function `notifying_property(get_current, set_current, signal, normalize=None)`
sống trong app này (không sửa `BaseQmlViewModel` của engine — 2 repo độc
lập, sửa engine là quyết định khác, không nằm trong epic này), áp dụng
**thử nghiệm trên 1 ViewModel trước** (`DataManagementViewModel` — nhiều
property nhất, nhiều cơ hội đo lợi ích nhất) trước khi lan ra 3 ViewModel
còn lại — tránh đúng bẫy "đổi 133 chỗ cùng lúc, hỏng thì hỏng cả 4 màn".

## 4. Hệ quả

**Được:** 2 cặp method + field trùng lặp thật (D1, D2) biến mất khỏi 2
Presenter, thay bằng 1 Coordinator dùng chung mỗi loại — đúng pattern
Coordinator đã có tiền lệ trong chính repo. `Property` boilerplate (D3)
giảm dần theo từng ViewModel áp dụng, bắt đầu từ nơi đo được lợi ích rõ nhất.

**Không làm theo đề xuất của Gemini:** không tạo `TradingScreenPresenter`/
`TradingScreenViewModel` base class mới (đi ngược hướng composition đã
chọn), không tạo `SymbolCatalogService` ôm thẳng `ICommandDispatcher` (phá
ranh giới FSM/action-ownership phải ở Presenter — luật đã chốt từ `EPIC-003`),
không sửa gì liên quan tới nút "Refresh Symbol" hay 3 claim sai khác — tính
năng/file đó không tồn tại.

## 5. Tham chiếu

- `src/presentation/ui/screens/dashboard/dashboard_presenter.py`
- `src/presentation/ui/screens/backtest/backtest_presenter.py`
- `src/presentation/ui/screens/data_management/coordinators/scan_coordinator.py` — tiền lệ Coordinator nhận `emit_*` callback
- `src/presentation/ui/screens/dashboard/coordinators/indicator_coordinator.py` — tiền lệ Coordinator từ `EPIC-003G`
- `sagittarius_engine/extensions/pyside_mvc/runtime/base_view_model.py` — `BaseQmlViewModel`, không có factory Property
- [`EPIC-003`](../EPIC-003_presenter_and_god_file_decomposition/README.md), [`EPIC-013`](../EPIC-013_hop_dong_tuong_minh_va_tach_coordinator/README.md) — lý do chọn Coordinator thay vì base Presenter dày
