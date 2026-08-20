# EPIC-001A — Chuẩn hoá Broker Simulator config cho phép so sánh công bằng với TradingView

**Thuộc:** [EPIC-001](../README.md)
**Trạng thái:** 🔴 Chưa làm.

## Mục tiêu

Trước khi chạy backtest để đối chiếu với TradingView, xác nhận (và nếu cần,
set đúng) toàn bộ config sau trên Backtest screen của app khớp với khai báo
`strategy(...)` gốc trong Pine Script (`BOT-109` §1):

- `pyramiding = 1`.
- Position sizing = 100% equity (`PositionSizingType.PERCENT_OF_EQUITY`,
  giá trị `100.0`) — không phải `RISK_PERCENT`/`FIXED`.
- Commission = 0, slippage = 0 (Broker Simulator modal, `BOT-104`).
- `BrokerSimulationConfig.take_profit_pct` set **riêng**, khớp giá trị với
  `take_profit_percent` của strategy input — nhắc lại gap đã ghi trong
  `BOT-110`: khai báo input không tự động enforce TP, đây là 2 field độc
  lập phải tự đồng bộ tay.
- `BrokerSimulationConfig.stop_loss_pct` = không set (Pine gốc không có SL,
  chỉ có TP + touch-exit) — nếu app đang có SL mặc định nào đó phải tắt đi,
  không thì kết quả lệch vì lý do không liên quan đến strategy.

## Việc cần làm

1. Đọc lại `BrokerSimulationConfig` hiện tại (default trong code +
   giá trị đang set qua Broker Simulator modal) — so với danh sách trên,
   liệt kê cái nào đã đúng sẵn, cái nào cần đổi.
2. Nếu UI đã đủ chỗ để set hết (`OrderExecutionModal.qml`/Broker Simulator
   modal của `BOT-104`) thì không cần code gì — chỉ cần ghi lại đúng các
   bước bấm để tái lập config này mỗi lần so sánh (đưa vào `EPIC-001B`).
3. Nếu thiếu chỗ set 1 trong các field trên qua UI, ghi rõ field nào thiếu
   — quyết định có cần thêm task code riêng hay không, đừng tự ý thêm code
   ngoài phạm vi task này.

## Ngoài phạm vi

Không tự sync lại dữ liệu, không tự chạy backtest — task này chỉ chuẩn hoá
config, việc chạy + đối chiếu là `EPIC-001B`.
