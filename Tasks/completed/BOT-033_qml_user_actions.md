# Nhiệm vụ: Hoàn thiện thao tác người dùng trên QML

## 1. Mục tiêu

Biến các control đang có trên QML từ UI tĩnh thành luồng thao tác có hiệu lực
và an toàn. Ưu tiên Developer Board vì đây là nơi các input hiện có thể tạo ra
kỳ vọng sai và còn có race condition đã được tái hiện.

## 2. Phạm vi đã chốt

### Phase 1 — an toàn thao tác bất đồng bộ ✅

- [x] Loại bỏ việc `Load History` chạy chồng nhau và xung đột với `Start Live`.
- [x] Mỗi worker nhận snapshot riêng của cấu hình và indicator; không đọc lại state
  mutable của Presenter khi đang chạy nền.
- [x] Hiển thị trạng thái đang tải, disable các action không hợp lệ, và khôi phục UI
  đúng sau thành công hoặc lỗi.
- [x] Test hồi quy cho `TC-ASY-01` và `TC-ASY-04`; `TC-ASY-02`/`TC-ASY-03`
  được chặn ở entry point và sẽ được mở rộng khi Phase 2 thay hard-code config.

### Phase 2 — cấu hình dữ liệu của Developer Board ✅

- [x] Nối `Symbol`, `Timeframe`, `Start date`, `End date` với ViewModel/Presenter.
- [x] Validate symbol, interval và date range trước khi dispatch; truyền các giá trị
  đã chốt vào query/load/start thay vì dùng hằng hard-code.
- [x] Định danh dữ liệu/chart theo `(symbol, interval)` để tick hoặc result cũ không
  bị trộn vào lựa chọn mới.
- [x] Nối Chart toolbar với cùng timeframe selection, không chỉ thay highlight.
  ✅ **Đã làm** (bởi 1 task khác chạy song song, số hiệu bị trùng nên đã đổi thành `BOT-034` —
  xem `Tasks/completed/BOT-034_dev_board_autostart_and_data_lifecycle.md` §6):
  `ChartToolbar.sig_timeframe_changed` đã nối vào `DashboardPresenter._on_timeframe_changed`,
  `cboTimeframe` (System Controls) đã bị xoá khỏi `DevBoardPanel.qml` để tránh 2 nguồn sự thật.
  Đổi timeframe reload ngay lập tức, kể cả khi đang Live (dừng → reload → start lại).

#### Đã build gì thực tế (Symbol / Start date / End date)

- **`DashboardQmlViewModel`** (`dashboard_view_model.py`): 3 Property mới —
  `symbol`, `startDate`, `endDate` (get/set/notify, cùng khuôn với
  `DataManagementViewModel.selectedSymbol`/`fromDateTime`/`toDateTime`). Default
  symbol `"ETHUSDT"` (khớp `_DEFAULT_SYMBOLS[0]` bên Presenter, nhưng cố tình
  không import chéo — cùng kiểu tự-chứa-default như `DataManagementViewModel`),
  default date range = 7 ngày gần nhất tới hiện tại (UTC), format
  `"%Y-%m-%d %H:%M"` — export ra module constant `DATETIME_FORMAT` để
  `stream_lifecycle_controller.py` dùng lại, không lặp literal.
- **`DevBoardPanel.qml`**: `cboSymbol` (ComboBox editable, model
  `["BTCUSDT","ETHUSDT"]`) đổi từ cosmetic sang bind 2 chiều qua
  `currentIndex`/`onCurrentTextChanged`. Bắt đầu bằng cách copy nguyên pattern
  đã chạy thật của `DatabaseScreen.qml`'s `cboSymbol`, nhưng test thật (chạy
  bằng venv tạm, xem mục kết quả test bên dưới) bắt được 2 bug binding-loop
  trong chính pattern đó — đã sửa bằng `Component.onCompleted` (gán
  `currentIndex` đúng 1 lần) + cờ `_initialSyncDone` chặn ghi ngược cho tới
  khi sync ban đầu xong; xem chi tiết ở mục "2 bug thật bắt được nhờ chạy
  test" cuối file.
  `txtStartDate`/`txtEndDate` bind `text: viewModel.startDate/endDate` +
  `onTextEdited` (không phải `onTextChanged` — tránh vòng lặp khi ViewModel tự
  set lại text), cũng đúng pattern `DatabaseScreen.qml`'s
  `txtFromDateTime`/`txtToDateTime`.
- **Validate trước dispatch** (`StreamLifecycleController._read_and_validate_inputs`,
  gọi từ cả `_on_load_history` và `_on_start_stream`): symbol phải khớp
  `^[A-Z0-9]{5,20}$` (upper+strip trước khi so, không phải lỗi nếu gõ
  thường), interval phải là `TimeFrame` hợp lệ, cả 2 ngày phải parse được
  (UTC, cùng format `DataManagementPresenter._CUSTOM_TIME_FORMAT` dùng) và
  `start < end`. Lỗi nào cũng return sớm + log `level="error"`, không dispatch
  gì cả — không có "âm thầm dùng lại giá trị cũ".
- **Symbol/date range chảy tới query/command thật**: `GetHistoricalKlinesQuery`
  (cả trong `_run_load_history` và `_run_sync_and_start`) và
  `SyncMarketDataCommand` giờ nhận `start_time`/`end_time` thật từ UI — cả 2
  đã có sẵn field này từ trước (dùng chung với `DataManagementPresenter`),
  chỉ chưa ai truyền vào từ Dev Board. `symbols` list đổi từ hard-code
  `_DEFAULT_SYMBOLS` (`("ETHUSDT",)`) sang `[symbol]` đọc từ ViewModel.
  Tham số mới (`start_time`, `end_time`) được **thêm vào cuối** chữ ký
  `_run_load_history`/`_run_sync_and_start`/`thread_manager.submit(...)` thay
  vì chen giữa — giữ nguyên toàn bộ vị trí positional-arg cũ mà bộ test hiện
  có đang assert, tránh phải sửa lại hàng loạt test không liên quan.
- **`(symbol, interval)` identity fix** — bug thật phát hiện khi làm phần này:
  `_rebuild_scripts`, `_on_indicator_data`, `_on_script_region_data`,
  `_on_script_info_data`, `_on_script_marker_data` đều tra chart card bằng
  hằng số module `_DEFAULT_SYMBOLS[0]` ("ETHUSDT") bất kể symbol nào thực sự
  đang được load — nghĩa là chỉ cần đổi sang symbol khác, mọi indicator sẽ
  âm thầm ngừng vẽ (card đúng key vẫn tồn tại trong `active_charts`, nhưng
  không ai tra đúng key nữa). Sửa bằng cách thêm `self._active_symbol`
  (instance attribute, cùng kiểu `self._active_interval` đã có từ BOT-033
  §6/BOT-034), set mỗi lần Load History/Start Live qua callback
  `set_active_symbol` bơm vào `StreamLifecycleController`. Đã viết test hồi
  quy riêng cho bug này (`test_indicator_data_routes_to_the_chart_of_the_active_symbol`,
  `test_rebuild_scripts_clears_the_chart_of_the_active_symbol`).
- **Bug phụ tìm thấy cùng lúc, không phải phạm vi Phase 2 nhưng sửa luôn vì
  1 dòng, rõ ràng, cùng gốc `(symbol, interval)` identity**: `_tick_to_candle`
  hard-code `interval=_DEFAULT_INTERVAL_STR` ("1m") cho mọi live tick, bất kể
  `self._active_interval` thực tế — BOT-034 đổi mọi chỗ đọc interval khác
  sang instance attribute nhưng bỏ sót đúng chỗ này, khiến
  `_raw_klines_by_symbol` gắn sai nhãn interval mỗi khi user chọn timeframe
  khác "1m". Đã thêm tham số `interval` vào `_tick_to_candle` và truyền
  `self._active_interval` tại nơi gọi (`_on_ui_chart_update`).

#### Test mới

- Unit (`tests/unit/presentation/ui/screens/test_dashboard_presenter.py`):
  đọc/validate/normalize symbol, reject symbol/date sai, truyền đúng
  start_time/end_time vào `_run_load_history`/`_run_sync_and_start`, và 2 test
  hồi quy cho bug `_DEFAULT_SYMBOLS[0]`/`_tick_to_candle` ở trên.
- Unit (`test_dashboard_view.py`): default + settable của 3 Property mới trên
  `DashboardQmlViewModel`.
- Integration (`test_dev_board_known_gaps.py`): TC-GAP-02
  (`test_symbol_dropdown_changes_which_symbol_load_history_fetches`) và
  TC-GAP-05 (`test_start_date_field_binds_to_the_view_model`,
  `test_an_invalid_date_range_blocks_load_history`) đổi từ "known gap" sang
  "fixed", tách riêng TC-GAP-04 (Strategy — vẫn ngoài phạm vi) thành test
  độc lập thay vì gộp chung như trước.

#### Ngoài phạm vi Phase 2 (không đụng tới)

- `_run_load_more_history`/`fetch_older_history` (BOT-035, infinite-scroll
  "load more") **không** nhận `start_time`/`end_time` — đây là hành động
  "tải thêm về quá khứ" độc lập, không nên bị giới hạn bởi date range ban đầu
  user gõ cho lần Load đầu tiên (đúng tinh thần BOT-035 đã ghi: load-more
  không chạy qua `_compute_fetch_limit()` vì lý do tương tự).
- `cboMarket` (Spot/Futures) và `cboStrategy` (Manual/SMA Crossover) —
  Phase 3, chưa đụng tới, đúng như đã chốt phạm vi từ đầu.

### Phase 3 — thao tác phụ thuộc quyết định sản phẩm (không tự ý bật)

- `Market` Spot/Futures: chỉ triển khai sau khi hạ tầng exchange xác nhận hỗ trợ
  Futures và hợp đồng dữ liệu khác Spot.
- `Strategy`: theo `BOT-026`; cần concrete strategy, log signal và marker chart.
- `Seed Records`, `Export JSON`, `Purge Vault`: cần use case/backend riêng. Nếu
  được chấp thuận, `Purge` bắt buộc có confirmation dialog.
- Settings persistence: cần use case ghi `user_config.json` và chính sách bảo vệ
  API secret; không chỉ đổi nhãn nút Save.

## 3. Ngoài phạm vi

- Đặt lệnh thật, quản lý ví/balance, Futures execution.
- Backtest UI/engine.
- Tự động áp indicator ngay trên chart đang chạy. Indicator/period tiếp tục có
  hiệu lực ở lần Load/Start kế tiếp để giữ contract hiện tại.

## 4. Tiêu chí hoàn thành

- Không còn request history/start chồng gây sai indicator hoặc UI state.
- Mỗi input Phase 2 tác động đúng request thực tế và lỗi validation được báo rõ.
- Kết quả/tick cũ không cập nhật chart sau khi user đổi `(symbol, interval)`.
- Unit/integration tests mới xanh; QML smoke test xác nhận binding và enabled
  state.
  ✅ **Đã tự chạy thật** (dựng venv tạm, cài PySide6/pyqtgraph/pydantic/
  sqlalchemy/qdarktheme/python-binance + toàn bộ `requirements.txt`, không
  chỉ review bằng mắt): `pytest tests/unit/ tests/integration/` toàn repo —
  **500 passed, 0 failed**.

#### 2 bug thật bắt được nhờ chạy test thay vì chỉ review

Cả 2 đều ở `cboSymbol` (`DevBoardPanel.qml`), cùng gốc: `currentIndex` từng là
1 **live binding** vào `viewModel.symbol` (y hệt pattern `DatabaseScreen.qml`
copy sang), gây `onCurrentTextChanged` bắn ngược lại `viewModel.symbol` bất
cứ khi nào `currentIndex` đổi — kể cả khi chính binding đó tự đổi:

1. **Binding loop nuốt symbol tự gõ**: gõ 1 symbol không có trong
   `presetSymbols` (vd "BT" trong test, hoặc "SOLUSDT" ngoài đời thật) khiến
   `indexOf` trả -1 → `Math.max(0, -1)` = 0 → currentIndex nhảy về 0 →
   `onCurrentTextChanged` bắn lại → `viewModel.symbol` bị ghi đè thành
   "BTCUSDT", xoá mất input vừa gõ. QML console log thật:
   `"Binding loop detected for property currentIndex"`.
   Test bắt được: `test_on_load_history_rejects_an_invalid_symbol` (submit
   được gọi dù input invalid — vì input đã bị binding loop tự sửa thành
   "BTCUSDT" hợp lệ trước khi validate chạy).
2. **Default symbol bị ghi đè lúc mở màn hình**: `ComboBox` tự gán
   `currentIndex = 0` ("BTCUSDT") ngay khi `model` được set — TRƯỚC khi
   `Component.onCompleted` (fix cho bug #1) kịp chạy để đặt lại đúng default
   từ `viewModel.symbol` ("ETHUSDT") — `onCurrentTextChanged` bắn 1 lần nữa
   với "BTCUSDT" trước cả `onCompleted`, khiến default thật sự luôn là
   "BTCUSDT" bất kể `DashboardQmlViewModel`'s default là gì.
   Test bắt được: `test_script_lines_are_routed_to_the_runner` và 3 test chị
   em (`presenter._active_symbol` là "BTCUSDT" thay vì "ETHUSDT" ngay sau khi
   construct, nên lookup `active_charts.get("ETHUSDT")` từ test fail).

**Sửa dứt điểm cả 2**: bỏ live-binding, chỉ gán `currentIndex` 1 lần ở
`Component.onCompleted`, và thêm cờ `_initialSyncDone` chặn
`onCurrentTextChanged` ghi ngược cho tới khi `onCompleted` đã chạy xong (xem
comment tại chỗ trong `DevBoardPanel.qml`). **`DatabaseScreen.qml`'s
`cboSymbol` nhiều khả năng có cùng bug #2 này** (không sửa — ngoài phạm vi
task này, nhưng đáng note lại nếu ai động vào màn đó sau này: default
`selectedSymbol` của `DataManagementViewModel` có thể đang luôn bị ghi đè
thành item đầu của `viewModel.symbols` bất kể default thật là gì).

## 5. Phụ thuộc và rủi ro

- Phụ thuộc `BOT-027` cho phần race condition; task này triển khai thay vì nhân
  đôi giải pháp.
- Trước Phase 2 phải giải quyết định tuyến theo interval: code hiện chỉ route
  theo symbol, không an toàn khi thêm nhiều timeframe.
- Không sửa hoặc commit các thay đổi đang có của `BOT-032` trong worktree.
