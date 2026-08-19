# Nhiệm vụ: Stop Loss / Take Profit + Position Sizing theo Rủi ro

**Trạng thái:** Hoàn thành (19/08) — bước 0 của [Epic BOT-109](../backlog/BOT-109_golden_strategy_ema_trend_confirm_pullback_epic.md).

> Thuộc [Epic BOT-040](BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 1/3** nhóm "PaperExchange nâng cao" (đã chia nhỏ theo yêu cầu user):
> `BOT-041` (file này) → [`BOT-049`](../backlog/BOT-049_leverage_and_liquidation.md) →
> [`BOT-050`](../backlog/BOT-050_short_selling_support.md).
> Phụ thuộc `BOT-021` ✅, nên làm sau [`BOT-045`](BOT-045_trade_journal_detail_and_metadata.md).

## 1. Mục tiêu

Cho `PaperExchange` 2 khả năng cơ bản nhất của quản trị rủi ro, **chưa đụng
đòn bẩy**:

1. **SL/TP tự động đóng vị thế** khi giá chạm ngưỡng — độc lập với tín hiệu
   strategy.
2. **Position sizing theo % rủi ro** thay cho all-in hiện tại.

## 2. Quyết định kiến trúc (không còn mở — đã tự giải quyết)

Task gốc yêu cầu chốt trước: sửa `PaperExchange` hay tạo class mới? Tới lúc
code, `BOT-104` (đã xong trước đó cùng ngày) đã mở rộng trực tiếp
`PaperExchange` cho pyramiding/slippage/commission/position sizing — tiền lệ
đã rõ ràng, nên SL/TP cũng mở rộng trực tiếp `PaperExchange`, không tạo class
mới. Rủi ro hồi quy được kiểm soát bằng cách: mọi field mới (`stop_loss_pct`/
`take_profit_pct` trên `BrokerSimulationConfig`) mặc định `None` — không cấu
hình gì thì hành vi giữ nguyên 100% như trước (đã verify: toàn bộ 19 test cũ
của `BOT-021`/`BOT-104` pass không sửa 1 dòng).

## 3. Triển khai

**Domain value objects:**
- `PositionSizingType.RISK_PERCENT` (mới) — `PositionSizing(type=RISK_PERCENT, value=1.0)` nghĩa là rủi ro 1% equity mỗi lệnh.
- `BrokerSimulationConfig.stop_loss_pct`/`take_profit_pct: float | None = None` — % khoảng cách từ giá vào tới ngưỡng, validate range.

**`PaperExchange`:**
- `_OpenPosition` thêm `stop_loss_price`/`take_profit_price` (giá tuyệt đối, tính 1 lần lúc `_open()` từ % config — không tính lại mỗi bar).
- `check_intrabar_stops(high, low, time) -> Sequence[Trade]` (method **mới**, public) — kiểm tra từng vị thế đang mở, đóng đúng vị thế chạm ngưỡng tại **giá mục tiêu** (không phải `high`/`low`), không trượt giá (khác `fill()` thường). Khi 1 nến chạm **cả** SL lẫn TP: **SL thắng** (giả định bảo thủ, OHLC không nói được thứ tự thật — ghi rõ trong docstring vì ảnh hưởng kết quả).
- Tách `_close_one_position()` dùng chung giữa `_close()` (đóng toàn bộ, dùng cho SELL/force_close) và `check_intrabar_stops()` (chỉ đóng đúng vị thế chạm ngưỡng — quan trọng với pyramiding nhiều vị thế cùng lúc, mỗi vị thế có SL/TP riêng).
- `_calculate_buy_capital()` thêm nhánh `RISK_PERCENT`: `risk_amount = equity * risk% ; quantity = risk_amount / stop_distance`. Từ chối lệnh (capital=0) nếu `stop_loss_pct` chưa cấu hình — sizing này **cần** SL đi kèm, không tự tính được nếu thiếu.

**`RunStaticBacktestCommandHandler`:**
- Gọi `exchange.check_intrabar_stops(candle.high_price, candle.low_price, candle.close_time)` **mỗi bar**, ngay sau khi fill tín hiệu chờ và trước khi hỏi strategy — đây là gap task gốc đã chỉ ra: `fill()` chỉ chạy khi có signal, nên bar không-signal cần đường riêng để SL/TP vẫn được kiểm tra.
- **Chỉ** wiring cho Static — Realtime (`RunRealtimeBacktestCommandHandler`, tick-based) nằm ngoài phạm vi task này.

## 4. Test

19 test cũ (`BOT-021`/`BOT-104`) không sửa, vẫn pass — xác nhận additive,
không hồi quy. 13 test mới trong `test_paper_exchange.py`: khớp đúng giá mục
tiêu (không phải high/low), PnL tính tay, quy tắc SL-thắng-khi-chạm-cả-hai,
no-op khi không cấu hình SL/TP hoặc khi Flat, chỉ đóng đúng vị thế trong
pyramiding chạm ngưỡng (không đóng nhầm vị thế khác), risk-sizing tính tay
(lỗ tại SL đúng bằng đúng % rủi ro đã đặt, theo thiết kế), sizing từ chối khi
thiếu `stop_loss_pct`, validate range của 2 field config mới. 1 test handler
mới (`test_run_static_backtest.py`) chứng minh SL đóng vị thế trên 1 bar
**hoàn toàn không có tín hiệu strategy** nào quanh đó — đúng yêu cầu cốt lõi
của task, không phải test giả.

Mutation-check thủ công 2 chỗ trước khi tin: (1) tạm bỏ dòng gọi
`check_intrabar_stops` khỏi handler → test handler fail đúng lý do → khôi
phục; (2) tạm đảo thứ tự ưu tiên SL/TP trong `check_intrabar_stops` → test
"chạm cả hai" fail đúng lý do → khôi phục.

Full suite (trừ `tests/integration/presentation/ui/` theo quy ước có sẵn):
1495 pass, `ruff` sạch.
