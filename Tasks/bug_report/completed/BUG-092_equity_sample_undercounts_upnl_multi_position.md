# BUG-092 — Equity sample chỉ lấy uPnL của **một** vị thế trong `ACCOUNT_UPDATE`, không cộng dồn — sai số khi mở ≥2 vị thế cùng lúc

**Reported date:** 2026-09-03
**Severity:** 🟠 **P2** — dữ liệu hiển thị/lưu trữ sai: đường cong equity trên biểu đồ và bản ghi
lịch sử phản ánh sai tổng uPnL thật khi tài khoản có nhiều vị thế mở đồng thời.
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`user_data_event_parser.py::account_update_equity_sample()` (cũ) đọc `payload["a"]["P"]`
(danh sách vị thế đổi trong event này) và lấy uPnL từ **phần tử đầu tiên** — một `ACCOUNT_UPDATE`
của Binance Futures có thể mang nhiều vị thế thay đổi trong cùng một event (vd. hai lệnh khớp gần
như đồng thời trên hai symbol khác nhau), và uPnL tổng của tài khoản là tổng uPnL của **mọi** vị
thế đang mở, không chỉ vị thế xuất hiện trong event mới nhất.

## 2. Root cause

`futures_user_data_stream.py::_handle_account_update()` gọi thẳng
`account_update_equity_sample(payload)` mỗi lần nhận `ACCOUNT_UPDATE`, xây `EquitySample` từ đúng
nội dung của **event đó** — không có state nào tích luỹ uPnL của các vị thế khác đang mở nhưng
không xuất hiện trong event hiện tại. Với tài khoản chỉ có 1 vị thế, tình cờ đúng; với ≥2 vị thế,
sai ngay khi event chỉ báo cập nhật 1 trong số chúng.

## 3. Fix

- `user_data_event_parser.py` — xoá `account_update_equity_sample()`; thêm 3 hàm nhỏ hơn, đúng
  một trách nhiệm mỗi hàm: `account_update_position_pnls(payload) -> dict[str, Decimal]` (map
  symbol → uPnL của **các vị thế xuất hiện trong event này**, dùng `.get("up", "0")` — không index
  trần, để không crash trên payload thiếu field), `account_update_wallet_balance(payload) ->
  Decimal | None`, `account_update_captured_at(payload) -> datetime`.
- `futures_user_data_stream.py` — thêm state instance
  `self._unrealized_pnl_by_symbol: dict[str, Decimal] = {}` (reset trong `start()`).
  `_handle_account_update()` giờ `.update()` state này bằng kết quả
  `account_update_position_pnls(payload)` (chỉ ghi đè đúng những symbol event này báo, giữ nguyên
  uPnL các symbol khác), rồi build `EquitySample` với
  `unrealized_pnl=sum(self._unrealized_pnl_by_symbol.values(), Decimal(0))` — tổng cộng dồn thật
  trên mọi vị thế đang biết, không chỉ vị thế trong event mới nhất.

## 4. Regression test

`tests/unit/infrastructure/binance/test_user_data_event_parser.py` — thay
`TestAccountUpdateEquitySample` bằng `TestAccountUpdatePositionPnls`,
`TestAccountUpdateWalletBalance`, `TestAccountUpdateCapturedAt`.

`tests/unit/infrastructure/binance/test_futures_user_data_stream.py`:
- `test_equity_sample_sums_unrealized_pnl_across_positions_not_just_this_event` — gửi hai
  `ACCOUNT_UPDATE` liên tiếp cho hai symbol khác nhau, xác nhận `EquitySample.unrealized_pnl` của
  event thứ hai là **tổng** uPnL cả hai symbol, không phải chỉ symbol trong event đó.
- `test_start_resets_the_running_per_symbol_pnl_total` — xác nhận `start()` không rò state uPnL
  cũ từ phiên trước sang phiên mới.

Xác nhận đỏ trước fix (`unrealized_pnl` của event thứ hai chỉ bằng uPnL riêng symbol đó, thiếu
uPnL của symbol thứ nhất), xanh sau fix.
