# BOT-123: Dev Board thiếu progress bar cho pha sync + nút Cancel không bật được lúc đang sync

**Trạng thái:** ✅ Hoàn thành (2026-09-01)

## 1. Bối cảnh & vấn đề thật

User đối chiếu mockup vs app thật (`Developer Board`), rồi gửi kèm 1 đoạn log thật của một lần
đổi timeframe khi đang Live: *"layout chung của màn hình abstract, thêm 1 layout progressbar,
sau đó chuẩn hoá lại progress bar hiện tại màn hình dev board chưa có progress bar"* — và
*"sync data nhưng không có progress bar, nút cancel vẫn chưa enable khi đang syncing"*.

Log đính kèm cho thấy đúng root cause: đổi timeframe lúc đang `LIVE` gọi lại `_on_stop_stream()`
rồi `_on_start_stream()` ngay lập tức — FSM chuyển sang `LOCKED`, `SyncMarketDataCommand` chạy
~9.8s để đồng bộ 17,568 nến ETHUSDT trước khi WebSocket kịp mở lại. Suốt quãng đó:

- **Không có gì hiển thị tiến độ** — dòng log `"Syncing missing data from Binance..."` là tín
  hiệu duy nhất, không đổi trong suốt 9.8s.
- **Nút Stop bị khoá** — `_sync_controls_active()` chỉ bật Stop khi `vm.uiMode == "LIVE"`, nên
  đúng lúc user muốn huỷ nhất (đang chờ sync) lại không bấm được gì ngoài tắt hẳn app.

Backtest và Data Management đã có đúng cặp cơ chế cho việc này (`ProgressBannerWidget` +
`SyncProgressFeed` + `correlation_id`, xem `BOT-121`/`BOT-122` và
[`Docs/Diagrams/event_correlation_id_design.md`](../../Docs/Diagrams/event_correlation_id_design.md)) —
Dev Board là màn sync thứ ba nhưng chưa từng được nối vào.

## 2. Thiết kế — không tạo layout mới, ghép vào layout chung sẵn có

`PageShell` (`src/presentation/ui/kit/page_shell.py`) đã là bố cục chung 4 dải (header/context
bar/workspace+rail/console) mọi màn dùng — không cần thêm. `ProgressBannerWidget`
(`qml/kit/ProgressBanner.qml`) cũng đã là component dùng chung, Backtest/Data Management đã
verify. Việc cần làm là **nối** Dev Board vào 2 cái đó, đúng khuôn `correlation_id` của
`BOT-122` — không lọc theo `(symbol, interval)`, vì Dev Board tự khởi lại chính nó (Stop rồi
Start lại khi đổi timeframe) hoàn toàn có thể trùng khoá đó với 1 request khác của chính nó.

```
StreamLifecycleController._sync_market_data() sinh correlation_id (uuid4)
  → SyncMarketDataCommand.correlation_id
    → SyncMarketDataCommandHandler publish SingleSyncProgressEvent (đã có sẵn từ BOT-122)
      → SyncProgressFeed (DashboardPresenter subscribe, giống Backtest/Data Management)
        → StreamLifecycleController.on_sync_progress() lọc đúng correlation_id đang giữ
          → ui_sync_progress_signal → DashboardQmlViewModel.set_progress()
            → DevBoardPanel._sync_progress() → ProgressBannerWidget
```

- `DashboardQmlViewModel`: thêm block `progress*` (Value/Maximum/Visible/Text/Percent) +
  `set_progress()`/`hide_progress()` — **y hệt** shape `DataManagementViewModel` đã có, không
  phát minh property mới.
- `StreamLifecycleController`: `_active_sync_correlation_id` (đọc/ghi xuyên thread, cùng mẫu
  `DataSyncCoordinator`/`SyncCoordinator` của `BOT-122`) + `on_sync_progress()` lọc theo id +
  `_sync_market_data()` sinh id/bật bar + `_run_sync_and_start()` bọc `finally` tắt bar dù kết
  quả là thành công/huỷ/lỗi.
- `DevBoardPanel`: `ProgressBannerWidget` mới trong card "Actions" (dưới hàng Load
  History/Start Live/Stop — đúng vị trí Backtest/Data Management đặt banner của họ so với nút
  bấm sync), Cancel của banner nối thẳng vào `requestStopStream` — **không** phải một đường huỷ
  riêng, cùng lệnh nút Stop đang có.
- **Fix bug thật**: `_sync_controls_active()` đổi điều kiện bật Stop từ `uiMode == "LIVE"` thành
  `uiMode in ("LIVE", "LOCKED")` — `_on_stop_stream()` vốn đã `cancel()` đúng
  `CancellationToken` mà `cancellation_requested` của sync đang đọc (`BUG-067`), chỉ thiếu
  đường bật nút.

## 3. Ngoài phạm vi

- Không trích đoạn glue "dựng `ProgressBannerWidget` + `_sync_progress()`" thành 1 helper dùng
  chung cho cả 3 màn — Dev Board là consumer thứ 3 lặp lại đúng ~10 dòng đó, nhưng thăng cấp nó
  không nằm trong yêu cầu, và sẽ phải đụng cả Backtest/Data Management đang chạy đúng.
- Không đổi `PageShell` — layout chung đã đúng, vấn đề chỉ là Dev Board chưa dùng
  `ProgressBannerWidget` bên trong nó.

## 4. Kiểm thử

- `test_dev_board_panel.py`: `test_stop_stays_enabled_while_locked_...` (test đỏ xác nhận: trước
  fix, `LOCKED` giữ Stop `disabled`), `test_progress_banner_reflects_the_view_model`,
  `test_clicking_the_progress_banners_cancel_button_requests_stop`.
- `test_stream_lifecycle_cancellation.py`: `test_sync_shows_the_progress_bar_then_hides_it_...`,
  `test_on_sync_progress_ignores_a_report_for_a_different_correlation_id`,
  `test_on_sync_progress_forwards_a_report_for_its_own_correlation_id`,
  `test_on_sync_progress_ignores_everything_when_no_sync_is_in_flight` — cùng lớp test
  `BOT-122` đã dùng cho `DataSyncCoordinator`/`SyncCoordinator`.

**Xác minh:** Linux thật (Python 3.12, PySide6 6.11.1 + `sagittarius_engine` cài editable từ repo
engine). 116 test trực tiếp liên quan (`screens/dashboard/`, `test_dev_board_panel.py`,
`test_dashboard_presenter.py`) + 28 test integration Dev Board (race conditions, indicators,
custom scripts, known gaps, live stream) + 210 test Backtest/Data Management/common (kiểm tra
không ảnh hưởng chéo, vì `SyncProgressFeed`/`SyncProgressReport` dùng chung) + 156 test
`application/` + 24 test `sanity/` (composition root thật) đều pass. `ruff check`/`format`: sạch.
`mypy`: không chạy trên `presentation/` (đã excluded wholesale theo `pyproject.toml`, class lỗi
`@Property` false-positive đã biết — xem `EPIC-002A`), đúng phạm vi gate hiện có.
