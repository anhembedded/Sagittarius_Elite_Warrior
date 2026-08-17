# Hoàn thành: BOT-095H — Quyền sở hữu Action Backtest & Chặn callback lỗi thời

> Thuộc Epic [`BOT-095`](../backlog/BOT-095_backtest_signals_fsm_lifecycle_epic.md).

## Bàn giao

- `BacktestActionContext` giữ `action_id`, kind, cấu hình snapshot deep-copy,
  thời điểm bắt đầu và state trước action. Presenter chỉ giữ một action active;
  action mới invalidate action pending cũ trước khi worker được submit.
- Signal kết quả `BACKTEST`/`SYNC`, chart data và strategy lines đều mang
  `action_id`. Slot chỉ apply UI, FSM hoặc chart khi action đó còn là owner hợp
  lệ; terminal callback lặp hoặc callback cũ chỉ ghi dev trace.
- Sync thành công chỉ tiếp tục đúng config snapshot đã tạo sync. Nó không đọc
  toolbar hiện tại để suy diễn một intent mới.
- `_invalidate_active_action()` là seam idempotent cho `BOT-095C`: Cancel UI
  sẽ gọi nó trước khi yêu cầu worker hủy, nên callback tới muộn đã bị fence
  ngay cả trước khi cancellation token hoàn tất.

## Kiểm thử

- Presenter test mô phỏng deterministically: old success/failure sau action
  mới, success sau failure cùng action, success/failure sau invalidation,
  sync success sau invalidation, và snapshot có nested strategy params.
- Reference-indicator artifacts vẫn do `BOT-095F` fence theo run id, vì chúng
  là pipeline render độc lập sau backtest chứ không được phép đổi lifecycle
  `BACKTEST`/`SYNC`.

## Ghi chú kế thừa

Task đặc tả được giữ ở `backlog/` để bảo toàn lịch sử thiết kế. `BOT-095C`,
`BOT-095D` và `BOT-095G` đã được mở khóa về precondition ownership; riêng
CancellationToken/progress UI vẫn thuộc phạm vi `BOT-095C`.
