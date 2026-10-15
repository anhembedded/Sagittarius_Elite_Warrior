# EPIC-039I — The Futures Grid also runs Short and Neutral

**Status:** 🟡 In progress — **Short** delivered in the first pull request (below); **Neutral** is the second, on top of it
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
- [x] **Short** (first pull request): `IOpeningStrategy` opens a MARKET SELL of the BUY levels' quantity (sliced under the per-order cap), the ladder's BUY counters are reduce-only, the close is a reduce-only MARKET BUY; the risk guard judges the **upper** edge; the stop loss sits **above** the range (the existing `ExitLevel.above`/`below` semantics are mirrored for Short: stop loss above `upper`, take profit below `lower`) — the planner's parameter resolution is direction-aware and tested.
- [ ] **Neutral:** no opening trade; entries on both sides; counters are the neighbouring level and are **not** reduce-only; the position is the signed net; the close flattens in whichever direction the position stands; the guard judges both edges (039F) and refuses if **either** liquidation sits inside the range or beyond its stop.
- [ ] Both directions pass the **same journeys** as Long on the fake (start, partial fill, stream gap, kill and restart, stop, halt-ends-flat, mark wick, out-of-range) — a parametrised suite over `TradeDirection`, not three copies. *(LONG and SHORT: `test_every_direction_passes_the_shared_journeys_on_the_fake_exchange.py`, a row per direction in `futures_direction_scenarios.py`; NEUTRAL is the second pull request's row. Out-of-range is covered at unit level for the direction-free `on_range_exit`, as for Long.)*
- [ ] The position function holds in the executor, not only in the planner *(LONG and SHORT done: `test_the_position_model_agrees_with_the_futures_executor.py`, parametrised)*: after a seeded price path on the fake, the derived position equals `q·(k(P)−c)` within the declared rounding for each direction, and equals the fake's `positionRisk`.
- [ ] A Neutral path that crosses its starting price many times never produces a rejected counter that the bot cannot classify, and ends flat when stopped.
- [ ] Out-of-range for Neutral: above the range the bot is net short at its maximum, below net long at its maximum; `hold`/`close` (O6) apply per side.
- [ ] Spot and Long journeys unchanged and green.

## 3. Design
Nothing new in structure: direction is data of the plan (039B), the collaborators are strategies chosen per direction (039H), the guard is per edge (039F). That is the test of the whole design: if Short or Neutral needs a new branch in a shared file, the seam was wrong and the task stops and reports. Mark in the notes any Neutral behaviour that has no Spot analogue and how it was verified.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/application/services/positions/opening_futures.py`, `closer_futures.py` | direction-aware (a sign) — no new files unless size forces a split |
| `bots/domain/grid/grid_params.py`, `grid_plan.py` | stop-loss / take-profit sides per direction |
| `bots/application/services/risk/risk_guard_futures.py` | per-edge estimates |
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

### Pull request 1 - Short (2026-10-15)
Decisions, all recorded here, none asked, each reversible:
- **Direction was already data; four places were Long's.** The planner, the position model, the replay's positions, the worst-case/liquidation verdicts and the reduce-only flags were direction-aware from 039B/039F/039H, so Short needed no new branch in the executor's shared files (this task's test of the design). What was Long's: (1) the opening was a market BUY (`PositionOpening` now reads the sign of `GridPlan.opening_quantity`; `BotOrderGateway.market_buy_base` became `market_base(side, ...)`); (2) the runtime's books (`grid_reactions` booked a SELL as a cycle's completion and a BUY as an entry, and kept an inventory that cannot go negative); (3) the stop loss and take profit geometry; (4) the profile's `bot_directions`.
- **Books: `GridRuntime.entry_side`** (BUY for Spot and LONG, SELL for SHORT) says which side opens a cycle; the other completes it and books its profit. `inventory` is signed on a SHORT runtime and `cost` is the proceeds of what is held (so `average_cost` is the average entry either way). The arithmetic moved to `grid_books.py` (split from `grid_reactions.py`, which reached 419 lines). It is stored only when it is SELL, so a Spot or LONG file reads and writes the bytes it did. The SHORT book is chosen by `entry_side`, never by the sign of the inventory: a Spot runtime fed a SELL with nothing held (a test of the Spot oracle does exactly that) books as before. `paired_buy_price` keeps its stored name; for a SHORT it is the entry (SELL) price the completing BUY pairs (documented in `grid_runtime.py`).
- **Exits mirror (the task's wording):** a SHORT's stop loss sits above the range (`ExitLevel.above(upper)`) and its take profit below it (`below(lower)`): `GridParams.stop_loss_price` / `take_profit_price` are direction-aware, and `crossed_exit(_in_range)` (the live watch), `futures_leg_events` and `FuturesReplay` (the backtest) read the direction. A SHORT's `take_profit` below the range is reached only after every reduce-only BUY has covered the short, so it ends a flat bot at a profit. The Plan's checks moved with it (`grid_exit_checks.py`, split from `grid_checks.py` at 412 lines): `STOP_LOSS_INSIDE_RANGE` for a SHORT is a stop at or below `upper`; the liquidation verdict's loss exit for LONG and SHORT is the stop loss, and for NEUTRAL (second pull request) its long leg's stop loss and short leg's take profit as 039F built it. The editor marks a SHORT's exit verdicts on the *Stop loss* row (`field_errors(verdicts, direction)`).
- **One sizing for the Plan and the executor: `grid_order_sizing.py`, #518's, and nothing else.** #518 (BUG-212) merged while this was in review; the position ladder's own module this pull request first built was folded into it, so no second module judges a position plan. What #518 already covered for a position ladder: `check_min_notional` and `GridStartSequence` read `find_breach`/`smallest_order`, whose `sized_orders` include the first counter of every pair of neighbouring levels at the one quantity (fee 0), which is what reaches the level left EMPTY at start. What this pull request added to it: `largest_order` and `find_cap_breach` (the per-order cap, which `check_max_notional` now reads for a position ladder from the same orders), and `GridStartSequence._ladder_is_placeable` (which runs for every venue **before** the opening strategy, so before the venue's settings are touched and before any order) calls `find_breach` and, for a position ladder only, `find_cap_breach` (re-review of #521: the first version judged in `PositionOpening` too, a duplicate the sequence already made unreachable). The Plan's verdict normally refuses first, so Start is refused in the Plan's words; the sequence's guard is for a plan that reaches it anyway, and `test_grid_start_cap.py` turns red when it is removed. Spot's branch of `check_max_notional` is unchanged. **Finding that motivated it:** before #518 the Futures check read only the levels that hold an order at the start, but a fill owes its counter at the neighbouring level, so the level left EMPTY (a price near an edge) takes an order too: with a minimum of 375 and a quantity of 0.006, the EMPTY rung at 62,000 is worth 372 and the old check passed on the 378 above it (LONG too). Proof: `test_position_orders_the_reactions_send.py` fills ladders through the real `on_fill`/`on_end` along seeded walks (LONG and SHORT, prices on and near the edges, minimums either side of the cheap rung) and holds every emitted order to the step, the minimum and the cap, with the Plan's verdicts and the executor's `find_breach`/`find_cap_breach` required to agree; it is red without the shared sizing, and a second test shows the walk does reach a breaking order over a plan the old check passed.
- **A resume of a short grid is refused in words, not built** (review of #521). A resume sizes SELL levels to a long inventory (`resized_for_inventory`); the mirror is not part of this pull request. The check is the direction, not what is held: over a flat short it would lay only reduce-only BUYs the exchange refuses. Executor (`GridResumeSequence.propose`) and readiness (`RUN_SHORT_RESUME_UNAVAILABLE`) say "a resume cannot size the position of a short or neutral grid yet; stop the bot (it closes the position) and start a new run"; each locked by a test, with a flat position among the cases. A halted Futures bot is STOPPED, so this is reachable only when a close did not complete. **Price paid, may return** with a resume that sizes BUY levels to the short.
- **The editor offers Short, and shows a direction no bot runs yet greyed out** (review of #521): the Direction rows list the profile's `directions`; one that is not in `bot_directions` (NEUTRAL until the second pull request) is disabled with its reason as the tooltip (`direction_closed_reason`, the pattern of a closed venue, `BUG-208`), so it is never selected and then refused at Start. **The bot's Plan is judged against `exposure_limits_of`** (what a bot may run), not `plan_limits_of` (what a plan or a backtest may name): a saved definition or a plan file naming NEUTRAL shows a REFUSED `DIRECTION_NOT_ALLOWED`, as Start does (`test_the_plan_refuses_a_direction_a_bot_cannot_run_as_start_does`).
- **A flat bot beside a position by hand could neither reconcile nor stop** (found for NEUTRAL, which is flat between cycles, and true of a LONG or SHORT bot whose exits all filled). Trading refuses a registration as `FOREIGN_POSITION` only when the bot's own fills add up to flat; three places read that refusal as "the budget was refused": the reconcile answered a wait with the reason `SWITCH_OFF`, the Stop waited forever in STOPPING, and the close "could not derive the bot's own position". Fixed at each mechanism: the reconcile halts with `FOREIGN_FILL` and the position in words; `GridStopSequence` goes on with that refusal (cancels the bot's orders, closes none of the foreign position); `PositionExposureCloser` treats it as an own position of zero and reports the foreign one. One journey per direction (`test_a_flat_bot_beside_a_position_by_hand_halts_and_stops_leaving_it_open`), a unit test of the close. Spot never answers this refusal, so its stop is unchanged.
- **Tests that encoded Long's geometry for a short were updated**, each with a reason: `test_a_short_is_judged_against_the_exit_above_the_range` (the exit above is the stop loss now), the replay's "take profit closes a short at market" (the exit above is a stop loss; two tests now, one per exit), the profile and limits tests (SHORT is a bot direction), `test_position_opening` (the SELL-coverage sentence names its reduce-only side), and the panel test for an exit verdict on a side (NEUTRAL marks the take profit, SHORT the stop loss).
- **HODL benchmark** of a SHORT runtime is the same capital held short (`grid_pnl._hodl`).

Verification (physically run): commit tier `ci-local.ps1 -SkipTests` PASS; `tests/unit/modules/bots`, `tests/unit/modules/trading` and `tests/unit/architecture` 7,085 passed; `tests/integration/modules/bots` 206 passed (the Spot journeys among them, untouched). Mutation checks: with `entry_side` always BUY, 7 SHORT journeys go red and every LONG one stays green; with the shared sizing off in `check_min_notional`, 7 sizing cases go red; with the opening's `first_breach` off, the executor test goes red. Not verified: nothing was placed on a real exchange; the GitHub `-Full` run is the full gate.

Not done, with the reason: Neutral (second pull request); a resume over a short (above); the Pionex trailing range and extra margin (out of scope, DESIGN §11).

## Resume
Short is in the first pull request. First action for the second (Neutral, on top of it): the books need a position that crosses zero (`grid_books.book_inventory` has a long and a short book; a NEUTRAL runtime needs a signed one), `GridRuntime.entry_side` becomes per-order for a NEUTRAL grid (an order is a completion when it counters an entry), `bot_directions` gains NEUTRAL, `PositionOpening` already opens nothing for a zero `opening_quantity` (verify with the journey), and `futures_direction_scenarios.SCENARIOS` takes a NEUTRAL row.
