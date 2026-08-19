# Nhiệm vụ: Triển Khai Chiến Lược "EMA Trend Confirm + Pullback + TP%" (BOT-110)

**Mã Task:** `BOT-110`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog (Chờ triển khai)**  
**Thuộc Epic:** [`BOT-109`](BOT-109_golden_strategy_ema_trend_confirm_pullback_epic.md) (Chuẩn Tham Chiếu Vàng)  
**Phụ thuộc:** [`BOT-050`](BOT-050_short_selling_support.md), [`BOT-105A`](BOT-105A_trailing_stop_and_partial_tp.md)

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
3. **Phát Tín Hiệu (Signal Generation)**:
   - Trả về `Signal(action=SignalAction.BUY, reason="LONG Pullback EMA")` cho Long Entry.
   - Trả về `Signal(action=SignalAction.SELL, reason="SHORT Pullback EMA")` cho Short Entry.
   - Trả về `Signal(action=SignalAction.SELL, reason="Exit Touch EMA Long")` khi nến chạm EMA 200.

---

## 4. Kế Hoạch Kiểm Thử (Test Plan)

- Unit tests trong `tests/unit/domain/strategies/test_ema_trend_pullback_strategy.py`:
  - Test khai báo schema và giá trị mặc định.
  - Test chuỗi nến xác nhận xu hướng tăng (`confirmed_trend == 1`) và giảm (`confirmed_trend == -1`).
  - Test điều kiện reset khi nến chạm EMA dài.
  - Test kích hoạt tín hiệu Pullback Long và Short.
