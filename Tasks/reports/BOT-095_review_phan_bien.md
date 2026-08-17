# Rà soát phản biện Epic BOT-095 — Backtest lifecycle

> Rà soát mã nguồn ngày 17/08/2026. Phạm vi: Epic `BOT-095`, đặc biệt là
> `BackTestPresenter`, `RunStaticBacktestCommandHandler`, FSM và các task
> `BOT-095C`…`BOT-095G`.

## Kết luận

Epic đúng hướng và phần nền đã có thật: `BOT-095A` đã có
`DeclarativeStateMachine` cùng bộ test Engine; `BOT-095B` đã có ma trận FSM,
dirty tracking, stale banner và test Presenter. Phần còn lại không nên triển
khai theo thứ tự cũ ngay lập tức. Cần đóng một lỗ hổng P1 về **quyền sở hữu của
tác vụ bất đồng bộ** trước: callback của run/sync cũ không được phép cập nhật
UI hoặc tự khởi động lại một cấu hình mới.

## Phát hiện và quyết định bổ sung

| Mục | Phản biện có bằng chứng | Quyết định chốt |
| :--- | :--- | :--- |
| Trạng thái tài liệu | Roadmap đánh `BOT-095A`/`B` hoàn tất, nhưng file task của chúng vẫn nằm ở `backlog`; liên kết completion của `BOT-095B` hiện không có file đích. | Không suy ra trạng thái từ thư mục. Thêm biên bản completion cho `B`; làm audit riêng khi dọn metadata toàn board. |
| `EMPTY_DATA` | Code hiện xem `result is None` (không có nến) là EMPTY; một `BacktestResult` có 0 trade vẫn là run thành công và có metrics. | Không dùng `EMPTY_DATA` cho “0 trade”. Đổi nghĩa thành `NO_HISTORICAL_DATA` ở lần refactor FSM kế tiếp, hoặc ghi rõ alias tương thích nếu chưa đổi tên. |
| Cancellation | Static handler hiện mô phỏng full range rồi còn chạy in/out-of-sample; kiểm tra token mỗi 1,000 nến và chỉ ở pass chính không thể bảo đảm hủy nhanh. `BacktestResult(cancelled=True)` cũng không phải contract hiện hữu. | Token/progress phải đi qua **mọi** pass; tạo outcome hủy tường minh, không emit success/failure event sau hủy; latency được đo bằng test, không hứa một số tuyệt đối. |
| Callback cũ | `SYNC_SUCCEEDED` hiện tự đọc toolbar hiện tại để run tiếp. Dù controls bị khóa, callback muộn từ một action cũ vẫn có thể thắng một action/reset mới khi các task tiếp theo mở thêm entry point. | Thêm `BOT-095H`: action id/generation, config snapshot, terminal outcome và fencing cho mọi callback. Đây là prerequisite của `C`, `D`, `G`. |
| Data probe | `min <= start and max >= end` không phát hiện lỗ thủng ở giữa, nến đang mở, hay timezone/boundary sai; count tổng không chứng minh coverage. | `BOT-095D` phải dùng UTC half-open range, cadence theo timeframe, phát hiện missing segments và post-sync re-probe. Preview chỉ được coi là preview, không là bằng chứng data đủ. |
| Validation Binance | 5 USDT là min-notional theo symbol/market và phụ thuộc giá + quantity; initial capital không đồng nghĩa order notional. | Tách local validation (format/range) khỏi market-rule validation. Chỉ enforce filter đã lấy được theo symbol; nếu không có metadata, báo “chưa xác minh” thay vì hard-code 5 USDT. |
| Dynamic indicators | Feed toàn bộ candle đồng bộ trên UI thread có thể làm UI treo; mục tiêu `<50ms` không thực tế với nhiều nến. | Render off-thread hoặc cache output theo `(run_id, script_key, script_version)`; chỉ đưa artifact đã hoàn tất về UI thread. Indicator tham chiếu không làm dirty execution config. |
| Run history | Snapshot giữ tham chiếu mutable sẽ sai lịch sử; chỉ lưu metrics/trades thiếu raw candles/markers/provenance thì không thể “khôi phục hoàn hảo”. | Snapshot bất biến, bounded cache theo budget bộ nhớ, có provenance (data window/watermark, strategy version/params, fee, engine mode). Restore thực hiện transactionally và suppress dirty signal. |

## Thứ tự triển khai đề nghị

`BOT-095A` ✅ → `BOT-095B` ✅ → **`BOT-095H`** → `BOT-095C` → `BOT-095D` →
`BOT-095E` / `BOT-095F` → `BOT-095G`.

`BOT-095C` đi trước `D` để thống nhất outcome/cancel/progress của backtest rồi
mới dùng chung action lifecycle cho sync. `BOT-095G` làm sau vì snapshot phải
gắn với `run_id` và provenance đã được `H` chuẩn hóa.

## Acceptance criteria dùng chung cho C/D/G

- Mỗi action có `action_id`, `kind`, immutable config snapshot, trạng thái
  terminal và timestamp; chỉ callback khớp action còn active mới được mutate UI.
- Cancel là idempotent. Hai lần bấm Cancel, callback thành công đến muộn, hoặc
  callback thất bại đến muộn đều không tạo transition trái phép.
- Hủy backtest/sync không tự động chạy lại; chỉ một intent `RunRequested` còn
  hiệu lực mới được auto-continue sau sync.
- Mọi đường terminal phải kiểm chứng bằng test race: success-after-cancel,
  failure-after-cancel, old-success-after-new-run, và sync-success-after-config-change.
- Ngưỡng hiệu năng phải được benchmark trên fixture đã công bố (số nến, máy
  đo, warm-up); không dùng cam kết `0ms`, `<50ms`, `<100ms` như một acceptance
  criterion độc lập.

