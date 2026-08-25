# 🐞 Bug Board — Sagittarius Elite Warrior

Bảng theo dõi **mọi lỗi đã báo cáo** của app. Tách riêng khỏi
[`../ROADMAP.md`](../ROADMAP.md) có lý do: ROADMAP là bảng *task* — bug đã sửa
thì xuất hiện ở mục Completed của nó, nhưng bug **đang mở** thì trước đây
không có chỗ nào hiển thị cả. Muốn biết hệ thống đang gánh lỗi gì, phải mở
từng file lên đọc. Bảng này là câu trả lời cho câu hỏi đó.

- **Bố cục thư mục** (song song với `Tasks/backlog|completed/` của task):
  - `incomplete/` — bug **chưa sửa xong**. Bug mới luôn tạo ở đây.
  - `completed/` — bug đã sửa, kèm ảnh chụp/bằng chứng của chính nó.
- Đặt tên `BUG-XXX_mô_tả.md`, số kế tiếp số lớn nhất đang tồn tại **ở cả hai
  thư mục**.
- **Khi sửa xong:** `git mv incomplete/BUG-XXX_*.md completed/` (kèm ảnh của
  nó), cập nhật `Status` trong file, rồi chuyển dòng tương ứng ở bảng dưới từ
  mục "Đang mở" sang mục "Đã sửa".
- Quy trình xử lý bug: [`.agents/rules/bug-fix-rule.md`](../../.agents/rules/bug-fix-rule.md)
  — root cause trước, regression test **fail đúng lý do** trước khi sửa, giữ
  test vĩnh viễn, ghi hồ sơ.
- Bug **không** được tính vào các con số task ở `ROADMAP.md`.

> Cập nhật: 2026-08-25

---

## 📊 Tổng quan

| Trạng thái | Số lượng |
| :--- | :---: |
| 🔴 **Đang mở** | 4 |
| ✅ **Đã sửa / đã đóng** | 41 |
| 📈 **Tổng** | **45** |

---

## 🔴 Đang mở (Open)

| ID | Tiêu đề | Mức độ | Ngày báo | Ghi chú |
| :--- | :--- | :---: | :---: | :--- |
| **[BUG-044](incomplete/BUG-044_published_engine_has_python2_except_syntax.md)** | `sagittarius_engine` 2.3.0 publish lên GitHub không import được — cú pháp `except A, B:` của Python 2 | 🔴 **P1** | 2026-08-25 | Fix đã push lên nhánh engine `claude/python2-exception-syntax-590urp`, chờ vào `main`. `v2.1.0`/`v2.2.0` đều dính (tự verify trên full clone). Thoát được vì `ruff check` báo "All checks passed!" trên file CPython không parse nổi. |
| **[BUG-045](incomplete/BUG-045_sanity_tier_makes_live_binance_network_calls.md)** | Tầng Sanity gọi mạng thật lên `api.binance.com` mỗi lần chạy CI | 🟡 P2 | 2026-08-25 | `container.resolve(...)` dựng `PythonBinanceClient`, constructor ping `/api/v3/ping`. Fixture chỉ patch websocket. Vi phạm `ci-rule.md` §6 "no network". Fix là `EPIC-009` D6 (fake Binance server). |
| **[BUG-034](incomplete/BUG-034_dev_board_live_chart_wrong_axis_scale.md)** | Dev Board Live Chart: nến không hiển thị, trục Y auto-range sai thang đo | Chưa đánh giá | 2026-08-23 | Chỉ mới ghi nhận hiện tượng theo yêu cầu, chưa điều tra root cause. OHLC/EMA readout đúng vùng giá ~2400 nhưng trục Y hiện `-50..100`. |
| **[BUG-030](incomplete/BUG-030_parallel_test_run_worker_dies_after_resource_warning.md)** | `ci-local.ps1 -Full` (song song `-n 6`) chết giữa chừng sau `ResourceWarning: unclosed database`, không có summary | 🟡 P2 | 2026-08-21 | Tái hiện 2/2 lần **đúng cùng 1 chỗ** (không phải flaky), chỉ trên Windows. **Cập nhật 2026-08-25:** cơ chế đã chứng minh — `engine.dispose()` chỉ đóng connection *checked-in*; một `Session` còn checked-out thì `dispose_all()` **không** đóng, để lại cho GC → đúng điều kiện sinh `ResourceWarning`. Nên bước "cứ thêm `dispose_all()`" là **không đủ**. Linux đo lại bằng bằng chứng dương tính: 0 connection chưa đóng trên cả 6 worker. Đã có `scripts/bug030_connection_leak_probe.py` để chỉ đích danh file:line khi chạy được trên Windows. |

---

## ✅ Đã sửa (Fixed)

| ID | Tiêu đề | Mức độ | Ngày báo | Sửa ở |
| :--- | :--- | :---: | :---: | :--- |
| **[BUG-041](completed/BUG-041_app_shutdown_hangs_on_inflight_thread_pool_task.md)** | App không thực sự thoát tiến trình khi có job nền đang chạy trên `ThreadManager` | 🟡 P2 | 2026-08-24 | Per-scan cooperative cancellation xuyên Presenter → Coordinator → Query Handler; process probe 2.000 pair thoát ~1,1s, full CI 1.700 tests pass. |
| **[BUG-043](completed/BUG-043_run_ui_cannot_import_local_engine.md)** | `run-ui.ps1` không import được Sagittarius Engine local | 🟡 P2 | 2026-08-24 | Bootstrap engine bằng editable sibling checkout hoặc GitHub theo `install-rule.md`; đồng thời cấu hình đúng local import path. |
| **[BUG-042](completed/BUG-042_paper_exchange_log_flood_freezes_ui_thread.md)** | Backtest nhiều trade đơ cứng UI — `PaperExchange` log INFO mỗi lệnh khớp, đổ vào `LogListModel` trên UI thread | 🔴 **P1** | 2026-08-24 | Trong chính hồ sơ này (2026-08-24). Tuân thủ `logging-rule.md` Rule 4 & 6: hạ 3 log per-fill/close sang `DEBUG`, giữ init ở `INFO`. `SignalLogHandler` (INFO) không nhận log per-trade; test red $\rightarrow$ green, CI full pass 1695 tests. |
| **[BUG-039](completed/BUG-039_native_chart_default_regressed_backtest_visuals.md)** | Native chart làm mặc định khiến Backtest mất grid, nến vẽ sai, tự phá chart khi có trend zone | 🔴 **P1** | 2026-08-24 | **Đóng 2026-08-24:** xoá hẳn native chart (`36f3a9f`) — không còn backend thì không còn đường tái hiện. Chính hồ sơ này là lý do quyết định xoá. |
| **[BUG-040](completed/BUG-040_ci_local_flaky_under_full_gate_load.md)** | `ci-local.ps1` flaky dưới tải full gate | 🟡 P2 | 2026-08-24 | Xem hồ sơ. |
| **[BUG-016](completed/BUG-016_chart_migration_benchmark_desktop_contract_hangs_windows.md)** | `chart_migration_benchmark.py --desktop-contract` treo vô hạn trên Windows | 🔴 **P1** | 2026-08-19 | **Đóng 2026-08-24 (moot, không phải fix):** native chart backend và script benchmark của nó đã bị xoá hoàn toàn để mở khoá `EPIC-006F`. |
| **[BUG-038](completed/BUG-038_native_fallback_drops_the_content_it_fell_back_for.md)** | Fallback sang Python vứt luôn nội dung mà nó fallback vì nó — nền trend zone không bao giờ được vẽ | 🔴 **P1** | 2026-08-23 | Trong chính hồ sơ này (2026-08-23). User phát hiện bằng mắt; test và log đều "xanh". Thêm `_apply_after_native_fallback()` phát lại nội dung lên host mới (cả 4 call site) + log `[chart-region]` ghi **đã vẽ mấy vùng lên host nào**. Xác nhận trên app thật: `replayed 1504 item(s)`. |
| **[BUG-037](completed/BUG-037_empty_trend_zone_payload_kills_native_chart_every_run.md)** | Native chart bị bỏ ở **mọi** lần chạy Backtest vì payload trend-zone **rỗng** | 🔴 **P1** | 2026-08-23 | Trong chính hồ sơ này (2026-08-23). `set_script_regions()` raise mà không nhìn payload; presenter emit spans rỗng mỗi lần chạy → cả epic `BOT-098F` chết ở runtime. Test cũ dùng `[]` nên đã đóng băng đúng hành vi sai. |
| **[BUG-036](completed/BUG-036_benchmark_crosshair_contract_synthetic_hover_race.md)** | Gate `Chart Benchmark Contract` lúc PASS lúc FAIL trên cây code giống hệt — synthetic hover ghi đè crosshair | 🟡 P2 | 2026-08-23 | Trong chính hồ sơ này (2026-08-23). Qt tự sinh hover tại con trỏ ma `(8,8)` của platform `offscreen`; `hoverMoveEvent()` đẩy thẳng vào `setCrosshairPosition()`, ghi đè giá trị benchmark vừa đặt. Sửa: đọc property ngay sau setter (đồng bộ), giữ giá trị sau-flush làm diagnostic + WARNING. Tái hiện 5/40 dưới tải, 0/40 sau sửa. |
| **[BUG-035](completed/BUG-035_engine_2_0_0_qml_module_rename_breaks_all_ui.md)** | Engine 2.0.0 đổi tên QML module `QmlShared` → `Sagittarius.UI`, hỏng toàn bộ UI | Cao | 2026-08-23 | 26 file `.qml` + 2 test file. Đóng chung BOT-117/BOT-118. Thêm guard `test_qml_imports_match_engine_qmldir.py`. Gate PASS, 1773 passed. |
| **[BUG-033](completed/BUG-033_realtime_backtest_progress_flood_freezes_ui_thread.md)** | Realtime Backtest tick-level làm UI thread đơ 5+ giây (progress signal flood) | 🟡 P2 | 2026-08-23 | Trong chính hồ sơ này (2026-08-23). Throttle `progress_callback` đổi từ đếm index (mỗi 256 tick/16 bar) sang thời gian thực (`ProgressThrottle`, ~150ms/lần) ở cả 2 handler (realtime + static) — chặn burst ~10,125 lần emit signal cross-thread cho 1 lần chạy 2.59M tick. |
| **[BUG-032](completed/BUG-032_chart_preview_renders_candles_before_running_backtest.md)** | Chart tự động vẽ nến và volume khi chưa nhấn "Chạy Backtest" | 🟡 P2 | 2026-08-22 | Trong chính hồ sơ này (2026-08-22). Không phải bug ngẫu nhiên — tính năng "Live Chart Preview" có chủ đích (`BOT-095D`/`BOT-102`) nhưng thiếu state phân biệt. Thêm `isChartPreview` (ViewModel) + badge QML, bật ở `_on_preview_data_ready`, tắt ở `_on_chart_data_ready`. |
| **[BUG-031](completed/BUG-031_cross_thread_timer_start_hangs_ui_during_backtest.md)** | `QBasicTimer::start: Timers cannot be started from another thread` treo UI màn hình Backtest | 🔴 **P1** | 2026-08-22 | Trong chính hồ sơ này (2026-08-22). Chuyển `apply_height` / `apply_minimum_height` thành `@Slot()` trên `BackTestView` gọi qua `QMetaObject.invokeMethod(..., QueuedConnection)`; bổ sung `@Slot(str)` cho `BackTestViewModel.set_ui_mode`. |
| **[BUG-029](completed/BUG-029_build_native_chart_join_path_powershell5_incompatible.md)** | `build-native-chart.ps1` dùng `Join-Path` 3-5 tham số, không chạy được trên Windows PowerShell 5.1 | 🔴 P1 | 2026-08-21 | Trong chính hồ sơ này (2026-08-21). `ci-local.ps1` tự khai `#Requires -Version 5.1` nhưng bị chính script con phá tương thích. Sửa 4 chỗ thành `Join-Path` lồng nhau 2 tham số. Verify trên đúng PowerShell 5.1 + `$ErrorActionPreference=Stop`. |
| **[BUG-015](completed/BUG-015_native_chart_geometry_rebuild_on_pointer_interaction_windows.md)** | Native chart "dựng lại" geometry OHLCV/volume khi rê chuột — hoá ra không phải bug renderer | 🟡 P2 | 2026-08-19 | Trong chính hồ sơ này (2026-08-21). **Không phải bug native code** — `root->buildCount` luôn = 1, đúng. Bug thật nằm ở probe script đọc property `geometryBuildCount` trước khi render thread kịp publish qua cross-thread hop — cùng lớp lỗi với 3 probe-bug khác đã sửa. Sửa: chờ post-condition thật thay vì đếm `processEvents()` cố định. 25% → 15/15 pass. |
| **[BUG-028](completed/BUG-028_kline_inspector_column_widths_misplaced_scope_qml_warning.md)** | `KLineInspectorModal` phát sinh cảnh báo QML `Unable to assign [undefined] to double` | 🟢 P3 | 2026-08-21 | Trong chính hồ sơ này (2026-08-21). Chuyển 5 thuộc tính `col*Width` về phạm vi root `ModalDialogCard` thay vì bên trong `ColumnLayout`. |
| **[BUG-027](completed/BUG-027_seeded_market_data_repository_missing_seven_port_methods.md)** | `_SeededMarketDataRepository` (Desktop E2E probe) thiếu 7/12 method của `IMarketDataRepository` — cùng lớp `BUG-026` | 🟡 P2 | 2026-08-21 | Trong chính hồ sơ này (2026-08-21). Tự phát hiện qua `EPIC-002A`'s audit `mypy`, không phải user báo. 2/7 method thiếu do chính `BUG-025` (phiên này) gây ra — phạm vi grep khi đó bỏ sót `scripts/`. |
| **[BUG-026](completed/BUG-026_shutdown_probe_missing_stream_historical_klines_implementation.md)** | Test probe đóng-app-khi-đang-sync crash — `_BlockingExchangeClient` thiếu `stream_historical_klines()` | 🟡 P2 | 2026-08-21 | Trong chính hồ sơ này (2026-08-21). Có sẵn từ trước (xác nhận qua `git stash`), lộ ra khi chạy full suite sau `BUG-025`; test double chưa theo kịp interface `IExchangeClient` mới. |
| **[BUG-025](completed/BUG-025_unbuffered_full_materialization_sync_and_backtest_data_paths.md)** | Đường dữ liệu Sync (Binance→DB) và Backtest (DB→RAM) không streaming — RAM phình theo độ dài range | 🔴 **P1** | 2026-08-21 | Trong chính hồ sơ này (2026-08-21). Nhánh Backtest: `count_klines()`/`stream_klines()` mới trên `IMarketDataRepository`, `RunStaticBacktestCommandHandler` tiêu thụ generator thay vì `list`. |
| **[BUG-023](completed/BUG-023_app_shutdown_hangs_when_database_sync_running.md)** | Đóng UI nhưng tiến trình Python + Database Sync không thoát (zombie process) | 🔴 **P1** | 2026-08-20 | Trong chính hồ sơ này (2026-08-21). Bổ sung `shutdown()` vào `DataManagementPresenter` và `DashboardPresenter`, cooperative cancellation trong `rate_limiter` & bulk sync, sửa tên tham số `RepairDataGapCommandHandler`. |
| **[BUG-020](completed/BUG-020_gap_repair_calls_undefined_run_check_status.md)** | Vá lỗ hổng thành công vẫn báo lỗi — gọi `_run_check_status()` không tồn tại | 🟡 P2 | 2026-08-20 | Sửa 2026-08-21 trong đợt refactor `_on_check_status()` của phiên khác |
| **[BUG-019](completed/BUG-019_gap_inspector_modal_unavailable_unknown_qml_module.md)** | `GapInspectorModal` không dựng được — `import Sagittarius.Theme` không tồn tại | 🔴 P1 | 2026-08-20 | Sửa 2026-08-21 bởi phiên khác, đúng đề xuất trong hồ sơ |
| **[BUG-024](completed/BUG-024_trend_zone_background_regions_uncapped_causes_pan_lag.md)** | Nền đỏ/xanh (trend zone) làm pan/zoom lag ~9x — 2065 `LinearRegionItem` không cắt tỉa viewport | 🔴 P1 | 2026-08-20 | Trong chính hồ sơ này (2026-08-20). Refactor `ViewportCulledLayer` ABC + `RegionLayer` mirror `MarkerLayer`. Đo lại: 234.7ms → 20.4ms median mỗi bước pan |
| **[BUG-022](completed/BUG-022_realtime_last_tick_of_every_bar_evaluated_twice.md)** | Realtime đánh giá tick cuối của **mọi** bar 2 lần — sai số PnL/trade | 🔴 P1 | 2026-08-20 | Trong chính hồ sơ này (2026-08-20). Tìm ra nhờ điều tra WARNING theo rule CI/CD mới; 6 tick → 9 lần gọi strategy, nay còn 6 |
| **[BUG-021](completed/BUG-021_realtime_backtest_chart_blank_queries_unsynced_timeframe.md)** | Chart trắng hoàn toàn sau mỗi lần chạy Realtime backtest | 🔴 P1 | 2026-08-20 | Trong chính hồ sơ này (2026-08-20) |
| **[BUG-018](completed/BUG-018_data_management_idle_to_idle_unlock_kills_stat_refresh.md)** | Ô "Stored KLines Records" mãi hiện `—` vì auto-discovery kết thúc bằng transition `IDLE -> IDLE` | 🟡 P2 | 2026-08-20 | Trong chính hồ sơ này (2026-08-20) |
| **[BUG-017](completed/BUG-017_backtest_sync_redownloads_full_range_ignoring_cached_coverage.md)** | "Đồng bộ ngay" tải lại toàn bộ range, bỏ qua phần đã cache | 🟡 P2 | 2026-08-20 | Trong chính hồ sơ này (2026-08-20) |
| **[BUG-014](completed/BUG-014_chart_pans_into_empty_space_and_goes_blank.md)** | Chart pan/zoom ra vùng trống rồi trắng hoàn toàn | 🔴 P1 | 2026-08-19 | Trong chính hồ sơ này |
| **[BUG-013](completed/BUG-013.md)** | `ResourceScope` teardown crash khi bắt đầu backtest mới (stale native dispose callback) | 🔴 P1 | 2026-08-19 | Trong chính hồ sơ này (2026-08-19) |
| **[BUG-012](completed/BUG-012.md)** | Indicator data có leading gap, không có giá trị trước để giữ | 🟡 P2 | 2026-08-18 | [`BOT-085`](../completed/BOT-085_dev_board_volume_spike_after_live_reload.md) |
| **[BUG-011](completed/BUG-011.md)** | UI block ở trạng thái health-check | 🟡 P2 | 2026-08-18 | [`BOT-085`](../completed/BOT-085_dev_board_volume_spike_after_live_reload.md) |
| **[BUG-010](completed/BUG-010_backtest_sync_never_satisfies_range_coverage.md)** | "Đồng bộ dữ liệu ngay" không bao giờ thoả range coverage, bấm bao nhiêu lần cũng vậy | 🔴 P1 | 2026-08-18 | Trong chính hồ sơ này (2026-08-18) |
| **[BUG-009](completed/BUG-009_backtest_cached_frame_preview_widget_shift.md)** | Cached-frame drag preview trông như dịch cả widget rồi giật về | 🟡 P2 | 2026-08-18 | Trong chính hồ sơ này (2026-08-18). Là case study của [`logging-rule.md`](../../.agents/rules/logging-rule.md) |
| **[BUG-008](completed/BUG-008_backtest_chart_toolbar_timeframe_noop.md)** | Nút timeframe trên chart-header chỉ có hình, không có tác dụng | 🔴 P1 | 2026-08-17 | Trong chính hồ sơ này |
| **[BUG-007](completed/BUG-007.md)** | Đóng app desktop nhưng tiến trình Python vẫn chạy | 🔴 P1 | 2026-08-17 | [`BOT-099`](../completed/) |
| **[BUG-006](completed/BUG-006.md)** | Trade marker chồng lên nhau đến mức không đọc nổi chart | 🟡 P2 | 2026-08-17 | [`BOT-098A1`](../completed/) |
| **[BUG-005](completed/BUG-005.md)** | Hộp thoại `Critical System Error` cố định kích thước, không xem hết stack trace | 🟡 P2 | 2026-08-14 | Trong chính hồ sơ này |
| **[BUG-004](completed/BUG-004.md)** | Bảng Trade Logs lệch cột giữa header và hàng dữ liệu | 🟡 P2 | 2026-08-14 | [`BOT-089`](../completed/BOT-089_content_driven_panel_sizing.md) — nguyên nhân thật khác với chẩn đoán ban đầu trong hồ sơ |
| **[BUG-003](completed/BUG-003.md)** | Volume bar bất thường sau khi Start Live reload chart | 🟡 P2 | 2026-08-14 | [`BOT-085`](../completed/BOT-085_dev_board_volume_spike_after_live_reload.md) |
| **[BUG-002](completed/BUG-002.md)** | Chart mất nến sau khi zoom out rồi zoom in | 🟡 P2 | 2026-08-12 | [`BOT-072`](../completed/BOT-072_chart_stale_viewport_window_on_zoom.md) |
| **[BUG-001](completed/BUG-001.md)** | App treo khi chưa sync xong (luồng nền chạm UI trực tiếp) | 🔴 P1 | 2026-08-12 | [`BOT-068`](../completed/BOT-068_ui_thread_affinity_guard.md) |

---

## Ghi chú về chất lượng hồ sơ

`BUG-001`…`BUG-005`, `BUG-011`, `BUG-012` là ghi chú thô (ảnh chụp + log dán
vào), không theo cấu trúc header. Từ `BUG-006` trở đi mới có định dạng chuẩn
(Reported / Severity / Status / Symptom / Root cause / Fix / Regression test)
mà [`bug-fix-rule.md`](../../.agents/rules/bug-fix-rule.md) §6 quy định. Mức
độ và ngày của nhóm cũ ở bảng trên được suy ra từ nội dung file và từ task đã
sửa chúng, không phải do file tự khai — nếu cần chính xác tuyệt đối thì đọc
thẳng file gốc.
