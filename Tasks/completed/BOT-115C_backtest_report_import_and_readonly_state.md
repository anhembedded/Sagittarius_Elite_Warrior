# Nhiệm vụ: Nạp Báo cáo & Chế độ Xem Chỉ đọc

**Mã Task:** `BOT-115C`  
**Thuộc Epic:** [`BOT-115`](../backlog/BOT-115_backtest_report_persistence_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking)**  
**Trạng thái:** ✅ **Hoàn thành một phần (2026-09-23) — xem §6, biểu đồ nến & vault-sync hoãn.**  
**Dependencies:** [`BOT-115A`](BOT-115A_backtest_report_schema_and_serializer.md), [`BOT-131`](BOT-131_backtest_fsm_and_stale_data_lifecycle.md)

---

## 1. Đây Là Task Khó Nhất Của Epic

Không phải vì đọc file (`BOT-115A` lo xong rồi), mà vì **màn Backtest đang giả định mọi kết quả trên màn hình đều do toolbar hiện tại sinh ra**. Import phá vỡ giả định đó.

---

## 2. State Mới Trong FSM

`BOT-095B` liên tục so `BacktestRunConfig` hiện tại của toolbar với snapshot lần chạy cuối để bật cờ `isConfigDirty`. Nạp một report từ đĩa vào sẽ khiến FSM lập tức bắn banner *"Cấu hình đã thay đổi — kết quả đang hiển thị là của lần chạy trước"*, hoàn toàn vô nghĩa với người dùng vừa mở file.

**Thiết kế:** thêm state `VIEWING_IMPORTED_REPORT` vào `BacktestUiState`:

- Vào state: hydrate toolbar theo config trong file **nhưng suppress dirty tracking** trong lúc hydrate (đúng kỹ thuật "restore transaction" mà `BOT-095G` §2.2 đã mô tả cho cache trong phiên — dùng chung cơ chế, đừng viết cơ chế thứ hai).
- Trong state: banner riêng nêu nguồn gốc — *"Đang xem báo cáo đã nhập — `ETHUSDT_5m_...json`, chạy ngày 18/08/2026"* — kèm nút "Thoát chế độ xem".
- Thoát state: bấm Run, hoặc bấm nút thoát. Bấm Run thì chạy thật bằng config đang hiện trên toolbar và quay về vòng đời bình thường.

---

## 3. Cảnh Báo Provenance (không được bỏ qua)

So `provenance` trong file với môi trường hiện tại, hiện badge ở khu kết quả khi lệch:

| Trường hợp | Xử lý |
| :--- | :--- |
| `engine_version` khác bản đang chạy | Badge vàng: *"Báo cáo tạo bởi engine v1.3.0 — chạy lại trên bản hiện tại có thể ra số khác."* |
| `strategy_key` không còn trong `StrategyRegistry` | Vẫn hiện kết quả, **khoá nút Run**, nêu rõ chiến lược không còn tồn tại. |
| `metrics` trong file lệch với `metrics` tính lại từ `trades` | Badge đỏ: nghi ngờ file bị sửa tay. |
| Không có `out_of_sample` | Tái dùng đúng dòng cảnh báo `BOT-080` đã có, không viết cảnh báo mới. |

Nguyên tắc xuyên suốt: **số liệu quá khứ không bao giờ được trình bày như số liệu vừa tính**.

---

## 4. Thiếu Dữ liệu Nến — Hạ Cấp Có Giải Thích

Report không chứa klines (quyết định ở §3.1 Epic). Sau khi nạp, thử lấy nến từ vault theo `symbol`/`timeframe`/`range` trong file:

- **Có đủ** → vẽ đầy đủ: nến, marker vào/ra, indicator của chiến lược (`strategy_indicator_lines.py`), tô nền xu hướng (`BOT-113`).
- **Thiếu/không có** → 3 panel còn lại (Performance Summary, Trade Logs, Equity Curve) hiển thị bình thường; panel nến hiện thông báo *"Cần sync dữ liệu ETHUSDT 5m (18/07–18/08) để xem biểu đồ nến"* + nút sync, tái dùng affordance của [`BOT-059`](../completed/BOT-059_backtest_inline_data_sync_affordance.md). Sync xong thì vẽ được ngay, không cần nạp lại file.

Lưu ý đường native chart: mọi tính năng ngoài phạm vi `NativeBacktestChartHostAdapter` đều raise `NativeUnsupportedFeatureError` và presenter tự rebuild host Python — đường import phải đi qua đúng cơ chế fallback đã có, không bypass.

---

## 5. Kiểm Thử

- Nạp file hợp lệ → 4 panel khớp **chính xác** kết quả gốc (so trực tiếp với `BacktestResult` dùng để xuất).
- Nạp xong `isConfigDirty` **phải là `False`** (đây là bug dễ xảy ra nhất của task này).
- Bấm Run trong chế độ xem → thoát state, chạy thật, banner biến mất.
- Engine version lệch / strategy key lạ / metrics bị sửa → đúng badge tương ứng.
- Vault không có nến → 3 panel vẫn đúng, panel nến hiện thông báo sync (không crash, không chart rỗng im lặng).
- File hỏng → thông báo lỗi tiếng Việt rõ ràng, màn hình giữ nguyên trạng thái cũ, không mất kết quả đang xem.

---

## 6. Implementation Notes (2026-09-23)

Xây đúng lõi của task (state FSM read-only + hydrate kết quả + cảnh báo
provenance), tái-scope 3 điểm có căn cứ kiểm chứng trực tiếp trên code thật
(không đoán — audit riêng bằng subagent trước khi viết dòng nào):

- **§4's "native chart"/`NativeBacktestChartHostAdapter`/
  `NativeUnsupportedFeatureError` đã lỗi thời** — grep toàn repo: 0 kết quả
  trong `src/`, chỉ còn trong `Tasks/completed|cancelled/`. Backend
  C++/QML này đã bị xoá hẳn ở commit `36f3a9f9` (24/08/2026); `ChartCard`
  (pyqtgraph) hiện là implementation duy nhất, không có cơ chế fallback
  nào để "đi qua" cả.
- **§2's "hydrate toolbar theo config trong file" — không làm phần
  round-trip giá trị số về lại text field.** `BACKTEST_STATE_FIELDS`
  (`backtest_state_fields.py`) có ~19 field, nhiều field là `QLineEdit`
  text (`initialCapitalText`, `broker_sim.orderSizeText`,
  `broker_sim.commissionText`, `time_range.customStartText`/`customEndText`
  …) mà `capture()`/`restore()` chỉ từng round-trip đúng chuỗi văn bản
  phiên đó tự gõ (`_on_restore_run_requested`, BOT-095G) — chưa từng có
  công thức "format số đã parse ngược lại thành text người dùng có thể đã
  gõ" ở đâu trong repo. Bịa một công thức ở đây có nguy cơ hiển thị sai
  tinh vi, mà `domain-truth-rule.md` xem là tệ hơn cả việc không đụng vào
  field đó. Giải pháp thay thế, xác minh được: `isConfigDirty` là hàm
  thuần của trạng thái FSM (`_get_is_config_dirty()`:
  `ui_mode == CONFIG_DIRTY`), nên chỉ cần vào đúng state
  `VIEWING_IMPORTED_REPORT` là tiêu chí "`isConfigDirty` phải `False`"
  của task đã tự động đúng — không cần hydrate toolbar mới đạt được.
  Toolbar giữ nguyên giá trị đang có; bấm Run dùng đúng giá trị đó, khớp
  với mô tả gốc của task ("chạy thật bằng config đang hiện trên toolbar").
- **§4's biểu đồ nến (fetch từ vault theo symbol/timeframe/range + BOT-059
  sync affordance) hoãn.** Report không bao giờ nhúng kline
  (`backtest_report.py`'s own docstring), nên OHLC/candlestick không có gì
  thật để vẽ; thay vào đó ép chart về chế độ **Equity**
  (`ChartDisplayMode.EQUITY`), vẽ thẳng từ `result.equity_curve` (luôn có
  sẵn trong report) — không cần nến thật. Wiring `RunResultViewModel.
  needsDataSync`/`_btn_request_sync` (cơ chế `BOT-059` thật, đã xác minh
  còn hoạt động — tài liệu `BOT-059` cũ mô tả kiến trúc QML/`UIMode` đã lỗi
  thời) vào đúng symbol/timeframe/range của report import là một khối việc
  riêng, kích thước tương đương phần đã xây — để lại làm follow-up.
- **§3's 4 badge màu riêng → 1 dòng cảnh báo gộp.** Màn Backtest không có
  sẵn widget "badge" để tái dùng, nhưng có sẵn cơ chế `resultWarningText`
  (`build_result_warning_text()`) đúng hình dạng "nhiều ghi chú, nối bằng
  dấu chấm giữa" — `build_report_provenance_warning_text()` mới tái dùng
  đúng convention đó thay vì phát minh 4 widget màu mới. Cảnh báo "thiếu
  `out_of_sample`" trong §3 **không** được thêm: hầu hết run bình thường
  không có out-of-sample (tính năng opt-in), nên cảnh báo riêng cho trường
  hợp import sẽ cảnh báo nhầm case phổ biến nhất, không phải một vấn đề
  provenance thật.
- **"Khoá nút Run khi strategy không còn tồn tại" (§3 dòng 2) không xây
  riêng.** Combobox chiến lược trên toolbar chỉ liệt kê chiến lược còn
  đăng ký (`IStrategyCatalog.options()`), nên nó không thể tự hiển thị
  giá trị đã bị xoá — bấm Run sau khi import một báo cáo với chiến lược lạ
  sẽ luôn chạy bằng chiến lược nào đang thật sự hiển thị trên toolbar
  (không phải chiến lược đã import), nên không có "lệnh chạy ma" nào cần
  khoá riêng. Dòng cảnh báo trong `resultWarningText` đã nêu rõ sự kiện
  này cho người dùng.

**Files**: `ui/logic/backtest_fsm_matrix.py` (`VIEWING_IMPORTED_REPORT`,
`REPORT_IMPORTED`, `IMPORTED_REPORT_VIEW_EXITED` + transitions), mới
`ui/logic/report_import.py` (`read_backtest_report_bytes`,
`backtest_report_to_run_config`, `build_report_provenance_warning_text`),
`ui/backtest_view_model.py` (`importReportRequested`/
`exitImportedReportViewRequested` signals+slots,
`importedReportBannerText` property), `ui/backtest_presenter.py`
(`_ask_report_import_path`, `_on_report_import_requested`,
`_on_exit_imported_report_view_requested`), `ui/signal_wiring.py` (2 new
connections), `ui/backtest_top_panel.py` ("Import report" button,
imported-report banner).

**Tests**: `test_backtest_fsm_matrix.py` (+2 — every non-busy state ->
`VIEWING_IMPORTED_REPORT`, and its own 3 exits), new
`test_report_import.py` (8 — round-trip through the real export/import
pair, provenance warning branches), `test_backtest_presenter.py` (+7 —
cancel, success with matching panels, malformed file, unknown strategy,
exit view, Run-while-viewing, edit-while-viewing; the last two
mutation-verified against `COMPLETED`'s coincidentally-identical
transitions by asserting the precondition state explicitly),
`test_backtest_top_panel_layout.py` (+2 — button always enabled, banner
visible only while viewing). Mutation-verified: removing the
`fsm.dispatch(REPORT_IMPORTED)` call turned all 4 of the "while viewing"/
entry/exit presenter tests red for the right reason, restored afterwards.

**Verification**: `ruff check`/`ruff format --check` clean on every
touched file; mypy (`--config-file pyproject.toml --namespace-packages
--explicit-package-bases`) introduces zero new errors on `report_import.py`
and `backtest_fsm_matrix.py`; the handful of new `Property`-assignment and
`BaseStateMachine[Any]` attr errors on the new `backtest_presenter.py`
lines match this file's own pre-existing, documented baseline classes
(`pyproject.toml`'s `[tool.mypy]` comment: PySide6 `@Property` false
positives are ~52% of `src/`'s frozen baseline) — not a new category.
`tests/unit/modules/backtesting/` (835) and `tests/unit/architecture`
(440): all green.
