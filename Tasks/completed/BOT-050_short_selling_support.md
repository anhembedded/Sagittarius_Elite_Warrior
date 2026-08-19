# Nhiệm vụ: Short-Selling (vị thế bán khống)

**Trạng thái:** Hoàn thành (20/08) — bước 1 của [Epic BOT-109](../backlog/BOT-109_golden_strategy_ema_trend_confirm_pullback_epic.md).

> Thuộc [Epic BOT-040](BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 3/3** nhóm "PaperExchange nâng cao":
> [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) ✅ →
> [`BOT-049`](BOT-049_leverage_and_liquidation.md) → `BOT-050` (file này).

## 1. Mục tiêu

Cho exchange giả lập mở được vị thế **short**. Đây là điều kiện để tab "Bán
(SHORT)" trong bảng Trade Logs và nhãn SHORT trên chart có dữ liệu thật —
trước đây chúng luôn rỗng vì mọi thứ đều long-only.

## 2. Quyết định thiết kế đã chốt trước khi code

`BOT-050` tự đặt câu hỏi bắt buộc hỏi user trước khi code: khi đang Long mà
gặp SELL — chỉ đóng Long, hay đóng Long **và** mở Short ngay (reverse)? Khi
hỏi lại, user phản biện đúng hướng: *"không phải đây là chuyện của script
strategy sao ta?"* — tức là **không nên để `PaperExchange` đoán ý định dựa
trên vị thế hiện tại**, mà strategy phải tự nói rõ ý định. Kết quả: thêm
2 giá trị mới vào `SignalAction` — `SHORT` (mở Short) và `COVER` (đóng
Short) — thay vì overload `BUY`/`SELL` cho cả 4 việc. `BUY`/`SELL` của mọi
strategy long-only hiện có (`EmaCrossover`, `MultiEmaTrendFollower`) **giữ
nguyên nghĩa cũ, không đổi hành vi** — xác nhận bằng việc **toàn bộ 45 test
`PaperExchange` cũ (`BOT-021`/`BOT-041`/`BOT-104`) pass không cần sửa 1 dòng**.

Hệ quả kiến trúc: không có cơ chế "reverse tự động trong 1 signal".
`PaperExchange` **từ chối** một entry ở phía ngược lại khi phía kia đang mở
(ví dụ SHORT trong khi đang Long) — strategy muốn đảo chiều phải tự phát 2
signal riêng (SELL rồi SHORT).

## 3. Triển khai

**Domain value objects:**
- `PositionSide` (mới) — `LONG`/`SHORT`.
- `SignalAction` thêm `SHORT`/`COVER`. `BaseStrategy` thêm helper `short()`/`cover()` mirror `buy()`/`sell()`.
- `Trade` thêm field `side: PositionSide = PositionSide.LONG` (default để mọi `Trade(...)` cũ không cần sửa).

**`PaperExchange`** (đại tu có kiểm soát, không đổi hành vi Long):
- `fill()` route theo 4 action: `BUY`→mở/thêm Long, `SELL`→đóng Long, `SHORT`→mở Short, `COVER`→đóng Short.
- `_open()`/`_close()` giờ nhận tham số `side`; từ chối entry phía ngược khi phía kia đang mở (xem §2).
- **Trượt giá đảo chiều đúng cho Short**: mở Short (bán) nhận giá thấp hơn; đóng/cover (mua) trả giá cao hơn — ngược hẳn Long (`_entry_effective_price`/`_exit_effective_price` mới, side-aware).
- **PnL Short**: `(giá_vào - giá_ra) × khối_lượng - phí` — verify bằng suy luận đại số cho thấy công thức này **tương đương cấu trúc** với công thức Long đã có (`net_proceeds - capital_deployed`), không phải một model tài chính khác biệt tự bịa ra.
- **`equity()` mark-to-market cho Short** — đây là chỗ task doc gốc **không** nêu rõ mà tự phát hiện khi code: `equity()` cũ luôn cộng `quantity * mark_price` (đúng cho Long, sai hướng cho Short — giá tăng phải LỖ). Sửa bằng `_mark_to_market()` side-aware: Short = margin giữ lại (`capital_deployed`) cộng/trừ theo `(entry_price - mark_price) * quantity`.
- **SL/TP đảo chiều cho Short**: SL nằm **trên** giá vào (kích hoạt khi `high` chạm), TP nằm **dưới** (kích hoạt khi `low` chạm) — ngược hẳn Long, tái dùng `check_intrabar_stops()` của `BOT-041`.
- **Vốn/margin cho Short**: tái dùng nguyên `_calculate_entry_capital()` (đổi tên từ `_calculate_buy_capital`) cho cả 2 chiều — `capital_deployed` là margin giữ lại (không phải tiền thật chi ra) cho Short, symmetric với cách Long "chi tiền mua".

**Trade Logs UI:**
- `trade_log_filter.py`: tab LONG/SHORT giờ đọc `TradeLogRow.side` thật, không còn no-op.
- `trade_log_row.py`: `TradeLogRow` thêm `side`; nhãn "Loại" đọc `_POSITION_LABEL[side]` ("vị thế mua"/"vị thế bán") thay vì hằng số cố định.

## 4. Test

19 test `test_paper_exchange.py` (13 short-selling mới: PnL thắng/thua tính
tay, no-op khi Cover lúc Flat, từ chối mix Long+Short — **2 test này ban đầu
bị "false pass" 2 lần** (pyramiding mặc định=1 và sizing all-in mặc định che
mất lỗi thật khi tắt guard thử nghiệm — phải sửa lại cấu hình test mới bắt
đúng), equity mark-to-market, slippage đảo chiều, SL/TP đảo chiều + quy tắc
"chạm cả hai" cho Short, risk-sizing symmetric). 1 test handler E2E
(`test_run_static_backtest.py`) chứng minh SHORT/COVER chạy xuyên suốt
StrategyEngine → Handler → PaperExchange thật, không chỉ unit test cô lập.
4 test UI (`trade_log_filter`/`trade_log_row`) xác nhận tab và nhãn SHORT
hoạt động thật.

Mutation-check thủ công 3 chỗ trước khi tin: (1) đảo dấu công thức PnL Short
→ 4 test tính tay fail đúng lý do; (2) tắt guard chặn mix Long+Short → phát
hiện 2 lần "false pass" do cấu hình mặc định che mất lỗi, sửa lại test rồi
mutate lại mới bắt đúng; (3) đảo hướng công thức SL Short → 2 test fail đúng
lý do. Cả 3 khôi phục lại sau khi xác nhận.

**Regression phát hiện muộn**: sửa message log tổng kết `"All positions
closed"` thành `"All {side} positions closed"` làm vỡ 1 integration test có
sẵn (`test_backtest_with_broker_simulation.py`) assert đúng chuỗi cũ — khôi
phục lại chuỗi gốc (thông tin side đã có sẵn trong từng dòng log giao dịch
riêng lẻ phía trên, không cần lặp lại ở dòng tổng kết).

Full suite (trừ `tests/integration/presentation/ui/` theo quy ước có sẵn):
1524 pass, `ruff` sạch.

## 5. Ngoài phạm vi (cố ý chưa làm)

- **Liquidation cho Short** — chờ [`BOT-049`](BOT-049_leverage_and_liquidation.md), chưa xong, không bắt buộc làm trước theo đúng file gốc.
- **Đòn bẩy (leverage) thật** — `BrokerSimulationConfig.short_leverage` đã tồn tại (từ `BOT-104`) nhưng chưa được `PaperExchange` sử dụng ở đâu cả cho cả Long lẫn Short; nằm ngoài phạm vi task này.
