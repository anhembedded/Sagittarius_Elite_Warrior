# EPIC-028L — A Spot desk screen: chart, Buy/Sell order entry, strategy, account summary and tabs

**Status:** ✅ Done (2026-10-02)
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟢 — mirrors `EPIC-028K` with the Spot profile
**Complexity:** M — composition only
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028C](EPIC-028C_both_venues_running_concurrently.md), [EPIC-028H](EPIC-028H_order_entry_panel_core_and_spot.md), [EPIC-028J](EPIC-028J_account_tabs_and_summary_panels.md), [EPIC-028K](EPIC-028K_futures_desk_screen.md), [EPIC-028O](EPIC-028O_order_contract_and_missing_reads.md) (stop-limit)

---

## 1. Context and problem
- The Spot screen exists today only as the single Trading screen's Holdings branch.

## 2. Acceptance criteria
- [x] Route `trading.spot`, nav "Spot"; same layout as the Futures desk with the Spot profile (Assets tab, Buy/Sell columns, no leverage).
- [x] With Spot not enabled, the disabled-venue state as in `EPIC-028K`.
- [x] Both desks open at once work independently (qtbot: an order, a signal or a chart stream on one never reaches the other; the per-desk stream owner and signal filter come from `EPIC-028K`).
- [x] Boot re-arms each desk's own saved strategy: `StrategyModule._restore_armed_strategies` widens from the primary venue to every enabled venue a desk shows (`EPIC-028C` restores the primary only, because until now no screen shows or disarms the other venue).

## 3. Design
- Same composition as `EPIC-028K`; the difference is only the `DeskProfile` passed in. `spot_desk_screen.py` builds the `trading.spot` contribution from `desk_factories` with `TradingVenue.SPOT_TESTNET`. Spot's profile already hides leverage, labels the sides Buy/Sell, offers Assets instead of Positions and says why TP/SL is unavailable (`EPIC-026K`, ADR O2). The presenter builds no TP/SL follower on Spot.
- **Restore on every enabled venue.** `_restore_armed_strategies` loops over `IVenueContexts.enabled()`, each venue through its own arming. One venue's bad saved config is logged and left disarmed by `_arm_from_config`, and never keeps the other venue from coming back.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/desk_screen/spot_desk_screen.py` | new: the Spot route |
| `src/modules/trading/module.py` | contributes the Spot desk |
| `src/modules/strategy/module.py` | the restore covers every enabled venue |

## 5. Testing
- Unit:
  - `test_two_desks_stay_apart.py` — both desks on one bus and one market stream. An order on Spot lists on Spot only; a Spot signal reaches Spot's card only and a backtest's reaches neither; enabling Futures leaves Spot local, then each streams its own market under its own owner; an Emergency Stop on Spot leaves Futures enabled.
  - `test_spot_desk_journey.py` — Buy through the panel's controls, then Assets shows the bought asset.
  - `test_module_restores_each_venues_strategy.py` — each enabled venue re-arms its own saved strategy, and one venue's refused config leaves the other armed.
- Sanity: the route scan and every navigable route constructing, both green.
- Mutation-checked, each turning a test red:
  - the restore cut back to the first venue (two tests);
  - the desk's feeds built for Futures whatever the venue (two tests).

## Implementation notes (written when done)
- **The old test that locked "primary only" was replaced, not weakened.** It asserted Spot's saved strategy stayed unarmed because no screen showed it (the PR #295 review, F3). Now that the Spot desk shows and stops it, the test asserts both venues come back armed, each with its own configuration. A new test pins that a refused venue does not stop the other.
- **The Spot desk's TP/SL stays unavailable** until `EPIC-026K` (ADR O2). The panel says so; the desk builds no follower.
- **The single Trading screen and the Dev Board still show the primary venue only.** Both desks sit beside them until `EPIC-028M` retires the single screen.
