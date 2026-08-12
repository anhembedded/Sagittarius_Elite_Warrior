# Nhiệm vụ: Stop Loss / Take Profit + Position Sizing theo Rủi ro

> Thuộc [Epic BOT-040](BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 1/3** nhóm "PaperExchange nâng cao" (đã chia nhỏ theo yêu cầu user):
> `BOT-041` (file này) → [`BOT-049`](BOT-049_leverage_and_liquidation.md) →
> [`BOT-050`](BOT-050_short_selling_support.md).
> Phụ thuộc `BOT-021` ✅, nên làm sau [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md).

## 1. Mục tiêu

Cho `PaperExchange` 2 khả năng cơ bản nhất của quản trị rủi ro, **chưa đụng
đòn bẩy**:

1. **SL/TP tự động đóng vị thế** khi giá chạm ngưỡng — độc lập với tín hiệu
   strategy.
2. **Position sizing theo % rủi ro** thay cho all-in hiện tại.

Đòn bẩy/thanh lý → [`BOT-049`](BOT-049_leverage_and_liquidation.md).
Short-selling → [`BOT-050`](BOT-050_short_selling_support.md).

## 2. Gap so với code hiện có

`PaperExchange` (`src/domain/backtesting/paper_exchange.py`, `BOT-021`):
- All-in: mỗi BUY dồn 100% balance.
- Vị thế **chỉ** đóng khi strategy phát SELL, hoặc `force_close()` cuối
  backtest. Không có cơ chế nào tự đóng theo giá.
- `fill()` chỉ được gọi **khi có signal** — muốn kiểm tra SL/TP mỗi nến thì
  handler phải gọi vào exchange **mỗi bar**, kể cả bar không có tín hiệu. Đây
  là thay đổi ở cả `RunStaticBacktestCommandHandler` chứ không riêng
  `PaperExchange`.

## 3. Các bước thực hiện (Action Items)

- [ ] **Quyết định kiến trúc trước**: sửa `PaperExchange` (thêm param optional)
  hay tạo class mới? Khuyến nghị **class mới** — để đường Static Backtest cơ
  bản (`BOT-021`, đã test kỹ) chạy độc lập, không rủi ro hồi quy. Nhưng nếu
  chọn class mới thì `BOT-049`/`BOT-050` cũng xây tiếp trên nó, không phải
  trên `PaperExchange` gốc.
- [ ] SL/TP: cấu hình bằng **%** (theo mockup: SL 1.2%, TP 3.2%) → quy ra giá
  tuyệt đối tại thời điểm mở lệnh.
- [ ] Kiểm tra chạm SL/TP **mỗi bar**, dùng `high_price`/`low_price` của nến
  (không phải `close_price` — nến có thể xuyên qua SL rồi hồi về, dùng close
  sẽ bỏ sót lệnh đã bị dừng lỗ trong thực tế).
- [ ] **Chốt quy tắc khi 1 nến chạm CẢ SL lẫn TP** — dữ liệu OHLC không nói
  được cái nào tới trước. Quy ước phổ biến (và bảo thủ): **giả định SL trước**.
  Ghi rõ quyết định vào code comment, vì nó ảnh hưởng trực tiếp kết quả
  backtest.
- [ ] Position sizing theo rủi ro: `risk_amount = balance * risk_percent / 100`,
  `quantity = risk_amount / abs(entry_price - stop_loss_price)`. Cần
  `stop_loss_price` **biết trước lúc mở lệnh**, nên SL là điều kiện tiên quyết
  của sizing — 2 mục này không tách rời được, đó là lý do chúng nằm chung task.
- [ ] Ghi `exit_reason` = `STOP_LOSS`/`TAKE_PROFIT` (enum do
  [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md) khai báo sẵn).
- [ ] Handler gọi exchange mỗi bar (không chỉ khi có signal) — sửa
  `RunStaticBacktestCommandHandler`, giữ nguyên quy tắc fill tín hiệu tại
  **giá mở nến kế tiếp** đã có.
- [ ] Test kịch bản tính tay: nến chạm đúng SL → đóng đúng giá SL; chạm TP →
  đóng đúng giá TP; nến chạm cả hai → theo quy ước đã chốt; risk% ra đúng
  quantity.

## 4. Rủi ro / Lưu ý

- Đây là **tính toán tài chính**, sai số nhỏ làm sai lệch toàn bộ kết quả
  backtest. Mỗi công thức tính tay trước, không suy ra từ code.
- Dùng `high`/`low` để phát hiện chạm SL/TP là **xấp xỉ** — nến 4H không cho
  biết giá đi theo trình tự nào trong nến. Đây là hạn chế cố hữu của backtest
  theo nến; dữ liệu tick ([`BOT-042`](BOT-042_tick_level_strategy_engine_support.md))
  mới giải quyết triệt để. Ghi rõ hạn chế này, không giả vờ chính xác tuyệt đối.
- **Không đụng** `PaperExchange`/`Trade`/`BacktestMetrics` gốc và test của
  chúng nếu chọn hướng class mới.

## 5. Phụ thuộc

- `BOT-021` ✅ — `PaperExchange` gốc.
- [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md) — nên làm **trước**,
  để `exit_reason` có sẵn chỗ ghi.
- [`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md) — nơi user nhập SL%/TP%/risk%.
