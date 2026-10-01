# EPIC-028O — The order path carries every order the desks offer, and the panels can read every figure they show

**Status:** 🔵 Backlog
**Source:**
- ADR O3: the user, 2026-09-29, stop-limit on both desks (`STOP_LOSS_LIMIT` on Spot, `STOP` on Futures).
- Split out of [EPIC-028H](EPIC-028H_order_entry_panel_core_and_spot.md) on 2026-09-30.
- Widened on 2026-10-01 after the epic-level review on PR #300 (§1, "Plan 028H–N — missing inputs"); the user agreed: *"đồng ý, làm theo đề xuất của bạn"* ("agreed, do as you propose").
- See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).

**Risk:** 🔴 — new order shapes on a real exchange; a wrong trigger direction fills at once instead of waiting
**Complexity:** L — the order model end to end, two payload mappers, the fake exchange, four reads
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028H](EPIC-028H_order_entry_panel_core_and_spot.md)

---

## 1. Context and problem
The epic-level review found that 028H–N cannot be executed as written, because the order path and the reads lack inputs the panels need:
- **The order path.** `PreviewOrderQuery` has no stop price, no time-in-force choice and no quote quantity (`application/orders/preview_order/query.py`). The handler hard-codes GTC and sets a price only for LIMIT. `Order.stop_price` and the Futures mapper support stops, but nothing upstream fills them.
- **Order types.** `OrderType` has no stop-limit member. The Spot mapper accepts MARKET and LIMIT only.
- **Leverage.** Nothing reads the current leverage or the brackets (`symbolConfig`, `leverageBracket`). `LeverageSetting.max_notional` exists only in the answer to a change, so `futures_max_quantity`'s leverage and headroom, and the liquidation estimate's MMR and `cum`, have no source.
- **Prices.** There is no mark price for a flat symbol (`LivePosition.mark_price` only), and nothing reads `bookTicker`. So `FuturesOrderTerms` cannot be filled, and the market-order open loss (`EPIC-028G` §3) cannot be modelled.
- **The app's own limit.** No maximum knows the app's `max_notional_per_order` (`trading_limits.py`), so a 100 % slider can be refused by the app's own gate.

## 2. Acceptance criteria
- [ ] `OrderRequest` and `PreviewOrderQuery` carry an optional stop price, a time-in-force and an optional quote quantity. Preview rounds the stop price to the tick, and the handler no longer hard-codes GTC.
- [ ] `OrderType` gains stop-limit. The Spot mapper sends `STOP_LOSS_LIMIT` with `stopPrice`, and `quoteOrderQty` for a market buy sized by quote. The Futures mapper sends `STOP` with `stopPrice`.
- [ ] A stop price on the wrong side of the last price for its direction is refused before it is sent, with the reason named. It is never sent to trigger at once.
- [ ] The fake exchange accepts both stop orders and fills them when triggered by price, and accepts a quote-quantity market buy. An integration test places each on its venue.
- [ ] Reads on `IOrderEntryTerms`, each a venue-addressed query:
  - the symbol's current leverage and margin type (`symbolConfig`);
  - its brackets (`leverageBracket`);
  - the mark price (`premiumIndex`);
  - the best bid and ask (`bookTicker`);
  - the app's per-order notional limit.

  Spot answers the leverage, bracket and mark reads with "not applicable", never an invented value.
- [ ] Both desk profiles offer the Stop-limit tab with a stop-price field. The Spot market buy sizes by quote amount. The price button can fill the best bid or ask.
- [ ] Every maximum also respects the app's per-order notional limit.
- [ ] Moved from [EPIC-028Q](EPIC-028Q_phase_2_reader_fixes.md): the fake Futures exchange fills a market order and returns it from `userTrades`, so a Futures fill, its trade history and its average entry price are exercised end to end. Existing tests that rely on the fake never filling are updated in the same change.
- [ ] Moved from EPIC-028Q: the Futures account reader reads Multi-Assets mode (`GET /fapi/v1/multiAssetsMargin`), and the desk's available balance names the margin it counts when the mode is on.

## 3. Design
To be written when started.

## 4. Changes, per file
To be written when started.

## 5. Testing
- Not run.

## Implementation notes (written when done)
Not started.
