# EPIC-048D — The other screens cut their bypass imports down against the baseline

**Status:** 🔵 Backlog
**Source:** the owner's delegation of 2026-10-24, settled as G9 of the EPIC-047 charter; the [decision record](../DECISION_2026-10-24_the_ui_reaches_the_application_through_its_doors.md) D3, D4.
**Risk:** 🟡 — many small moves on screens that handle orders (the Trade and Desk areas) and alerts; each must render as before.
**Complexity:** L — 170 of the 215 imports are outside the Bots screen, over the other areas of DERISK §7.3. **Split per screen when started**: one pull request per area, each lowering the baseline.
**Epic:** [EPIC-048](../README.md)
**Depends on:** [EPIC-048A](EPIC-048A_the_doors_rule_and_its_guard.md) (the guard), [EPIC-048C](EPIC-048C_presenters_receive_a_narrow_gateway.md) (the gateway each area uses)

---

## 1. Context and problem
After 048B, the other areas still hold the debt R7 measured at `5ddbd68` (DERISK §7.3): `alerting/ui/options` 65, `trading/ui/desk` 20, `market_data/ui/coordinators` 17, `trading/ui/market` 14, `backtesting/ui/coordinators` 11, `backtesting/ui` 9, `bots/ui/backtest_workbench` 7, `bots/ui/strategies` 8, and nine areas under 5 each. The most imported ports: `IMarketDataSync` 9, `ISymbolCatalog` 8, `IHistoricalKlines` 8, `ICandleFeed` 6 (allowed), `IVenueContexts` 5, `IVenueTradingPorts` 4. 78 of the 110 application imports are data (results, words, enums, constants), 32 are computation (`alerting/ui/options` 14 of them). The numbers move after 048A and 048B; this task re-measures first.

## 2. Acceptance criteria
- [ ] Re-measure with the guard of EPIC-048A and write the per-area counts and an order (largest `fn` and port debt first) in the Implementation notes before the first move.
- [ ] Each area, in its own pull request, reaches its target: 0 `fn`, port and adapter imports outside the allowlist, and `data` imports lowered or justified in the baseline.
- [ ] After each pull request the guard's baseline file shows that area's counts fell, and the full gate is green.
- [ ] No screen changes what it shows: each area's existing tests are unchanged and green, and a frame comparison before and after is identical for the screens the area owns.
- [ ] The Trade and Desk areas keep every order-side confirmation, with the same words (real money).
- [ ] The task is closed when the baseline holds 0 `fn`, port and adapter imports in every area. The `data` line may stay above 0 if the Implementation notes name each remaining import and why a result type belongs to the screen; a follow-up task records the rest.

## 3. Design
The same pattern per area as 048B: a host fact becomes a query or an event; a pure function moves to the application layer; the area's presenter takes its gateway (048C). No new mechanism. The order follows the debt, not the module order.

## 3a. Reuse
For each area: the catalog row or search checked in `.claude/rules/capabilities.md`, then `used <symbol>` or `not used because …`, written per area when the split tasks are created.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/*/ui/…` | per area, written when the area is split |
| `src/modules/*/application/…` | the queries and moved functions each area needs |
| `tests/unit/architecture/baseline_ui_doors.json` | lowered per area |

## 5. Testing
Tier: unit and architecture per area, then the full gate on each pull request. Not run.

## 6. Docs touched
`Docs/MODULES/<module>/` for each module that has a folder, per area, written when the area is split; `none, because …` otherwise.

## Implementation notes (written when done)
Not written: not started.
