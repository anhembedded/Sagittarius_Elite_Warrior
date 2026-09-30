# EPIC-028O — Stop-limit orders reach both venues through the one submission path, and the order panel can fill the best bid or ask

**Status:** 🔵 Backlog
**Source:** ADR O3 (the user, 2026-09-29: stop-limit on both desks, `STOP_LOSS_LIMIT` on Spot and `STOP` on Futures), split out of [EPIC-028H](EPIC-028H_order_entry_panel_core_and_spot.md) on 2026-09-30. See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🔴 — a new order type on a real exchange; a wrong trigger direction fills at once instead of waiting
**Complexity:** M — the order model, two payload mappers, the fake exchange, one panel tab
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028H](EPIC-028H_order_entry_panel_core_and_spot.md)

---

## 1. Context and problem
- `OrderType` has no stop-limit member, and `OrderRequest` has no stop price (`contracts/order_request.py`), so no path can send one.
- The Binance order form fills the price from the best bid or ask ("BBO"). Nothing here reads the book; `EPIC-028H`'s panel fills the last price instead.

## 2. Acceptance criteria
- [ ] `OrderRequest` carries an optional stop price. Preview rounds it to the tick. The Spot mapper sends `STOP_LOSS_LIMIT` with `stopPrice`, and the Futures mapper sends `STOP` with `stopPrice`.
- [ ] A stop price on the wrong side of the last price for its direction is refused before it is sent, named, never sent to trigger at once.
- [ ] The fake exchange accepts and fills both, triggered by price; an integration test places one on each venue.
- [ ] `IOrderEntryTerms` reads the best bid and ask (`bookTicker`), and the panel's price button can fill it.
- [ ] Both desk profiles offer the Stop-limit tab, with a stop-price field.

## 3. Design
To be written when started.

## 4. Changes, per file
To be written when started.

## 5. Testing
- Not run.

## Implementation notes (written when done)
Not started.
