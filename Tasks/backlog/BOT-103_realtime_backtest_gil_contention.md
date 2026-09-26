# Nhiệm vụ: Realtime Backtest (BOT-076) làm UI đơ khi chạy — GIL contention, không phải chạy trên UI thread

> **Update 2026-09-22 — still in backlog, not done.** Before picking a
> direction, option (a) (`time.sleep(0)` periodically, including this
> task's own suggested N=256) was really measured with a synthetic
> benchmark: it does **not** reduce `max_gap_ms` (the worst-case
> GIL-acquisition gap) at any tested N, and slows the loop by up to +456%
> at N=256. Reverted, never shipped. Full measurements and the
> recommended next direction (option c: profile the real `_simulate()`
> before choosing) are in
> [`Tasks/reports/BOT-103_gil_yield_benchmark_investigation.md`](../reports/BOT-103_gil_yield_benchmark_investigation.md).
> The real module has since been renamed: `run_realtime_backtest/handler.py`
> below is now `run_historical_tick_backtest/handler.py`.
>
> **Update 2026-09-26 — option (c) executed, task still not closed.**
> `scripts/benchmarking/tick_backtest_profile.py` runs a real `cProfile`
> pass over `RunHistoricalTickBacktestCommandHandler.execute()` (real
> strategy/indicator/exchange, no mocks, 600k ticks). Clean result (after
> fixing two methodology traps — see the report): **~42% of total time is
> in the strategy/crossover-detection evaluation path
> (`Series`/`decide`/`evaluate`), and that cost is deliberate by design
> (BOT-042D/BOT-076: re-evaluating every tick, not just at bar close, is
> this handler's entire reason to exist) — not overhead to cut.** No safe
> local optimization target was found. Combined with option (a) already
> being ruled out above, the two remaining directions are (b)
> `ProcessPoolExecutor` (a real architectural change, high risk/effort) or
> accepting the current limitation (~5x the 16.7ms budget) as a known
> constraint — this is a product/risk trade-off decision, not a technical
> choice to make unilaterally within one task-execution pass. Full
> measurements plus the `tottime`/`cumtime` table are in
> [`Tasks/reports/BOT-103_gil_yield_benchmark_investigation.md`](../reports/BOT-103_gil_yield_benchmark_investigation.md)
> §"Update 2026-09-26". Task stays in `backlog/`, awaiting a decision
> between direction (b) or accepting the limitation, before any
> production code changes.

> Không thuộc epic nào. Người dùng báo cáo trong lúc dùng thật: "làm cơ chế
> chạy realtime tính toán trên 1 thread khác được không, đang chạy trên UI
> thread kìa" — đã verify code trước khi ghi task này, xem §1.

## 1. Đã verify: KHÔNG chạy trên UI thread — nhưng vẫn làm UI đơ

Đọc kỹ [`backtest_presenter.py`](../../src/presentation/ui/screens/backtest/backtest_presenter.py)
và `thread_manager.py`
trước khi ghi task này, vì giả thuyết "chạy trên UI thread" trong report có
thể chỉ đúng về triệu chứng (UI đơ) chứ không đúng về nguyên nhân:

- `_on_run_backtest()` gọi `self._thread_manager.submit(self._run_backtest, ...)`
  (`backtest_presenter.py:912`). `IThreadManager` (`thread_manager.py`) là
  `concurrent.futures.ThreadPoolExecutor(max_workers=4)` thật — một OS thread
  riêng, không phải Qt UI thread. Cả 2 nhánh (`RunRealtimeBacktestCommand` lẫn
  `RunStaticBacktestCommand`) đều dispatch bên trong `_run_backtest`, tức
  cùng nằm trên worker thread đó.
- `progress_callback` (`run_realtime_backtest/handler.py:263-268`) đã được
  throttle sẵn — chỉ emit ở tick đầu, tick cuối, và mỗi 256 tick — nên không
  phải do signal Qt cross-thread bắn quá dày làm nghẽn event queue của main
  thread.

**Nguyên nhân thật (đã verify):** `_simulate()` trong
`run_realtime_backtest/handler.py`
là một vòng `for` Python thuần, CPU-bound, không có điểm nhường CPU nào, chạy
tới hàng trăm nghìn lần lặp (ví dụ 7 ngày ở độ phân giải 1 giây = 604,800
tick). Mỗi tick gọi `engine.on_forming_bar_tick()`/`engine.on_tick()`
(`strategy_engine.py:52-78`), tức đánh giá lại strategy/indicator mỗi lần.
Do CPython chỉ có 1 GIL, một worker thread giữ GIL gần như liên tục trong
một vòng lặp Python CPU-bound dài như vậy sẽ khiến main/UI thread — vốn cũng
cần GIL để chạy bất kỳ code Python nào (Qt slot, QML property binding, xử lý
click) — bị đói CPU và phản hồi chậm/đơ, dù về kiến trúc nó **đang** chạy
đúng trên background thread. Đây chính là điều người dùng quan sát được.

## 2. Vì sao đáng làm

Realtime Backtest (BOT-076) là engine chính thức, không phải tính năng phụ —
UI đơ trong lúc chạy (có thể vài giây tới hàng chục giây tuỳ độ dài khoảng
thời gian x độ phân giải tick) làm người dùng tưởng app treo, đặc biệt vì nút
Cancel (mới thêm) cũng cần main thread phản hồi kịp để người dùng bấm được.

## 3. Gợi ý hướng làm (chưa quyết, người nhận task tự chọn)

- **(a) Nhường GIL định kỳ trong vòng lặp** — ví dụ `time.sleep(0)` mỗi N
  tick (đã có sẵn điểm chia N=256 dùng cho progress_callback, có thể tái
  dùng). Rẻ, sửa 1 chỗ, nhưng chỉ giảm mức độ đơ chứ không loại bỏ hẳn GIL
  contention nếu main thread cần nhiều thời gian CPU hơn khoảng nhường.
- **(b) Chuyển việc mô phỏng sang tiến trình riêng** (`ProcessPoolExecutor`
  thay vì `ThreadPoolExecutor` cho riêng lệnh này) — thoát hẳn GIL contention
  với UI thread, nhưng cần `command`/`ticks`/kết quả pickle-able qua ranh giới
  process, và `cancellation_requested`/`progress_callback` (hiện là callable
  Python thuần) phải đổi cơ chế (queue/pipe) vì callable không pickle được
  qua process boundary — việc mới hoàn toàn, rủi ro cao hơn (a).
- **(c) Giảm chi phí mỗi tick** — đo xem `on_forming_bar_tick`/`on_tick` tốn
  bao nhiêu (indicator nào tính lại mỗi lần) trước khi chọn hướng; có thể chi
  phí thật đến từ 1 indicator cụ thể chứ không phải vòng lặp tự nó.

Nên đo thời lượng đơ thực tế trên vài kích cỡ dữ liệu khác nhau trước khi
chọn hướng — (a) có thể đã đủ nếu UI chỉ giật nhẹ, không cần (b).

## 4. Test bắt buộc

Theo `.claude/rules/testing-rule.md`. Một test tái tạo được sự đơ là khó (không
đo UI responsiveness qua unit test dễ dàng) — tối thiểu cần 1 benchmark script
đo tổng thời gian giữ GIL liên tục (ví dụ đo khoảng cách tối đa giữa 2 lần
main thread có thể acquire GIL trong lúc `_simulate()` chạy) để chứng minh
fix có tác dụng thật, tương tự cách `BUG-009` case study
(`Tasks/reports/BUG-009_logging_and_test_gap_case_study.md`) đã làm cho vấn
đề render — đo trước/sau bằng con số thật, không chỉ "cảm thấy mượt hơn".
