# Nhiệm vụ: BOT-042D — `StrategyEngine` đường nhận tick + sửa lời hứa `BOT-020`

> Thuộc Epic [`BOT-042`](../backlog/BOT-042_tick_level_strategy_engine_support.md).
> Phụ thuộc [`BOT-042B`](BOT-042B_indicator_provisional_contract.md) ✅ và
> [`BOT-042C`](BOT-042C_series_provisional_slot.md) ✅ — cả 2 đã xong.
> **Chặn [`BOT-076`](../in_progress/BOT-076_realtime_backtest_engine.md).**

## 1. Mục tiêu

Thêm vào [`StrategyEngine`](../../src/application/services/strategy_engine.py)
1 đường nhận **tick** (giá + timestamp của bar đang hình thành), tách biệt
khỏi `on_tick(candle)` hiện có (tên đang gây hiểu nhầm — hiện tại nó chỉ
nhận **1 nến đã đóng**, không phải tick thật). Và cập nhật tài liệu
`BOT-020` để không ai hiểu nhầm sự khác biệt Static/Realtime sau `BOT-042`
là bug.

## 2. Các bước thực hiện

- [x] Thêm method mới trên `StrategyEngine`, ví dụ `on_forming_bar_tick(...)`
      (tên chính xác chốt theo `BOT-042A`) — dùng `peek_provisional()` của
      từng `IIndicator` (`BOT-042B`) và `poke_provisional()` của `Series`
      liên quan (`BOT-042C`) thay vì `update()`/`push()`.
- [x] `on_tick(candle)` hiện tại **giữ nguyên hành vi 100%** — cân nhắc đổi
      tên (vd `on_bar_close`) nhưng **đừng đổi hành vi**; nếu đổi tên, giữ
      alias cũ hoặc cập nhật toàn bộ call site trong 1 commit, không để 2
      tên cùng tồn tại mập mờ. **Quyết định: không đổi tên** — rủi ro dò hết
      call site không cần thiết cho phạm vi task này; thay vào đó docstring
      class `StrategyEngine` nói rõ "on_tick, despite its name, only ever
      receives a CLOSED candle" để giảm hiểu nhầm mà không đổi API.
- [x] `_process_one(candle)` (đường bar-close) — **không sửa**.
- [x] Xác nhận `run_batch()` (Static) tuyệt đối không gọi đường tick mới —
      Static chỉ đi qua `update()`/`push()`, không đổi.

## 3. Cập nhật tài liệu — bắt buộc, không phải ghi chú tuỳ chọn

- [x] [`Tasks/completed/BOT-020_indicator_strategy_engine_core.md`](../completed/BOT-020_indicator_strategy_engine_core.md):
      thêm ghi chú rõ ràng ngay cạnh đoạn "Cơ chế đảm bảo batch == incremental"
      (dòng 30) và test `test_batch_and_incremental_produce_identical_signals`
      — nói rõ lời hứa đó **chỉ còn đúng khi không dùng đường tick mới của
      `BOT-042D`**. Dùng đường tick (`peek_provisional`/`poke_provisional`)
      xen giữa các lần `update()`/`push()` có thể khiến Realtime quyết định
      sớm hơn Static trên cùng dữ liệu — **cố ý**, không phải bug.
- [x] Docstring `StrategyEngine` (đoạn *"usable identically in batch...
      incremental mode"*) — sửa cho khớp: đường `run_batch`/`on_tick` cũ vẫn
      đúng lời hứa cũ; đường tick mới thì không, và phải nói rõ vì sao.

## 4. Guard test bắt buộc

- [x] `test_batch_and_incremental_produce_identical_signals` (đã có từ
      `BOT-020`) phải **vẫn xanh, không sửa** — chứng minh đường cũ chưa bị
      đụng.
- [x] Test mới: dựng kịch bản strategy dùng đường tick mới ra quyết định
      **khác** với cùng dữ liệu chạy qua Static — chứng minh sự khác biệt là
      **có chủ đích, đo được, giải thích được** (không phải flaky/random).

> ✅ **Hoàn thành (2026-08-19)**: `StrategyEngine.on_forming_bar_tick()` +
> `_peek_indicators()` mới, docstring class + `BOT-020` doc cập nhật đúng
> §3. 4 test mới trong `test_strategy_engine.py` (reject closed candle,
> zero-mutation, divergence-with-eventual-close, cộng
> `test_batch_and_incremental_produce_identical_signals` xanh không sửa) +
> 318 test `tests/unit/domain/`+`tests/unit/application/` cũ giữ nguyên.
>
> **Phát hiện thật ngoài phạm vi task doc gốc, đã xử lý**: `Series.push()`
> hoá ra được gọi **trực tiếp bên trong `decide()` của từng concrete
> strategy** (`EmaCrossoverStrategy`/`MultiEmaTrendFollowerStrategy`), không
> phải bên trong `StrategyEngine` như task doc ngầm định — nên chỉ sửa
> `StrategyEngine` là chưa đủ, tick path sẽ tính đúng chỉ báo provisional
> nhưng vẫn `push()` thẳng vào `Series` (phá `BOT-042C`). Xử lý bằng cách
> thêm `BaseStrategy.track(series, value, context)` — dispatch `push()` vs
> `poke_provisional()` dựa trên `context.candle.is_closed` (field đã có sẵn
> từ trước, dùng cho live websocket — tái dùng, không thêm field mới vào
> `StrategyContext`). Cả 2 concrete strategy đổi từ gọi `series.push()` trực
> tiếp sang `self.track(series, value, context)` — 9 call site, hành vi
> không đổi (test cũ xanh không sửa) vì `is_closed` mặc định `True`. Thêm
> test end-to-end thật (`test_provisional_ticks_never_leak_into_the_committed_cross_series`
> trong `test_ema_crossover_strategy.py`) chứng minh cả chuỗi
> `StrategyEngine → BaseStrategy.track → Series` không rò rỉ tick tạm vào
> lịch sử đã chốt.

## 5. Phụ thuộc

- [`BOT-042B`](BOT-042B_indicator_provisional_contract.md) ✅ — indicator
  đã có `peek_provisional`.
- [`BOT-042C`](BOT-042C_series_provisional_slot.md) ✅ — `Series` đã có
  ô tạm.
- Chặn [`BOT-076`](../in_progress/BOT-076_realtime_backtest_engine.md) — consumer đầu tiên
  của đường tick mới.
