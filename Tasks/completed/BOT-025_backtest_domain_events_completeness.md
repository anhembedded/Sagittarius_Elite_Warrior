# Nhiệm vụ: Backtest Domain Events — Completeness Pass

**Trạng thái:** ✅ Done (2026-09-22), re-scoped — see Implementation notes below.

> Thuộc Epic [BOT-006 — Backtest Engine](../backlog/BOT-006_backtest_engine_execution.md), Cross-cutting. Phụ thuộc `BOT-021` ✅, [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md) (làm **sau** khi cả 2 đã có code thật để rà soát).
>
> 📌 **2026-08-18 — đổi phụ thuộc: `BOT-023` → `BOT-076`.** `BOT-023` (Dynamic) đã bị huỷ ([hồ sơ huỷ](../cancelled/BOT-023_dynamic_backtest_engine.md)). Bộ event cần chuẩn hoá giờ là Static (`BOT-021`) + **Realtime** (`BOT-076`), không còn "Dynamic".

## 1. Mục tiêu (Objective)
Đảm bảo toàn bộ event của tính năng Backtest (cả Static lẫn Realtime) nhất quán, đầy đủ, có tài liệu rõ ràng — tránh mỗi task tự chế event riêng lẻ không đồng bộ.

## 2. Mô tả (Description)
Sau khi `BOT-021` (Static) và `BOT-076` (Realtime) đã triển khai xong phần event của riêng mình, rà soát lại toàn bộ, chuẩn hoá thành 1 bộ chung, đặt tại 1 module duy nhất.

## 3. Các bước thực hiện (Action Items)
- [x] ~~Liệt kê & chuẩn hoá toàn bộ event vào `domain/events/backtest_events.py`: `BacktestRunRequestedEvent`, `BacktestProgressEvent`, `BacktestTradeSimulatedEvent`, `BacktestCompletedEvent`, `BacktestFailedEvent`, `BacktestStoppedEvent`, `BacktestPausedEvent`, `BacktestResumedEvent`.~~ **Re-scoped — xem Implementation notes.** `domain/events/backtest_events.py` chưa từng tồn tại; vị trí thật luôn là `contracts/events/`, và chỉ 2 trong 8 event trên từng được xây.
- [x] ~~Xác nhận Static mode (`BOT-021`) chỉ phát tập con hợp lý...; Realtime mode (`BOT-076`) phát đầy đủ tập trên.~~ **Sai giả định — xem Implementation notes.** Cả 2 mode phát y hệt nhau (`Completed`/`Failed`), không mode nào phát `Progress`/`Paused`/... qua event bus.
- [ ] (Tuỳ chọn, vẫn treo) Nối `BacktestCompletedEvent`/`BacktestFailedEvent` vào `BOT-018` (Notifications) — `BOT-018` vẫn ở backlog, chưa có gì để nối vào.
- [x] Viết tài liệu ngắn mô tả khi nào mỗi event được phát, ai lắng nghe — thành `contracts/events/__init__.py` (vị trí thật của module, không phải `domain/events/`).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đây là task "dọn dẹp/chuẩn hoá" — chỉ nên làm **sau khi** `BOT-021` và `BOT-076` đã có code thật để rà soát, không định nghĩa event trước rồi đoán mò sẽ dùng thế nào.

## Implementation notes (2026-09-22)

Task này đứng yên từ 2026-08-18 chờ `BOT-021`/`BOT-076` có code thật; cả hai đã xong từ lâu, nhưng khi rà soát thật (2026-09-22, đầu batch chứa `BOT-115B`/`BOT-106D`), **toàn bộ giả định của task gốc đều sai**:

- **Vị trí module sai.** `domain/events/backtest_events.py` không tồn tại và chưa từng tồn tại (`grep -rln` xác nhận). Vị trí thật, đã có sẵn từ khi `BOT-021` xây `BacktestCompletedEvent`, là `src/modules/backtesting/contracts/events/` — một file một event, đúng khuôn mọi dataclass khác trong `contracts/`.
- **6 trong 8 event chưa từng được xây.** Chỉ `BacktestCompletedEvent`/`BacktestFailedEvent` tồn tại. `BacktestRunRequestedEvent`, `BacktestProgressEvent`, `BacktestTradeSimulatedEvent`, `BacktestStoppedEvent`, `BacktestPausedEvent`, `BacktestResumedEvent` — không file nào, không import nào, không test nào nhắc tới trong `src/`.
- **Static và Realtime phát y hệt nhau**, không phải "Static chỉ phát tập con, Realtime phát đầy đủ" như task gốc giả định: cả `RunStaticBacktestCommandHandler` lẫn `RunHistoricalTickBacktestCommandHandler` chỉ gọi `event_publisher.publish()` đúng 2 lần khả dĩ — `Completed` khi có `BacktestResult` thật, `Failed` khi không có dữ liệu lịch sử. Không mode nào phát `Progress` qua event bus: cả hai dùng `ProgressThrottle`/`progress_callback` (callable thuần) thẳng tới Presenter — đúng thiết kế vì progress bắn ở tần suất tick/bar, đưa qua domain event bus là làm ngập bus cho một nhu cầu chỉ riêng UI, không bounded context nào khác cần.
- **Cancel không phải event.** Đã có `BacktestCancelled` (`contracts/backtest_cancelled.py`) — một marker giá trị trả về từ `execute()`, không phải domain event. Đúng: hủy là ngắt cục bộ do UI khởi xướng, không phải sự kiện bounded context khác cần biết.
- **Pause/Resume chưa từng tồn tại ở bất kỳ đâu** (`grep -rln "pause\|resume"` trong `src/modules/backtesting/` ra rỗng). Cả hai chỉ có ý nghĩa cho chế độ "Dynamic" — đã huỷ ở [`BOT-023`](../cancelled/BOT-023_dynamic_backtest_engine.md) trước khi từng được xây.

**Việc thật đã làm**, đúng đủ action item #4 (tài liệu hoá) cộng một khoá hồi quy (`architecture-rule.md` §7, "code speaks for itself" — không để lại một đoạn văn không ai đọc lại):
- `contracts/events/__init__.py` (mới) — docstring mô tả đầy đủ: 2 event tồn tại, ai phát (cả 2 handler, đúng 1 lần mỗi loại, cuối `execute()`), ai lắng nghe (chỉ `BackTestPresenter` qua `connect_engine_events`, chỉ để log dev-mode — đường cập nhật UI thật đi qua Qt signal riêng của handler, không qua event bus này), và lý giải từng lý do vì sao 6 event kia không phải lỗ hổng.
- `tests/unit/modules/backtesting/contracts/test_events_catalog.py` (mới, 2 test) — khoá danh sách file trong `contracts/events/` đúng bằng 2 file tài liệu đã nêu (thêm event thứ 3 mà không cập nhật docstring sẽ đỏ ngay), và một tripwire xác nhận docstring còn nhắc đúng tên 2 handler/2 event thật (chống rename âm thầm làm tài liệu lệch). Hành vi publish 2 event đúng lúc đã có sẵn test từ trước (`test_run_static_backtest.py`/`test_run_historical_tick_backtest.py`), không lặp lại ở đây.
- `ruff`/`mypy` sạch trên toàn 646 file `src/`. Bộ test liên quan (`tests/unit/architecture` + `tests/unit/modules/backtesting/application` + `tests/unit/modules/backtesting/contracts`) — 543 pass.
- Mục "Tuỳ chọn" (nối vào `BOT-018`) vẫn treo đúng như task gốc ghi — `BOT-018` chưa xây, không có gì để nối.
