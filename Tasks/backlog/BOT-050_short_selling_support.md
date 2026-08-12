# Nhiệm vụ: Short-Selling (vị thế bán khống)

> Thuộc [Epic BOT-040](BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 3/3** nhóm "PaperExchange nâng cao":
> [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) →
> [`BOT-049`](BOT-049_leverage_and_liquidation.md) → `BOT-050` (file này).
> Phụ thuộc `BOT-041`.

## 1. Mục tiêu

Cho exchange giả lập mở được vị thế **short**. Đây là điều kiện để tab "Bán
(SHORT)" trong bảng Trade Logs và nhãn SHORT trên chart có dữ liệu thật —
hiện tại chúng luôn rỗng vì mọi thứ đều long-only.

## 2. Gap so với code hiện có

`PaperExchange` (`BOT-021`) long-only theo đúng thiết kế:
- `SELL` khi **không** có vị thế → **no-op** (đã có test pin hành vi này:
  `test_sell_with_no_open_position_is_a_no_op`).
- `EmaCrossoverStrategy` (`BOT-026`) cũng long-only — docstring ghi rõ *"SELL
  nghĩa là đóng long, không phải mở short"*.

Cho short nghĩa là **đổi ngữ nghĩa của SELL**, nên phải phân biệt được: SELL
để đóng long, vs SELL để mở short.

## 3. Các bước thực hiện (Action Items)

- [ ] **Chốt ngữ nghĩa trước khi code**: khi đang long mà gặp SELL —
  (a) chỉ đóng long, hay (b) đóng long **và** mở short ngay (reverse)? Đây là
  2 chiến lược giao dịch khác hẳn nhau về kết quả. Pine cho phép cả hai. **Hỏi
  user**, không tự chọn.
- [ ] PnL short đảo dấu: lãi khi giá **giảm**. Dễ sai dấu — tính tay trước.
- [ ] SL/TP cho short **đảo chiều**: SL ở **trên** giá vào, TP ở **dưới**
  (ngược với long). Kiểm tra chạm cũng đảo (`high` cho SL, `low` cho TP).
- [ ] `Trade` thêm `side` (LONG/SHORT) — cột "Loại" trong bảng Trade Logs đọc
  từ đây.
- [ ] Liquidation cho short (nếu `BOT-049` đã xong) — công thức khác long,
  cùng yêu cầu đối chiếu nguồn ngoài.
- [ ] **Cần 1 strategy short-capable để test thật** — `EmaCrossoverStrategy`
  long-only nên không sinh được lệnh short. Dùng scripted test-double (như
  `_ScriptedStrategy` trong `test_run_static_backtest.py` của `BOT-021` đã
  làm) thay vì chờ [`BOT-043`](BOT-043_named_strategy_library.md).
- [ ] Cập nhật test hiện có `test_sell_with_no_open_position_is_a_no_op` —
  hành vi này **thay đổi có chủ đích**, không phải hồi quy. Sửa test kèm ghi
  chú lý do.

## 4. Rủi ro / Lưu ý

- Đây là task **duy nhất trong nhóm làm thay đổi hành vi đã có test pin** —
  cẩn thận phân biệt "phá hồi quy" với "đổi hành vi có chủ đích".
- Sai dấu PnL short là lỗi kinh điển và **im lặng** (số vẫn ra, chỉ là sai
  chiều) — test phải có ít nhất 1 kịch bản short thắng và 1 short thua, tính
  tay cả hai.

## 5. Phụ thuộc

- [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) — SL/TP để đảo
  chiều.
- [`BOT-049`](BOT-049_leverage_and_liquidation.md) — nếu cần liquidation cho
  short (không bắt buộc làm trước).
- [`BOT-045`](BOT-045_trade_journal_detail_and_metadata.md) — `Trade` metadata.
