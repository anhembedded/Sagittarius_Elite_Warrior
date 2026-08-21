# EPIC-003C — `PaperExchange` → Domain Policy (Margin/Matching/Fee)

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** ✅ Hoàn thành 2026-08-22
**Phụ thuộc:** Không có — độc lập hoàn toàn.

---

## 1. Vì Sao Rủi Ro Thấp Nhất Trong Cả 6 Task

Thuần Domain — không đụng PySide6/QML, không có rủi ro lệch binding UI như
mọi task Presentation khác trong epic này. Đã có **56 test bảo vệ sẵn**
cho `PaperExchange` (xác nhận qua `BOT-114`/`BUG-025`/`EPIC-003C` — toàn bộ
suite pass 100% không đổi một assertion nào).

## 2. Thiết Kế (theo `PRO-002` §2.4)

3 Policy tách khỏi `paper_exchange.py`:
- `MarginRiskPolicy`: ký quỹ, Maintenance Margin, Margin Call, Liquidation, leverage, mark-to-market, realized PnL.
- `OrderMatchingPolicy`: khớp lệnh theo nến/tick, intrabar stop (`BOT-041`), slippage, SL/TP target calculation.
- `FeeCalculatorPolicy`: phí Maker/Taker, tính trên notional/contracts theo `CommissionType` (`PERCENT`, `CASH_PER_ORDER`, `CASH_PER_CONTRACT`).

`PaperExchange` giữ vai trò điều phối, gọi vào 3 Policy — không tự tính
toán margin/khớp lệnh/phí trực tiếp nữa.

## 3. Kiểm Thử / Nghiệm Thu

- Toàn bộ 56 test hiện có của `test_paper_exchange.py` pass **không đổi một assertion nào**.
- 3 test suite độc lập cho từng Policy:
  - `tests/unit/domain/backtesting/policies/test_fee_calculator_policy.py`
  - `tests/unit/domain/backtesting/policies/test_order_matching_policy.py`
  - `tests/unit/domain/backtesting/policies/test_margin_risk_policy.py`
- Tổng cộng 119 unit test backtesting domain pass 100%. Full CI suite (1761 primary tests + 50 sanity tests) pass clean.
