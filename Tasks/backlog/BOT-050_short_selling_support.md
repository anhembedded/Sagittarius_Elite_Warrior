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

Cho short **không** đổi ngữ nghĩa của `BUY`/`SELL` hiện có (xem quyết định
2026-08-19 ở §3) — thêm 2 giá trị `SignalAction` mới (`SHORT`/`COVER`) thay
vì overload `SELL` cho cả "đóng long" lẫn "mở short".

## 3. Các bước thực hiện (Action Items)

- [x] **Chốt ngữ nghĩa** (2026-08-19, đã hỏi user trước khi ghi lại kế hoạch
  này): **không** để `PaperExchange` đoán ý nghĩa của SELL dựa trên vị thế
  hiện tại (đóng Long hay mở Short?) — đây là chuyện strategy phải tự nói rõ
  ý định. `SignalAction` (`src/domain/value_objects/signal_action.py`) có
  thêm 2 giá trị mới: `SHORT` (mở vị thế short) và `COVER` (đóng vị thế
  short) — `BUY`/`SELL` của mọi strategy long-only hiện có (`EmaCrossover`,
  `MultiEmaTrendFollower`) **giữ nguyên nghĩa cũ, không đổi hành vi**. Một
  strategy muốn short chỉ cần tự phát đúng `SHORT`/`COVER` khi nó biết chắc
  ý định, không dựa vào `PaperExchange` suy luận từ vị thế đang mở. `fill()`
  route theo 4 giá trị: `BUY`→mở/thêm Long, `SELL`→đóng Long, `SHORT`→mở
  Short, `COVER`→đóng Short; `HOLD` không đổi. Không cần cơ chế "reverse tự
  động trong 1 signal" — muốn đảo chiều, strategy tự phát 2 signal riêng
  (`SELL` rồi `SHORT`) ở 2 nến/tick khác nhau hoặc cùng nhịp tuỳ logic của
  nó, không phải trách nhiệm của `PaperExchange`.
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
- [ ] `test_sell_with_no_open_position_is_a_no_op` **không cần sửa** — SELL
  giữ nguyên nghĩa cũ (chỉ đóng Long) theo quyết định §3, nên khi Flat nó vẫn
  đúng là no-op như trước. Thêm test mới song song cho `SHORT`/`COVER` thay
  vì sửa test cũ.

## 4. Rủi ro / Lưu ý

- Sai dấu PnL short là lỗi kinh điển và **im lặng** (số vẫn ra, chỉ là sai
  chiều) — test phải có ít nhất 1 kịch bản short thắng và 1 short thua, tính
  tay cả hai.
- `SignalAction` được nhiều nơi dùng (mọi strategy hiện có, `PaperExchange`,
  test batch≡incremental) — thêm `SHORT`/`COVER` là thay đổi **additive**
  (thêm case mới vào `match`/`if` chuỗi xử lý signal, không sửa nhánh
  `BUY`/`SELL` đã có); grep hết mọi nơi switch theo `SignalAction` trước khi
  code để không bỏ sót 1 chỗ im lặng bỏ qua giá trị enum lạ.

## 5. Phụ thuộc

- [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) — SL/TP để đảo
  chiều.
- [`BOT-049`](BOT-049_leverage_and_liquidation.md) — nếu cần liquidation cho
  short (không bắt buộc làm trước).
- [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md) — `Trade` metadata.
