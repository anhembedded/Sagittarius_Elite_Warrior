# EPIC-028L — A Spot desk screen: chart, Buy/Sell order entry, strategy, account summary and tabs

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟢 — mirrors `EPIC-028K` with the Spot profile
**Complexity:** M — composition only
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028C](../completed/EPIC-028C_both_venues_running_concurrently.md), [EPIC-028H](../completed/EPIC-028H_order_entry_panel_core_and_spot.md), [EPIC-028J](EPIC-028J_account_tabs_and_summary_panels.md), [EPIC-028O](EPIC-028O_order_contract_and_missing_reads.md) (stop-limit)

---

## 1. Context and problem
- The Spot screen exists today only as the single Trading screen's Holdings branch.

## 2. Acceptance criteria
- [ ] Route `trading.spot`, nav "Spot"; same layout as the Futures desk with the Spot profile (Assets tab, Buy/Sell columns, no leverage).
- [ ] With Spot not enabled, the disabled-venue state as in `EPIC-028K`.
- [ ] Both desks open at once work independently (qtbot: an order, a signal or a chart stream on one never reaches the other; the per-desk stream owner and signal filter come from `EPIC-028K`).
- [ ] Boot re-arms each desk's own saved strategy: `StrategyModule._restore_armed_strategies` widens from the primary venue to every enabled venue a desk shows (`EPIC-028C` restores the primary only, because until now no screen shows or disarms the other venue).

## 3. Design
Same composition as `EPIC-028K`; the difference is only the `DeskProfile` passed in.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/spot_desk/` | new MVP trio + contribution + preview |
| `src/shell/surfaces.py` | `spot_desk` surface |

## 5. Testing
Sanity route scan; qtbot journey Buy → Assets shows the holding.
- Not run.

## Implementation notes (written when done)
Not started.
