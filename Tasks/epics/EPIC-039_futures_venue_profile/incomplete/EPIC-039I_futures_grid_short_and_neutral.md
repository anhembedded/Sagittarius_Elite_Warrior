# EPIC-039I — The Futures Grid also runs Short and Neutral

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10; [DESIGN §5](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🔴 — Short mirrors a Long that has been proven; Neutral has no Spot oracle and a net position that crosses zero
**Complexity:** L — mostly planner-driven and already tested in 039B; the executor and the guard learn two more cases
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (Futures section).
**Design:** [DESIGN §5, §6](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§1, §2](../RESEARCH_2026-10-10_futures_grid.md) · **Decision:** O1, O10
**Depends on:** [039H](EPIC-039H_futures_grid_long.md) (a proven Long).

---

## 1. Context and problem
`039B` made the planner know three directions and proved the position function in pure domain; `039H` runs Long. Short is the sign flip of Long (opening MARKET SELL, BUY counters reduce-only); Neutral opens nothing, uses no reduce-only (the net crosses zero), and has **two** liquidation estimates (Pionex and Bitget both show neutral as the safer-looking mode and treat the two sides separately, RESEARCH §1–§2).

### Facts verified on `master-warrior` `076d339` (after 039H these will have changed: re-read)
- The opening, closing and exposure-check collaborators are the seams from 039H; the planner's signed `opening_quantity` and per-order `reduce_only` come from 039B.
- `LiquidationTerms.side` is `PositionSide.LONG` or `SHORT`; `estimated_liquidation_price` is per one position.
- One-way mode nets a long and a short order on one symbol into one position; Hedge Mode is refused (D3).

## 2. Acceptance criteria
- [ ] **Short:** `IOpeningStrategy` opens a MARKET SELL of the BUY levels' quantity (sliced under the per-order cap), the ladder's BUY counters are reduce-only, the close is a reduce-only MARKET BUY; the risk guard judges the **upper** edge; the stop loss sits **above** the range (the existing `ExitLevel.above`/`below` semantics are mirrored for Short: stop loss above `upper`, take profit below `lower`) — the planner's parameter resolution is direction-aware and tested.
- [ ] **Neutral:** no opening trade; entries on both sides; counters are the neighbouring level and are **not** reduce-only; the position is the signed net; the close flattens in whichever direction the position stands; the guard judges both edges (039F) and refuses if **either** liquidation sits inside the range or beyond its stop.
- [ ] Both directions pass the **same journeys** as Long on the fake (start, partial fill, stream gap, kill and restart, stop, halt-ends-flat, mark wick, out-of-range) — a parametrised suite over `TradeDirection`, not three copies.
- [ ] The position function holds in the executor, not only in the planner: after a seeded price path on the fake, the derived position equals `q·(k(P)−c)` within the declared rounding for each direction, and equals the fake's `positionRisk`.
- [ ] A Neutral path that crosses its starting price many times never produces a rejected counter that the bot cannot classify, and ends flat when stopped.
- [ ] Out-of-range for Neutral: above the range the bot is net short at its maximum, below net long at its maximum; `hold`/`close` (O6) apply per side.
- [ ] Spot and Long journeys unchanged and green.

## 3. Design
Nothing new in structure: direction is data of the plan (039B), the collaborators are strategies chosen per direction (039H), the guard is per edge (039F). That is the test of the whole design: if Short or Neutral needs a new branch in a shared file, the seam was wrong and the task stops and reports. Mark in the notes any Neutral behaviour that has no Spot analogue and how it was verified.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/application/services/opening_futures.py`, `closer_futures.py` | direction-aware (a sign) — no new files unless size forces a split |
| `bots/domain/grid/grid_params.py`, `grid_plan.py` | stop-loss / take-profit sides per direction |
| `bots/application/services/risk_guard_futures.py` | per-edge estimates |
| `tests/integration/modules/bots/` | the parametrised direction suite |

## 5. Testing
Tier: unit and integration on the Futures fake. Red first.
- `test_a_short_opens_a_market_sell_and_lays_reduce_only_buys` · `test_a_short_stop_loss_sits_above_the_range`
- `test_a_neutral_bot_opens_nothing_and_lays_entries_on_both_sides`
- `test_the_executor_position_equals_the_position_function_for_each_direction`
- `test_a_neutral_path_crossing_the_start_price_repeatedly_stays_consistent_and_ends_flat`
- `test_neutral_is_refused_when_either_liquidation_is_inside_the_range`
- `test_every_direction_passes_the_shared_journeys` (parametrised)
Not run yet.

## Pitfalls
- One-way mode **nets**: a SELL entry above price and a BUY counter can reduce each other; a Neutral rung whose "counter" would flip the position rather than reduce it must be judged by the planner's position function, not by the order's label.
- Do not copy Long's stop-loss sign into Short; the resolution helpers (`ExitLevel.below/above`) are directional.
- Pionex's trailing range and extra margin are not available for Neutral there (RESEARCH §1): they are out of scope here (DESIGN §11) and not to be added to satisfy symmetry.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: re-read the collaborators 039H created and list what is still Long-specific.
