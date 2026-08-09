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

### Phase 2 — cấu hình dữ liệu của Developer Board

- Nối `Symbol`, `Timeframe`, `Start date`, `End date` với ViewModel/Presenter.
- Validate symbol, interval và date range trước khi dispatch; truyền các giá trị
  đã chốt vào query/load/start thay vì dùng hằng hard-code.
- Định danh dữ liệu/chart theo `(symbol, interval)` để tick hoặc result cũ không
  bị trộn vào lựa chọn mới.
- Nối Chart toolbar với cùng timeframe selection, không chỉ thay highlight.
  ✅ **Đã làm** (bởi 1 task khác chạy song song, số hiệu bị trùng nên đã đổi thành `BOT-034` —
  xem `Tasks/backlog/BOT-034_dev_board_autostart_and_data_lifecycle.md` §6):
  `ChartToolbar.sig_timeframe_changed` đã nối vào `DashboardPresenter._on_timeframe_changed`,
  `cboTimeframe` (System Controls) đã bị xoá khỏi `DevBoardPanel.qml` để tránh 2 nguồn sự thật.
  Đổi timeframe reload ngay lập tức, kể cả khi đang Live (dừng → reload → start lại). Nếu Phase 2
  của task này cũng định làm lại phần toolbar, **đọc file đó trước** để tránh làm trùng/xung đột.

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

## 5. Phụ thuộc và rủi ro

- Phụ thuộc `BOT-027` cho phần race condition; task này triển khai thay vì nhân
  đôi giải pháp.
- Trước Phase 2 phải giải quyết định tuyến theo interval: code hiện chỉ route
  theo symbol, không an toàn khi thêm nhiều timeframe.
- Không sửa hoặc commit các thay đổi đang có của `BOT-032` trong worktree.
