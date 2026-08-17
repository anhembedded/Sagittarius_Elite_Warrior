# Nhiệm vụ: BOT-095H — Quyền sở hữu action Backtest & Chặn callback lỗi thời

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> Phụ thuộc: `BOT-095A` ✅, `BOT-095B` ✅.
> **Precondition bắt buộc của** `BOT-095C`, `BOT-095D`, `BOT-095G`.

## Mục tiêu

Chuẩn hóa vòng đời cho action bất đồng bộ `BACKTEST` và `SYNC`: mỗi intent có
`action_id`/generation, immutable `BacktestRunConfig`, token hủy (nếu có),
trạng thái terminal và thời điểm tạo. Callback chỉ được phép cập nhật UI/FSM
khi còn sở hữu action active. Đây là hàng rào chống kết quả cũ ghi đè run mới.

## Phạm vi kỹ thuật

- Tạo value object nội bộ `BacktestActionContext`: `action_id`, `kind`,
  `config`, `started_at`, `cancellation_token`, `is_cancel_requested`.
- `BackTestPresenter` giữ đúng một active context; thay thế/reset context phải
  invalidate context cũ trước khi submit tác vụ mới.
- Các signal worker mang `action_id`; các slot terminal validate ownership
  **trước** khi mutate ViewModel, dispatch FSM, render chart hoặc auto-run.
- `SYNC_SUCCEEDED` chỉ nối tiếp run của config snapshot ban đầu nếu action đó
  vẫn active; không đọc toolbar hiện tại để suy đoán ý định của người dùng.
- Ghi trace log có `action_id`, kind, config summary và terminal outcome để
  điều tra race mà không log dữ liệu nhạy cảm.

## Ngoài phạm vi

- Không thêm progress/cancel UI (BOT-095C/D).
- Không persist lịch sử run (BOT-095G).

## Acceptance criteria

- `success-after-cancel`, `failure-after-cancel`, `old-success-after-new-run`
  và `sync-success-after-invalidated-config` không thay đổi UI/FSM của action
  hiện tại.
- Cancel/reset idempotent; không có `InvalidStateTransitionError` bị nuốt.
- Focused Presenter tests chạy deterministically với worker/signal giả lập;
  Local CI `-UnitOnly` xanh.

