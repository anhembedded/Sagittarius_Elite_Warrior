# Hoàn thành: BOT-095B — Backtest FSM Dirty Tracking & Diff Summary

> Thuộc Epic [`BOT-095`](../backlog/BOT-095_backtest_signals_fsm_lifecycle_epic.md).

## Bàn giao

- `backtest_fsm_matrix.py` là nguồn trạng thái và event tập trung, gồm
  `CONFIG_DIRTY`, `CANCELLING`, `COMPLETED` cùng transition matrix khai báo.
- `BacktestRunConfig` snapshot cấu hình lần chạy, so sánh delta và tạo diff
  summary. `BackTestPresenter` dùng snapshot này để chuyển kết quả cũ sang
  stale khi toolbar thay đổi.
- ViewModel/QML hiển thị stale banner, đổi CTA sang “CẬP NHẬT LẠI”, làm mờ
  Trade Logs và đánh dấu export là dữ liệu cũ.
- Các test FSM lifecycle và Presenter đã có trong repository.

## Ghi chú kế thừa

Task đặc tả ban đầu được giữ ở `backlog/` để không làm mất lịch sử thiết kế;
file này là đích liên kết completion chính thức của Roadmap. `BOT-095H` phải
xong trước các phần async kế tiếp để ngăn callback cũ phá lifecycle này.

