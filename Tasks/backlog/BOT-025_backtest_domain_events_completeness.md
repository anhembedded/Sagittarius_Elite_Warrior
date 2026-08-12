---
id: "BOT-025"
title: "Nhiệm vụ: Backtest Domain Events — Completeness Pass"
status: "backlog"
---

# Nhiệm vụ: Backtest Domain Events — Completeness Pass

> Thuộc Epic [BOT-006 — Backtest Engine](BOT-006_backtest_engine_execution.md), Cross-cutting. Phụ thuộc `BOT-021`, `BOT-023` (làm **sau** khi cả 2 đã có code thật để rà soát).

## 1. Mục tiêu (Objective)
Đảm bảo toàn bộ event của tính năng Backtest (cả Static lẫn Dynamic) nhất quán, đầy đủ, có tài liệu rõ ràng — tránh mỗi task tự chế event riêng lẻ không đồng bộ.

## 2. Mô tả (Description)
Sau khi `BOT-021` (Static) và `BOT-023` (Dynamic) đã triển khai xong phần event của riêng mình, rà soát lại toàn bộ, chuẩn hoá thành 1 bộ chung, đặt tại 1 module duy nhất.

## 3. Các bước thực hiện (Action Items)
- [ ] Liệt kê & chuẩn hoá toàn bộ event vào `domain/events/backtest_events.py`: `BacktestRunRequestedEvent`, `BacktestProgressEvent`, `BacktestTradeSimulatedEvent`, `BacktestCompletedEvent`, `BacktestFailedEvent`, `BacktestStoppedEvent`, `BacktestPausedEvent`, `BacktestResumedEvent`.
- [ ] Xác nhận Static mode (`BOT-021`) chỉ phát tập con hợp lý (`Requested`/`Completed`/`Failed` — không cần `Progress`/`Paused` vì chạy gần như tức thời); Dynamic mode (`BOT-023`) phát đầy đủ tập trên.
- [ ] (Tuỳ chọn) Nối `BacktestCompletedEvent`/`BacktestFailedEvent` vào `BOT-018` (Notifications) nếu task đó đã hoàn thành, để chạy backtest dài (dynamic) xong có thể báo qua Telegram.
- [ ] Viết tài liệu ngắn (docstring module-level hoặc README nhỏ trong `domain/events/`) mô tả khi nào mỗi event được phát, ai lắng nghe (presenter nào, handler nào).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đây là task "dọn dẹp/chuẩn hoá" — chỉ nên làm **sau khi** `BOT-021` và `BOT-023` đã có code thật để rà soát, không định nghĩa event trước rồi đoán mò sẽ dùng thế nào.
