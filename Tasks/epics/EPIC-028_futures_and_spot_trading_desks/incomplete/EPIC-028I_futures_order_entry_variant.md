# EPIC-028I — The Futures order entry sets margin mode and leverage, reduce-only, TIF and TP/SL, and shows liquidation, cost and max

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🔴 — TP/SL places extra reduce-only orders on a real exchange; a wrong side opens a position instead of protecting one
**Complexity:** L — variant UI + TP/SL order construction
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028F](../completed/EPIC-028F_commission_and_futures_account_controls.md), [EPIC-028H](../completed/EPIC-028H_order_entry_panel_core_and_spot.md), [EPIC-028O](EPIC-028O_order_contract_and_missing_reads.md) (stop-limit), ADR O2, O3

---

## 1. Context and problem
- `OrderType` already has `STOP_MARKET` / `TAKE_PROFIT_MARKET`; no UI uses them.

## 2. Acceptance criteria
- [ ] Margin-mode chip (Cross/Isolated) and leverage chip dispatch `EPIC-028F`'s commands and show the exchange's answer.
- [ ] Buttons read Buy/Long and Sell/Short; reduce-only checkbox and TIF (GTC/IOC/FOK) map to the order.
- [ ] With TP/SL on, a filled entry is followed by `TAKE_PROFIT_MARKET` and `STOP_MARKET` reduce-only orders on the opposite side (test asserts side and `reduce_only`).
- [ ] The Futures profile offers the Stop-limit tab that `EPIC-028O` adds to the submission path (ADR O3).
- [ ] A market maximum accounts for the open loss against the book, or leaves that margin (`EPIC-028G` §3: not modelled there).
- [ ] TP/SL has one owner with `EPIC-026K`, which builds the same protective orders. The TP and SL placed after an entry are exempt from `MAX_ORDERS_PER_SESSION` and `MIN_ORDER_INTERVAL` (`trading_limits.py`), or they hit the app's own limits (the PR #300 epic review).
- [ ] Liquidation price, cost and max show from `EPIC-028G`, the liquidation value labelled estimate.

## 3. Design
TP/SL construction is a domain policy (`protective_orders_for(entry)`) so the side logic is tested without Qt.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/order_entry/futures_variant.py` | new |
| `src/modules/trading/contracts/protective_orders.py` | new policy |

## 5. Testing
Unit for the policy (both sides, reduce-only); qtbot for the variant; fake-exchange integration placing entry + TP + SL.
- Not run.

## Implementation notes (written when done)
Not started.
