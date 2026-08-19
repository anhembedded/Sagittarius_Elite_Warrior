# Nhiệm vụ: BOT-042B — `IIndicator.peek_provisional()` + áp cho EMA/RSI/MACD/WMA

> Thuộc Epic [`BOT-042`](../backlog/BOT-042_tick_level_strategy_engine_support.md).
> Phụ thuộc [`BOT-042A`](BOT-042A_provisional_commit_design.md) (design phải
> được duyệt trước). Không phụ thuộc [`BOT-042C`](BOT-042C_series_provisional_slot.md)
> — 2 task này làm song song được.

## 1. Mục tiêu

Thêm `peek_provisional(value) -> T | None` vào contract `IIndicator` và cài
đặt cho cả 4 indicator hiện có (`EMA`, `RSI`, `MACD`, `WMA`) — tính đúng công
thức của `update()` nhưng **không mutate state nội bộ**, gọi được nhiều lần
tuỳ ý trong 1 bar mà không ảnh hưởng gì tới lần `update()` thật tiếp theo.

Chi tiết thiết kế: xem [`Docs/Diagrams/tick_provisional_commit_design.md`](../../Docs/Diagrams/tick_provisional_commit_design.md)
(đã duyệt ở `BOT-042A`) — task này chỉ hiện thực hoá đúng thiết kế đó, không
tự quyết định lại kiến trúc.

## 2. Các bước thực hiện

- [x] `src/domain/indicators/i_indicator.py`: thêm `peek_provisional` vào
      `Protocol`.
- [x] `EMA.peek_provisional()`: đúng công thức `update()` nhánh sau warm-up,
      dùng biến cục bộ thay vì gán `self._ema`. Trong lúc `self._ema is
      None` (đang warm-up), trả `None` — **không** đụng `self._seed_values`.
- [x] `RSI.peek_provisional()`: tương tự — không gán `self._avg_gain`/
      `self._avg_loss`/`self._previous_close`/`self._gain_sum`/`self._loss_sum`.
- [x] `WMA.peek_provisional()`: dựng view tạm từ `self._values` (deque) +
      `value` mới — **không** `append()` vào deque thật. Xử lý đúng 2
      trường hợp: chưa đầy `period` (trả `None`, giống `update()`) và đã đầy
      (dùng `period` phần tử gần nhất tính từ view tạm).
- [x] `MACD.peek_provisional()`: gọi `peek_provisional()` của `_fast_ema`/
      `_slow_ema`, tính `macd_line` tạm, rồi gọi `peek_provisional()` của
      `_signal_ema` — đúng thứ tự `update()` hiện làm, không tự chế logic
      mới.

## 3. Guard test bắt buộc (viết trước khi coi là xong)

- [x] Với từng indicator: gọi `peek_provisional()` N lần bất kỳ (N ngẫu
      nhiên, giá trị ngẫu nhiên), sau đó gọi `update()` — kết quả **phải
      giống hệt** như chưa từng gọi `peek_provisional()` lần nào. Đây là
      bất biến "zero-mutation" — nếu test này fail, nghĩa là
      `peek_provisional()` đã lỡ mutate state.
- [x] Với từng indicator: `peek_provisional(value)` gọi ngay sau khi
      `update()` vừa chốt cùng `value` đó phải trả **kết quả giống hệt**
      giá trị `update()` vừa trả (tính nhất quán công thức).
- [x] Toàn bộ test hiện có của `EMA`/`RSI`/`MACD`/`WMA` phải xanh **không
      sửa 1 dòng nào** — sửa test để nó xanh là dấu hiệu đã phá bất biến
      "đường `update()` không đổi hành vi".

> ✅ **Hoàn thành (2026-08-19)**: 13 test mới (3-4/indicator) + 16 test cũ
> giữ nguyên = 29/29 pass, `ruff check`/`format` sạch. `_compute_rsi()` được
> refactor thành gọi `_compute_rsi_from(avg_gain, avg_loss)` (static method)
> để `update()`/`peek_provisional()` dùng chung công thức mà không trùng
> lặp — bản thân `update()` không đổi hành vi (test cũ xanh không sửa).

## 4. Phụ thuộc

- [`BOT-042A`](BOT-042A_provisional_commit_design.md) — design phải duyệt trước.
- Chặn [`BOT-042D`](../backlog/BOT-042D_strategy_engine_tick_path_and_docs.md).
