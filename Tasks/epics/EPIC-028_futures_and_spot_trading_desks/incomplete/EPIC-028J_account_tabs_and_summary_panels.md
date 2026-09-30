# EPIC-028J — Each desk has an account summary and bottom tabs: open orders, order history, trade history, positions or assets

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — reuses the existing tables; the change is loading them from queries, not only events
**Complexity:** M — two panels, reuse `ui/order_book/`
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028D](EPIC-028D_account_summary_reader.md), [EPIC-028E](EPIC-028E_open_orders_and_history_readers.md)

---

## 1. Context and problem
- `ui/order_book/` has Positions, Holdings and Open-orders panels; no history tables; no summary.

## 2. Acceptance criteria
- [ ] Tabs: Open orders (cancel one, cancel all — confirmed), Order history, Trade history, and Positions (Futures, with close-at-market) or Assets (Spot).
- [ ] Every tab loads from its query when the desk opens and updates from events of its own venue.
- [ ] A "hide other pairs" toggle filters to the desk's symbol.
- [ ] With "hide other pairs" off, the Order history and Trade history tabs name the pairs they show (`HistoryPage.scanned_symbols`, `EPIC-028E`): Binance needs a symbol per history request, so "every pair" is the venue's active symbols, and a pair closed out with nothing open is not among them. The tab never implies the list is the whole account (PR #297 review, finding 3).
- [ ] Reading every pair stays inside Binance's request-weight limit (6 000 a minute): `IAccountHistoryReader`'s thirty-day bound is per symbol and endpoint, a Spot page of every pair re-reads the span for each active symbol (31 requests × weight 20 per symbol at thirty days, 8 at ADR O5's seven), and each page request reads again. The tabs cache a span behind the port (its listed caching decorator) or cap the pairs scanned with `symbol=None`, and a test shows flipping pages does not re-read the exchange (PR #297 re-review, finding 2).
- [ ] The summary panel shows the `EPIC-028D` figures and refreshes on fills.

## 3. Design
`AccountTabsPanel` (`QTabWidget`) composes the existing panels plus two new history tables; the `DeskProfile` decides Positions vs Assets. `LiveOrderBookCoordinator` grows a load-from-query step.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/account_tabs/` | new (tabs + two history tables + preview) |
| `src/modules/trading/ui/desk/account_summary/` | new |
| `src/modules/trading/ui/live_order_book_coordinator.py` | initial load, venue filter |

## 5. Testing
qtbot per tab; integration: open a desk after placing an order elsewhere — it is listed.
- Not run.

## Implementation notes (written when done)
Not started.
