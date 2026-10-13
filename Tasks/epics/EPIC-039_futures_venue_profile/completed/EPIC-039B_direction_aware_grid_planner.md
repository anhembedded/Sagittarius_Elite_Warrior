# EPIC-039B — The Grid planner knows three directions; Spot is the Long case and the proof

**Status:** ✅ Done (2026-10-13)
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
- [x] `GridParams` gains `direction` (a `TradeDirection`) and `leverage` (int ≥ 1). **Definitions saved before this epic load as LONG/1 through one explicit migration function** (`grid_params.py`, named, tested, logged once per bot at load) — never through a default for new bots: a new Futures definition without these keys is a `GridParamsError` naming the key (`PARAMETERS_WITHOUT_A_DEFAULT` is extended accordingly for Futures profiles, decided with the owner if it changes what the UI leaves blank).
- [x] `GridPlan` gains `direction` and a **signed** `opening_quantity` (`+` buy, `−` sell, `0` none); `opening_buy_quantity` remains as the LONG reading, derived, so no Spot caller changes. Quantities follow DESIGN §5: LONG opens `q·k(P₀)` by market buy; SHORT opens `−q·(N−k(P₀))` by market sell; NEUTRAL opens none.
- [x] **Spot oracle.** For every input in a recorded corpus (the existing planner/simulator unit-test inputs plus ≥ 500 seeded random ones, including prices outside the range and both spacings), the planner with `LONG` and leverage 1 returns the **same** levels, sides, quantities, opening quantity and the simulator the same PnL as the current code. The corpus's expected values are **recorded from the current code in the first commit of this task** (a fixture file) before any change.
- [x] **Position function.** For random price paths over the simulator, for each direction, the position after every fill equals `q·(k(P)−c)` within the step-size rounding the plan declares. Neutral is covered including a path that crosses its starting price repeatedly.
- [x] Counter orders: LONG's SELLs and SHORT's BUYs are marked `reduce_only=True` in the plan; NEUTRAL's are not (DESIGN §5, O10).
- [x] `BaseHandling` → `ExposureHandling` (`KEEP`, `CLOSE_AT_MARKET`) in **one mechanical commit** (D6): every importer in `src/`, `scripts/`, `tests/`; persisted values: if `BaseHandling` values are stored anywhere (check the store codec `grid_runtime_codec.py` and bot snapshots), the stored string stays readable.
- [x] The order sizing for a Futures profile uses `capital_quote × leverage` as the worst-case notional ceiling (O2); for Spot (`leverage = 1`) it is the existing capital rule.
- [x] A direction not in the venue's `VenueProfile.directions` is a REFUSED verdict (`DIRECTION_NOT_ALLOWED`) from `evaluate_grid`, same shape as the other checks.

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
Run: the oracle (682 cases), the planner and position-model tests, the params and verdict tests, `tests/unit/modules/bots`, `tests/integration/modules/bots`, `tests/unit/architecture`, the commit tier and the whole unit tier. The test names above differ from the files: `spot_oracle/test_the_spot_oracle.py`, `test_grid_plan_directions.py`, `test_grid_position_model.py`, `test_grid_params_exposure.py`, `test_grid_direction_allowed.py`. `test_exposure_handling_values_stored_by_the_old_name_still_load` was not written: the value was never stored (see the notes).

## Pitfalls
- The planner **rounds** (BUY down, SELL up, quantities down to `step_size`): the position function holds within one step; a test that asserts exact equality will fail on rounding, not on the model.
- `GridPlan` is `slots=True`/frozen: adding fields changes positional construction everywhere; grep `GridPlan(` in `src/`, `tests/` and `scripts/`.
- Do not change `evaluate_grid`'s Spot verdict *codes* or order (the UI keys on them).
- The renamed enum is imported in the UI and in `use_cases/stop_bot`: the rename commit contains nothing else.

## 3a. Reuse
| Need | Result |
| :--- | :--- |
| A reference for "Spot must not move" | used the `EPIC-037D` sibling-parity idea: `tests/unit/modules/bots/domain/grid/spot_oracle/` records the current planner and replay first (600 plans, 80 seeded replays, hashes stable across re-recording) |
| Order rounding | used `OrderQuantityRoundingPolicy` (the planner's own rounding) |
| The direction value and the venue's allowed set | used `TradeDirection` and `VenueProfile.directions` from `039A` |

## Implementation notes
**Three decisions, all recorded with the coordinator session.**
1. **The Spot replay is not made direction-aware; a small position model is.** `GridReplay` runs the live executor's own reactions (base-denominated fees, paired buy prices, average-cost inventory), so generalising it would rewrite the Spot path the oracle pins. The "direction-aware simulator" the task and `039K` name is `domain/grid/grid_position_model.py`: a pure model with a signed position, average entry, `entry - exit` PnL for a short, no fees. `039K` extends it with funding and liquidation.
2. **The position function needs one base quantity per level.** DESIGN §5's `pos(P) = q * (k(P) - c)` is exact only when every level has the same `q`. Spot's equal-capital sizing does not: from 65,000 up through 66,000 and 67,000 and back to 66,000 the position differs from the first visit to 66,000 (0.06130534 against 0.06153844, the counter BUY is sized by its own level), for LONG too. So `plan()` takes a `LevelSizing`: `EQUAL_CAPITAL` (default, Spot, the oracle) and `EQUAL_QUANTITY` (position venues; sized at the highest level so every order filled at once is worth at most capital x leverage, O2). `039H` must pass `EQUAL_QUANTITY` for a position profile (keyed on the profile's `exposure_kind`). The property test (random paths, both spacings, three directions) is exact; a test pins why equal-capital is not.
3. **The migration logs nothing.** The task asked for a log line per bot at load. A definition saved before the epic is written back without the new keys, so nothing is rewritten and nothing is migrated on disk; a log per parse would be a hot-path INFO line (`logging-rule.md` §6).

- **A quantity that cannot be sent is refused.** `evaluate_grid` takes the `LevelSizing` (default equal capital) and `check_min_notional` answers a level whose quantity rounded to nothing with a REFUSED `LEVEL_BELOW_MIN_NOTIONAL` (before, a zero quantity ended in a division by zero that the planner reported as unreadable parameters, for Spot too: a degenerate input, not in the oracle). A quantity under the minimum notional was already refused. `ExchangeTerms` holds no separate `minQty`; the step and the minimum notional are what it reads.
- **Model, not replay.** `grid_position_model.py` says so in its first lines, and `039H` and `039K` now name the condition: replay the Futures executor, or test the model against it on the same fills.
- `BaseHandling` -> `ExposureHandling` (`KEEP`, `CLOSE_AT_MARKET`) is its own commit. The value was never stored (`StopBotCommand` carries it in memory; the runtime keeps a bool), so no old name needed to stay readable and the "stored by the old name" test was not written.
- `GridPlan.opening_quantity` is signed; `opening_buy_quantity` is the derived LONG reading, so no Spot caller changed. `GridLevel.reduce_only` marks LONG's SELLs and SHORT's BUYs; the Spot executor never reads it.
- `evaluate_grid` answers a direction outside `BotKindInputs.allowed_directions` with `DIRECTION_NOT_ALLOWED`. The default set is the Spot profile's, so no caller changed; `039H` and `039J` pass the profile's.
- **Not done here, by design:** `PARAMETERS_WITHOUT_A_DEFAULT` for Futures (the screen's blanks, `039J`), the O2 bracket cap (needs brackets, `039E`), the account/opening checks for a position venue (`039E`, `039H`). Nothing makes a SHORT or NEUTRAL grid startable: `BOT_MARKETS` is Spot-only and the Spot profile allows LONG only.
- Verified: the oracle is green on the changed planner; mutations of the counter direction, the SHORT sign, the reduce-only rule, the highest-price sizing and the leverage factor each turn a test red; the verdict test is red when the check is removed.
- Not verified here: nothing touched an exchange, and no Futures behaviour exists to observe.
