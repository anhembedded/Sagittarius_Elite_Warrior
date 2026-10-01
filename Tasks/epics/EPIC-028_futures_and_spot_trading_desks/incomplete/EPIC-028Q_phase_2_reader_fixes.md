# EPIC-028Q — The Phase 2 readers tell the truth about what they could not read

**Status:** 🔵 Backlog
**Source:** the epic-level review on PR #300 (§3), 2026-10-01. The user agreed on 2026-10-01: *"đồng ý, làm theo đề xuất của bạn"* ("agreed, do as you propose").
**Risk:** 🟡 — history and balance figures shown as complete when they are not
**Complexity:** M — two readers, one refresh service, one gate's wording, fake routes
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028E](../completed/EPIC-028E_open_orders_and_history_readers.md), [EPIC-028F](../completed/EPIC-028F_commission_and_futures_account_controls.md)

---

## 1. Context and problem
The review found these defects in merged Phase 2 code:
1. **Futures order history silently drops orders.** Binance's `allOrders` does not return CANCELED or EXPIRED orders with no fill that are older than 3 days. `i_account_history_reader.py` promises "complete or raise, never truncated", and `HistoryPage` does not disclose the gap.
2. **"Every symbol" history leaves out closed trades.** `active_symbols` takes open positions and open orders only (`futures_history_reader.py`), so a round trip already closed inside the window never appears.
3. **Reader errors escape the port's contract.** Row mapping runs outside `history_read_failures` in both history readers, so a malformed row raises a raw `KeyError` or `InvalidOperation` instead of `AccountHistoryUnavailableError`.
4. **The leverage gate states an exchange fact that may be false.** ADR D7 and `account_control_gate.py` refuse any leverage change while a position is open, as "the rule Binance enforces". Binance may allow raising leverage with a position open; this needs a Testnet check.
5. **Spot rate-limit exposure.** A 7-day read costs 8 windows × weight 20, per symbol, per endpoint, and every page click re-reads the span.
6. **Smaller items:**
   - a negative `cummulativeQuoteQty` becomes a negative average price, where it should be `None`;
   - a failed summary read leaves the last balance on screen with no stale marker;
   - Multi-Assets mode is not read;
   - the Spot commission reader's docstring is wrong about python-binance.

## 2. Acceptance criteria
- [ ] Order history says what it cannot see. A Futures page discloses that unfilled cancelled or expired orders older than 3 days are not returned, and the port's docstring states it as a limit.
- [ ] "Every symbol" includes symbols traded in the window. They come from `/fapi/v1/income` on Futures, and from the trades already read on Spot.
- [ ] Every row mapping runs inside the port's error translation, with a test feeding a malformed row to each reader.
- [ ] The leverage gate's rule is checked on Testnet and either narrowed or documented as the app's own policy.
- [ ] A negative `cummulativeQuoteQty` gives no average price.
- [ ] A failed summary read publishes a stale marker, and the desk shows it.
- [ ] The Spot history cost is bounded (by caching the span per page, or by reading only the page's windows), and a test counts the requests.
- [ ] The fake Futures routes enforce the 7-day span and the 3-day purge, and exercise non-empty `userTrades`.

## 3. Design
To be written when started.

## 4. Changes, per file
To be written when started.

## 5. Testing
- Not run.

## Implementation notes (written when done)
Not started.
