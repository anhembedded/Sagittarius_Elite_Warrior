# EPIC-029D — A Grid configuration can be replayed on real candles, against buy-and-hold, under a stated fill rule

**Status:** 🔵 Backlog
**Source:** [`PRO-006`](../../../proposal/PRO-006.md). The user chose 2026-10-03, *"Có, nhưng chạy
song song"*: build it in parallel with the live bot, and require it before mainnet. The report's own
caveat is *"dữ liệu giả lập … khớp lệnh ngay khi chạm giá"* ("simulated data … fills on touch").
The design is in ADR D14 and D18.
**Risk:** 🟡 — a simulator that fills too generously gives false confidence. The fill rule is the
main risk, and every result must state it.
**Complexity:** L — a new event-driven simulator, two-resolution data loading, a result type, and a
result view in the Bots tab.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029C` (`GridPlan`) and `EPIC-029G` (the overlay, for the result chart).
**Not** on the fast track's critical path: it runs in parallel with `EPIC-029E` and `EPIC-029F`.

---

## 1. Context and problem

The backtest engine fills strategy signals at the next candle. It has no resting orders and one
flat fee (`backtesting/ui/logic/backtest_limitations_view.py:21-40`;
`backtesting/contracts/broker_simulation_config.py:36-37`). No stored aggTrades exist. The
finest data is 1-second klines (`backtesting/application/run_historical_tick_backtest/handler.py:118-143`).
Buy-and-hold is computed nowhere.

## 2. Acceptance criteria

- [ ] **The simulator.** `simulate_grid(plan, candles, fine_candles, rule) -> GridBacktestResult`
  replays a plan:
  - the opening buy at the first candle's open, with the taker fee;
  - ladder fills by the fill rule, with the maker fee;
  - the counter order placed on each full fill;
  - stop loss and take profit exits at market, with the taker fee.
- [ ] **The fill rule** (D14):
  - a BUY at L fills only when `low ≤ L − tick`, and a SELL only when `high ≥ L + tick`;
  - the order of levels within a candle comes from its 1-second klines;
  - within one 1-second kline a level fills at most once.

  `result.fill_rule` names the rule, and the result view shows it.
- [ ] **Without fine data.** When 1-second klines are missing for a period, the simulator falls
  back to the conservative order (adverse side first). It marks the affected candles in
  `result.coarse_periods`, and never silently.
- [ ] **The result.** `GridBacktestResult` carries:
  - the equity curve, plus a buy-and-hold curve on the same timestamps (D18);
  - grid profit (closed cycles) separated from unrealised profit and loss;
  - the cycle count and the fill list;
  - the stop reason (none, stop loss, take profit or end of data);
  - the fee totals by maker and taker;
  - the fill rule and the coarse periods.
- [ ] **Synthetic regimes.** The simulator is replayed on synthetic paths that reproduce the
  report's four regimes: ranging, uptrend, downtrend and crash-then-recovery. Each shows the
  report's qualitative outcome: in the uptrend the grid trails buy-and-hold, and in the downtrend
  the stop loss limits the loss. These are regression fixtures, not real-data claims.
- [ ] **The chart is `BotChart`** (`EPIC-029G`, ADR D16). The backtest result hosts a `BotChart` and draws its
  candles with `draw_history` and its overlay with `show_overlay`, never through a drawer of its own, so
  the backtest and the running bot cannot draw a Grid differently (the PR #321 review).
- [ ] **Running it from the planner.** In the Bots tab, "Backtest" on the Grid panel runs the
  current parameters over a chosen period. It shows:
  - the result chart (candles, levels, fills, stop loss and take profit, through `EPIC-029G`'s
    overlay);
  - the equity against buy-and-hold;
  - the summary numbers.

  It runs on a worker with cancellation and fencing (`async-ui-action-rule.md`). A cancelled run
  publishes nothing.
- [ ] **Missing data.** When the chosen period's candles are not stored locally, the planner
  offers to sync them through the existing sync port. It never fetches silently (`BUG-107`:
  opening a screen is not a network request).

## 3. Design

- **Shared with live.** The simulator lives in `bots/domain/grid/grid_simulator.py` and is pure. It
  reuses the same level state machine as the live executor (ADR §3.2), so the backtest and live
  agree on what a fill means.
- **Data.** It is loaded in `bots/application/queries/run_grid_backtest/` through `market_data`
  contracts: `IHistoricalKlines` for the bar candles and the repository's fine-resolution stream
  for 1-second klines, which is the same source the historical-tick run uses.
- **Fees** come from the plan's fee inputs, which the planner seeded from `order_entry_terms` when
  online and which the user can edit.
- **The view** is a coordinator owned by the Bots presenter. It is not a reuse of the Backtest
  screen, which is strategy-shaped and cannot be imported (`backtesting/ui`).

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_simulator.py`, `grid_backtest_result.py`, `buy_and_hold.py` (new) | simulator, result, comparison |
| `src/modules/bots/application/queries/run_grid_backtest/` (new) | data loading + simulate |
| `src/modules/bots/ui/coordinators/grid_backtest_coordinator.py` (new) | worker, fencing, cancel |
| `src/modules/bots/ui/grid_backtest_view.py` (new) | result chart and summary |
| `tests/unit/modules/bots/domain/grid/test_grid_simulator*.py` (new) | fill-rule boundaries, four regimes, fees |

## 5. Testing

Unit tests:

- the fill rule at exactly `L − tick` and at `L` (no fill on touch);
- multiple crossings inside one candle, with and without fine data;
- the fee split;
- each stop reason;
- the four synthetic regimes as fixtures.

Integration test: a stored week of 1-minute and 1-second klines from the test fixtures, through
the query.

UI test: running, cancelling, and stale-result fencing with `qtbot`.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
