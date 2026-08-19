# Nhiệm vụ: Realtime Backtest (BOT-076) làm UI đơ khi chạy — GIL contention, không phải chạy trên UI thread

> Không thuộc epic nào. Người dùng báo cáo trong lúc dùng thật: "làm cơ chế
> chạy realtime tính toán trên 1 thread khác được không, đang chạy trên UI
> thread kìa" — đã verify code trước khi ghi task này, xem §1.

## 1. Đã verify: KHÔNG chạy trên UI thread — nhưng vẫn làm UI đơ

Đọc kỹ [`backtest_presenter.py`](../../src/presentation/ui/screens/backtest/backtest_presenter.py)
và [`thread_manager.py`](../../../sagittarius_engine/infrastructure/thread_manager.py)
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
[`run_realtime_backtest/handler.py`](../../src/application/use_cases/backtest/run_realtime_backtest/handler.py)
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

Theo `.agents/rules/code-rule.md`. Một test tái tạo được sự đơ là khó (không
đo UI responsiveness qua unit test dễ dàng) — tối thiểu cần 1 benchmark script
đo tổng thời gian giữ GIL liên tục (ví dụ đo khoảng cách tối đa giữa 2 lần
main thread có thể acquire GIL trong lúc `_simulate()` chạy) để chứng minh
fix có tác dụng thật, tương tự cách `BUG-009` case study
(`Tasks/reports/BUG-009_logging_and_test_gap_case_study.md`) đã làm cho vấn
đề render — đo trước/sau bằng con số thật, không chỉ "cảm thấy mượt hơn".
