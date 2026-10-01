# EPIC-028K — A Futures desk screen: chart, order entry, strategy, account summary and tabs

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — a new route and surface; the old screen stays until `EPIC-028M`
**Complexity:** M — composition only; every part exists by now
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028C](../completed/EPIC-028C_both_venues_running_concurrently.md), [EPIC-028I](EPIC-028I_futures_order_entry_variant.md), [EPIC-028J](EPIC-028J_account_tabs_and_summary_panels.md)

---

## 1. Context and problem
- `trading_view.py` (575-line baseline) and `trading_presenter.py` (978) are the old single screen.

## 2. Acceptance criteria
- [ ] Route `trading.futures`, nav "Futures"; workspace chart, RAIL order entry + strategy card + summary, bottom tabs, EMERGENCY STOP and Enable for this venue only.
- [ ] With Futures not enabled, the screen shows "Futures Testnet not enabled — Settings" and no controls that could send an order.
- [ ] View, presenter and view model are each under 400 lines.

## 3. Design
A `WorkbenchSurface` like the Dev Board (HLD 11 §11.2): docks for RAIL, `QToolBar` for Enable/Emergency Stop.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/futures_desk/` | new MVP trio + screen contribution + preview |
| `src/shell/surfaces.py` | `futures_desk` surface |

## 5. Testing
Sanity route scan; qtbot journey: place a Limit, see it in Open orders, cancel it.
- Not run.

## Implementation notes (written when done)
Not started.
