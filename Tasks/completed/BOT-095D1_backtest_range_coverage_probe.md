# Nhiệm vụ: BOT-095D1 — Range Coverage Probe cho Backtest

> Trạng thái: ✅ Hoàn thành 2026-08-17

> Sub-task của `BOT-095D`, tạo 2026-08-17 để đóng dependency kỹ thuật trước
> khi bật 1-click auto-sync.

## Mục tiêu

- Đánh giá dữ liệu đúng khoảng half-open `[start, end)` của lần chạy, theo
  cadence `TimeFrame`; không dùng một nến tồn tại hoặc gap count toàn DB làm
  bằng chứng coverage.
- Báo riêng boundary thiếu đầu/cuối, gap nội bộ, duplicate và nến chưa đóng.
- Trả một DTO immutable để Presenter quyết định preview/sync/run mà không
  diễn giải dữ liệu SQLite trong UI.

## Acceptance

1. Unit test cover đầy đủ, thiếu đầu/cuối, gap nội bộ, duplicate và nến chưa đóng.
2. Probe dùng snapshot config/action, không đọc toolbar ở callback.
3. BOT-095D chỉ auto-run sau khi re-probe trả fully covered.

## Kết quả

- Probe chạy bằng aggregate/window function trong SQLite, không materialize
  toàn bộ OHLCV vào RAM.
- Business DTO giữ đúng half-open `[start, end)`, UTC/cadence, boundary,
  internal gap, duplicate và nến chưa đóng.
- Presenter dùng config/action snapshot; callback cũ bị generation fencing.
