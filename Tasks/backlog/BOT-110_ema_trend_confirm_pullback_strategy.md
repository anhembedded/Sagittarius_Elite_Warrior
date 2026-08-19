# Nhiệm vụ: Triển Khai Chiến Lược "EMA Trend Confirm + Pullback + TP%" (BOT-110)

**Mã Task:** `BOT-110`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog (Chờ triển khai)**  
**Thuộc Epic:** [`BOT-109`](BOT-109_golden_strategy_ema_trend_confirm_pullback_epic.md) (Chuẩn Tham Chiếu Vàng)  
**Phụ thuộc:** [`BOT-050`](../completed/BOT-050_short_selling_support.md), [`BOT-105A`](BOT-105A_trailing_stop_and_partial_tp.md)

---

## 1. Mục Tiêu

Chuyển thể hoàn chỉnh và chính xác 1:1 mã Pine Script v6 của chiến lược *"EMA Trend Confirm + Pullback + TP%"* sang Python kế thừa `BaseStrategy`.

---

## 2. Các Đầu Vào (Input Parameters)

Khai báo thông qua `self.input_int`, `self.input_float`, `self.input_bool`:
1. `emaLongLen`: Chu kỳ EMA dài (mặc định 200, min 10, max 500, group="Xu hướng dài hạn").
2. `tickConfirm`: Số nến liên tiếp xác nhận (mặc định 5, min 1, max 20, group="Xu hướng dài hạn").
3. `touchSensitivity`: Độ nhạy chạm EMA dài (%) (mặc định 0.0, step 0.1, group="Xu hướng dài hạn").
4. `enableTouchReset`: Reset bộ đếm khi chạm EMA dài (mặc định True, group="Xu hướng dài hạn").
5. `enableTouchExit`: Thoát lệnh khi nến chạm EMA dài (mặc định True, group="Xu hướng dài hạn").
6. `emaEntryLen`: Chu kỳ EMA ngắn vào lệnh (mặc định 50, min 10, max 500, group="Entry").
7. `pullbackSensitivity`: Độ nhạy pullback (%) (mặc định 0.2, step 0.1, group="Entry").
8. `candleConfirmEntry`: Chờ nến đóng xác nhận bật lại (mặc định False, group="Entry").
9. `takeProfitPercent`: % Chốt lời mục tiêu (mặc định 2.0%, step 0.5%, group="Chốt lời").
10. `enableAlerts`: Gửi thông báo (mặc định True, group="Cảnh báo").

---

## 3. Logic Xử Lý & State Machine

1. **Bộ đếm nến & Xác nhận xu hướng**:
   - Duyệt nến qua `context.candle` và `self._prev_candle`.
   - Phát hiện nến chạm EMA dài: `low <= emaUpper and high >= emaLower`.
   - Nếu chạm và `enableTouchReset`: reset `consecutive_bars = 0`, `trend_side = 0`, `confirmed_trend = 0`.
   - Nếu không chạm: đếm số nến liên tiếp đóng trên/dưới EMA dài. Khi `consecutive_bars >= tickConfirm` $\rightarrow$ `confirmed_trend = trend_side`.
2. **Logic Pullback & Bounce**:
   - **LONG**: `confirmed_trend == 1 and low <= entryUpper and close > emaEntry` (kèm điều kiện `low[1] <= entryUpper` nếu `candleConfirmEntry == True`).
   - **SHORT**: `confirmed_trend == -1 and high >= entryLower and close < emaEntry` (kèm điều kiện `high[1] >= entryLower` nếu `candleConfirmEntry == True`).
3. **Phát Tín Hiệu (Signal Generation)** — dùng đúng 4 giá trị `SignalAction`
   riêng biệt cho 4 ý định khác nhau (quyết định 2026-08-19 ở
   [`BOT-050`](../completed/BOT-050_short_selling_support.md) §3: strategy tự nói rõ ý
   định, không để `PaperExchange`/`reason` string đoán):
   - `Signal(action=SignalAction.BUY, reason="LONG Pullback EMA")` cho Long Entry.
   - `Signal(action=SignalAction.SHORT, reason="SHORT Pullback EMA")` cho Short Entry (**không** dùng `SELL`).
   - `Signal(action=SignalAction.SELL, reason="Exit Touch EMA Long")` khi đang Long và nến chạm EMA 200.
   - `Signal(action=SignalAction.COVER, reason="Exit Touch EMA Long")` khi đang Short và nến chạm EMA 200 (Pine's `touchesLong` thoát cả 2 chiều — bản Python cũ chỉ có 1 nhánh SELL nên đã bỏ sót chiều Short, xem `exitByTouch` áp dụng cho cả `strategy.position_size > 0` lẫn `< 0` trong Pine gốc).

> ⚠️ **Câu hỏi kiến trúc chưa chốt, phải giải quyết trước khi code phần
> touch-exit ở trên**: để phát đúng `SELL` (đang Long) hay `COVER` (đang
> Short), strategy phải **biết mình đang ở phía nào** — nhưng
> `StrategyContext` (`src/domain/strategies/strategy_context.py`) hiện
> **hoàn toàn không mang thông tin vị thế** (chỉ có `candle`/`indicators`,
> strategy vốn được thiết kế "position-blind", mọi vị thế do `PaperExchange`
> giữ). Cùng nguyên tắc "strategy tự quyết, engine không đoán" ở
> [`BOT-050`](../completed/BOT-050_short_selling_support.md) §3 đòi hỏi ngược lại ở đây:
> muốn strategy tự quyết đúng, nó cần được **cho biết** vị thế hiện tại, chứ
> không phải tự đoán. Cần chốt trước khi code: thêm trường tuỳ chọn (ví dụ
> `current_position_side: PositionSide | None`) vào `StrategyContext`, hay
> hướng khác? Đây là thay đổi chạm **mọi** strategy hiện có (kể cả những cái
> không cần short), nên phải additive/optional, không phá `IStrategy`/test
> cũ.

---

## 4. Kế Hoạch Kiểm Thử (Test Plan)

- Unit tests trong `tests/unit/domain/strategies/test_ema_trend_pullback_strategy.py`:
  - Test khai báo schema và giá trị mặc định.
  - Test chuỗi nến xác nhận xu hướng tăng (`confirmed_trend == 1`) và giảm (`confirmed_trend == -1`).
  - Test điều kiện reset khi nến chạm EMA dài.
  - Test kích hoạt tín hiệu Pullback Long và Short.
