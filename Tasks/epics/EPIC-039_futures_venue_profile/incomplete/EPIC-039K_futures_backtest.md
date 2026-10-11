# EPIC-039K — A Futures backtest uses Futures candles and counts funding and liquidation

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10; [DESIGN §13](../DESIGN_2026-10-10_futures_venue_profile.md); [decision O9](../DECISION_2026-10-10_futures_venue_profile.md).
**Risk:** 🟡 — a backtest that ignores funding and liquidation flatters a leveraged grid
**Complexity:** L — candles for another market, a funding history source, the simulator's liquidation
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (the Plan's backtest).
**Design:** [DESIGN §5, §6, §13](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§1, §8](../RESEARCH_2026-10-10_futures_grid.md)
**Depends on:** [039B](EPIC-039B_direction_aware_grid_planner.md) (a direction-aware simulator), [039G](EPIC-039G_futures_costs_funding_and_pnl.md) (funding model).

---

## 1. Context and problem
The Grid backtest reads **Spot** candles and Spot filters (`application/queries/run_grid_backtest/handler.py:70,86,97`) and replays them through `domain/grid/grid_simulator.py` (176 lines) with `grid_fill_rule.py`, `grid_replay.py`, `fine_klines.py`. A Futures plan needs its own market's candles, the funding that would have been paid and the liquidation that would have happened.

### Facts verified on `master-warrior` `076d339`
- The three `MarketType.SPOT` constants above; the UI sites `grid_backtest.py:47`, `grid_backtest_presenter.py:262` (039A/039J).
- The simulator's result type: `domain/grid/grid_backtest_result.py`; `buy_and_hold.py` compares against holding; `streamed_fine_klines.py` (application) streams finer candles for fills inside a candle.
- `venue.market_data_venue` decides where a venue's candles are read (`TradingVenue.market_data_venue`, `BUG-172`: the chart shows the market its orders fill in). Futures candles are read by `market_data` through its own port; the funding history is **not** read anywhere today (**to verify** whether Binance's public funding-rate history endpoint is reachable through the gateway; the gateway is `src/support/binance_gateway`).
- Futures MARKET orders and fees are modelled in the manual backtest of the `backtesting` module (`paper_exchange.py`, `OpenPosition`) — a different simulator for strategies; do not merge the two (`EPIC-037` sibling-path rule): read it for formulas, keep the Grid simulator its own.

## 2. Acceptance criteria
- [ ] The backtest query takes the market from the bot's venue profile; Spot results are **identical** to the recorded Spot outputs (039B's fixture).
- [ ] A Futures backtest reads Futures candles for the venue's market-data venue and the symbol's recorded Futures filters/fees; a missing history is `unavailable` with words, never an empty result.
- [ ] **Funding** is charged on the held position at each funding time inside the window from a funding history (source recorded; if none is reachable, the result says "funding not included" prominently and the owner's O9 choice is applied: refuse or warn).
- [ ] **Liquidation** is simulated: when the candle's low (LONG) or high (SHORT) crosses the liquidation price for the position at that moment (isolated margin, the bracket at that notional), the simulation closes the position, forfeits the margin, cancels orders and ends the run with `LIQUIDATED` in the result — checked against `estimated_liquidation_price`.
- [ ] The result reports realized grid profit, funding paid/earned, fees, unrealized PnL at the end, **maximum adverse excursion** (the worst distance to liquidation reached) and a "would have been liquidated" flag; the buy-and-hold comparison for Short/Neutral is defined in the notes.
- [ ] The three directions are covered, and a property test shows: raising leverage never reduces the chance of liquidation on the same path.

## 3. Design
Extend the one simulator with *ports for what differs* (funding schedule, liquidation rule) injected by the profile, the same way costs and risk are; not a Futures copy of the simulator. The simulator stays pure domain (no I/O): funding and candles are passed in.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `application/queries/run_grid_backtest/handler.py` | market and filters by profile |
| `domain/grid/grid_simulator.py`, `grid_pnl.py`, `grid_backtest_result.py` | funding events, liquidation, new result fields |
| `application/services/funding_history_reader.py` (new) | the history source (after verification) |
| `ui/kinds/grid/backtest/*` | show the new fields (with 039J) |

## 5. Testing
Tier: unit (pure simulator), integration with recorded candles.
- `test_a_long_through_its_liquidation_price_ends_liquidated_with_the_margin_lost`
- `test_funding_is_charged_at_each_funding_time_on_the_held_position`
- `test_spot_backtests_are_identical_to_the_recorded_outputs`
- `test_higher_leverage_never_reduces_liquidation_on_the_same_path`
- `test_a_missing_funding_history_is_stated_not_ignored`
Not run yet.

## Pitfalls
- A candle can contain both the liquidating wick and the recovery: the simulator must test the **extreme first** (the existing `fine_klines` mechanism orders sub-candle moves; use it for the check).
- Do not reuse `paper_exchange.py` as the engine (different simulator, different contract); copy formulas only.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: find whether a funding-rate history can be read through `binance_gateway`, and record the endpoint and field names after reading Binance's page.
