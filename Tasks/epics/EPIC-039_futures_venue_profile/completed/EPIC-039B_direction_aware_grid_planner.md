# EPIC-039B — The Grid planner knows three directions; Spot is the Long case and the proof

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10; [DESIGN §5](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🟡 — pure domain, but it changes the type every Grid file imports; the Spot oracle is what makes it safe
**Complexity:** L — planner, plan, simulator, params, a rename across the tree, a property test
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) — unchanged for Spot; a "direction" row is added for the screen in `039J`.
**Design:** [DESIGN §4, §5](../DESIGN_2026-10-10_futures_venue_profile.md) · **Decision:** D2, D6, O2 ([record](../DECISION_2026-10-10_futures_venue_profile.md))
**Depends on:** [039A](EPIC-039A_venue_profile_seam.md) (`TradeDirection`).

---

## 1. Context and problem
The planner builds a ladder whose SELL levels are covered by an opening MARKET BUY (`domain/grid/grid_plan.py`: "A SELL level sells base bought by the opening purchase … The opening purchase is the total quantity of the SELL levels"). Short and Neutral need a different opening exposure; the level prices, spacing and counter-order rule are the same. The research model (DESIGN §5): a ladder is a position function of price, `position(P) = q·(k(P) − c)`, and the three directions are three values of `c`.

### Facts verified on `master-warrior` `076d339`
- `domain/grid/grid_plan.py`: `LevelSide` (BUY/SELL/EMPTY), `GridLevel(index, price, side, quantity)`, `GridPlan` with `opening_buy_quantity`, `sell_levels`, `order_levels`, `last_price`; prices rounded by side to `tick_size` (BUY down, SELL up); the level nearest the price stays EMPTY within half a step.
- `domain/grid/grid_params.py`: parsed from `BotDefinition.config` string keys `lower, upper, grid_count, spacing, capital_quote, stop_loss, take_profit`; "no field has a hidden default"; `PARAMETERS_WITHOUT_A_DEFAULT = {lower, upper, capital_quote}`; `GridParamsError` names the key.
- `domain/grid/grid_simulator.py` (176 lines), `grid_pnl.py` (68), `grid_replay.py`, `grid_fill_rule.py`, `grid_level_fsm_matrix.py` — the backtest and the level FSM.
- `BaseHandling` (`KEEP`, `SELL_AT_MARKET`) is in `contracts/i_bot_executor.py` and used by `grid_stopper.py`, `grid_price_reaction.py`, the use cases `stop_bot`, the UI.
- Existing bot definition files on disk have **no** `direction` or `leverage` key.

## 2. Acceptance criteria
- [ ] `GridParams` gains `direction` (a `TradeDirection`) and `leverage` (int ≥ 1). **Definitions saved before this epic load as LONG/1 through one explicit migration function** (`grid_params.py`, named, tested, logged once per bot at load) — never through a default for new bots: a new Futures definition without these keys is a `GridParamsError` naming the key (`PARAMETERS_WITHOUT_A_DEFAULT` is extended accordingly for Futures profiles, decided with the owner if it changes what the UI leaves blank).
- [ ] `GridPlan` gains `direction` and a **signed** `opening_quantity` (`+` buy, `−` sell, `0` none); `opening_buy_quantity` remains as the LONG reading, derived, so no Spot caller changes. Quantities follow DESIGN §5: LONG opens `q·k(P₀)` by market buy; SHORT opens `−q·(N−k(P₀))` by market sell; NEUTRAL opens none.
- [ ] **Spot oracle.** For every input in a recorded corpus (the existing planner/simulator unit-test inputs plus ≥ 500 seeded random ones, including prices outside the range and both spacings), the planner with `LONG` and leverage 1 returns the **same** levels, sides, quantities, opening quantity and the simulator the same PnL as the current code. The corpus's expected values are **recorded from the current code in the first commit of this task** (a fixture file) before any change.
- [ ] **Position function.** For random price paths over the simulator, for each direction, the position after every fill equals `q·(k(P)−c)` within the step-size rounding the plan declares. Neutral is covered including a path that crosses its starting price repeatedly.
- [ ] Counter orders: LONG's SELLs and SHORT's BUYs are marked `reduce_only=True` in the plan; NEUTRAL's are not (DESIGN §5, O10).
- [ ] `BaseHandling` → `ExposureHandling` (`KEEP`, `CLOSE_AT_MARKET`) in **one mechanical commit** (D6): every importer in `src/`, `scripts/`, `tests/`; persisted values: if `BaseHandling` values are stored anywhere (check the store codec `grid_runtime_codec.py` and bot snapshots), the stored string stays readable.
- [ ] The order sizing for a Futures profile uses `capital_quote × leverage` as the worst-case notional ceiling (O2); for Spot (`leverage = 1`) it is the existing capital rule.
- [ ] A direction not in the venue's `VenueProfile.directions` is a REFUSED verdict (`DIRECTION_NOT_ALLOWED`) from `evaluate_grid`, same shape as the other checks.

## 3. Design
Direction is *data* of the plan, not a class hierarchy: one `plan_grid(params, terms, last_price)` with the direction determining the opening exposure and the side of the counters; nothing else forks (open/closed: a new direction is one `TradeDirection` member and one opening rule). The oracle makes the refactor safe by construction — the repository's own pattern for risky equivalence (`EPIC-037D` sibling parity). If the property test **disproves** the position-function model for Neutral, **stop and report** to the owner with the counter-example before building anything on it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `domain/grid/grid_params.py` | `direction`, `leverage`; the explicit legacy migration |
| `domain/grid/grid_plan.py` | direction, signed opening quantity, reduce-only marks |
| `domain/grid/grid_simulator.py`, `grid_pnl.py`, `grid_replay.py` | direction-aware fills; PnL for a short is `entry − exit` |
| `domain/grid/grid_checks.py` (+ `grid_account_checks.py`) | `DIRECTION_NOT_ALLOWED`; the opening-buy check becomes an opening-exposure check |
| `contracts/i_bot_executor.py` and every user of `BaseHandling` | `ExposureHandling` |
| `tests/unit/modules/bots/domain/grid/` | the oracle fixture, the property tests |

## 5. Testing
Tier: unit (pure domain). Every test is shown red before its change where it can be (the oracle test is green on day one and **stays** green: it is the guard; the property tests are red until the planner knows directions).
- `test_long_at_leverage_one_reproduces_the_recorded_spot_plan_and_pnl` (corpus fixture)
- `test_position_equals_q_times_k_minus_c_for_each_direction` (seeded paths; neutral crosses zero)
- `test_short_opens_a_market_sell_of_the_buy_levels_quantity` · `test_neutral_opens_nothing`
- `test_long_counters_are_reduce_only_and_neutral_counters_are_not`
- `test_a_definition_saved_before_the_epic_loads_as_long_one` · `test_a_new_futures_definition_without_direction_names_the_key`
- `test_a_direction_the_venue_does_not_allow_is_refused`
- `test_exposure_handling_values_stored_by_the_old_name_still_load`
Not run yet.

## Pitfalls
- The planner **rounds** (BUY down, SELL up, quantities down to `step_size`): the position function holds within one step; a test that asserts exact equality will fail on rounding, not on the model.
- `GridPlan` is `slots=True`/frozen: adding fields changes positional construction everywhere; grep `GridPlan(` in `src/`, `tests/` and `scripts/`.
- Do not change `evaluate_grid`'s Spot verdict *codes* or order (the UI keys on them).
- The renamed enum is imported in the UI and in `use_cases/stop_bot`: the rename commit contains nothing else.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: commit the recorded oracle fixture from the **current** planner and simulator, then the guard test that reads it.
