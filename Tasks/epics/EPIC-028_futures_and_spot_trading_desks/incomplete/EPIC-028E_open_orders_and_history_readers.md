# EPIC-028E — Each desk loads its open orders, order history and trade history from the exchange

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — history endpoints are weight-heavy; paging and symbol filter must be right first time
**Complexity:** M — three readers × two venues, three queries
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028B](../completed/EPIC-028B_venue_addressed_commands.md), ADR O5

---

## 1. Context and problem
- Nothing reads `allOrders`, `myTrades` (Spot) or `userTrades` (Futures); `EPIC-027` ADR O6 deferred
  `myTrades` (Spot average entry price).
- Open orders reach the UI only through Enable/Emergency Stop results and stream events — a desk
  opened after an order was placed elsewhere shows nothing.

## 2. Acceptance criteria
- [ ] `GetOpenOrdersQuery(venue, symbol | None)` returns the live open orders on screen open.
- [ ] `GetOrderHistoryQuery` and `GetTradeHistoryQuery(venue, symbol | None, since, page)` return the last 7 days paged 50 rows (ADR O5), newest first; trade rows carry price, qty, fee and fee asset.
- [ ] Spot trade history gives an average entry price per held asset (closes EPIC-027 ADR O6).
- [ ] A request that exceeds the exchange's lookback window is split, never silently truncated.

## 3. Design
`IOrderHistoryReader`, `ITradeHistoryReader` (ABC) with Futures (`futures_get_all_orders`, `futures_account_trades`) and Spot (`get_all_orders`, `get_my_trades`) adapters; `TradeRecord` value type; average-entry-price as a pure policy over trade records.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_order_history_reader.py`, `i_trade_history_reader.py`, `trade_record.py` | new |
| `src/modules/trading/adapters/binance/…` | four adapters |
| `src/modules/trading/application/queries/get_open_orders|get_order_history|get_trade_history/` | new queries |
| `tests/.../fakes/binance_fake_server.py` | serve the four endpoints |

## 5. Testing
Unit per adapter; fake-exchange integration; policy test for average entry price (mutation-verified).
- Not run.

## Implementation notes (written when done)
Not started.
