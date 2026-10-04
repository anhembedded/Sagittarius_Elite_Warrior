# EPIC-029D — A Grid configuration can be replayed on real candles, against buy-and-hold, under a stated fill rule

**Status:** ✅ Done (2026-10-04), PR6
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

- [x] **The simulator.** `simulate_grid(plan, candles, fine_candles, rule) -> GridBacktestResult`
  replays a plan:
  - the opening buy at the first candle's open, with the taker fee;
  - ladder fills by the fill rule, with the maker fee;
  - the counter order placed on each full fill;
  - stop loss and take profit exits at market, with the taker fee.
- [x] **The fill rule** (D14):
  - a BUY at L fills only when `low ≤ L − tick`, and a SELL only when `high ≥ L + tick`;
  - the order of levels within a candle comes from its 1-second klines;
  - within one 1-second kline a level fills at most once.

  `result.fill_rule` names the rule, and the result view shows it.
- [x] **Without fine data.** When 1-second klines are missing for a period, the simulator falls
  back to the conservative order (adverse side first). It marks the affected candles in
  `result.coarse_periods`, and never silently.
- [x] **The result.** `GridBacktestResult` carries:
  - the equity curve, plus a buy-and-hold curve on the same timestamps (D18);
  - grid profit (closed cycles) separated from unrealised profit and loss;
  - the cycle count and the fill list;
  - the stop reason (none, stop loss, take profit or end of data);
  - the fee totals by maker and taker;
  - the fill rule and the coarse periods.
- [x] **Synthetic regimes.** The simulator is replayed on synthetic paths that reproduce the
  report's four regimes: ranging, uptrend, downtrend and crash-then-recovery. Each shows the
  report's qualitative outcome: in the uptrend the grid trails buy-and-hold, and in the downtrend
  the stop loss limits the loss. These are regression fixtures, not real-data claims.
- [x] **The chart is `BotChart`** (`EPIC-029G`, ADR D16). The backtest result hosts a `BotChart` and draws its
  candles with `draw_history` and its overlay with `show_overlay`, never through a drawer of its own, so
  the backtest and the running bot cannot draw a Grid differently (the PR #321 review).
- [x] **Running it from the planner.** In the Bots tab, "Backtest" on the Grid panel runs the
  current parameters over a chosen period. It shows:
  - the result chart (candles, levels, fills, stop loss and take profit, through `EPIC-029G`'s
    overlay);
  - the equity against buy-and-hold;
  - the summary numbers.

  It runs on a worker with cancellation and fencing (`async-ui-action-rule.md`). A cancelled run
  publishes nothing.
- [x] **Missing data.** When the chosen period's candles are not stored locally, the planner
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

Three commits on PR6: the simulator (domain), the query (application), and the Backtest tab (UI).

- **The simulator** (`domain/grid/grid_simulator.py`, `grid_replay.py`, `grid_fill_rule.py`,
  `grid_backtest_result.py`, `buy_and_hold.py`, `fine_klines.py`). It replays through the live
  executor's own reactions (`runtime_from_plan`, `ladder_orders`, `on_fill`, `book_market_fill`,
  `placed`/`accepted`), so a fill means the same thing in both. A candle no resting order or exit
  can react to is skipped, 1-second klines and all. A counter order rests from the next step, so
  within one 1-second kline a level fills at most once. Exits sell at market at `min(sl, open)` and
  `max(tp, open)`, so a gap is not filled at a price that never traded. A halt in the replay stops it
  with the live executor's reason (`HALTED`). Cancellation is checked before every candle and
  returns `GridBacktestCancelled`, never a partial result. 20 unit tests cover the fill-rule
  boundaries, kline order, fees per fill, every stop reason, a gap, cancellation and the four
  regimes. Mutation-checked: fill on touch (both sides), kline colour, a counter active in the same
  step, the gap exit, maker fees on buys, and a stop loss that never exits.
- **The query** (`application/queries/run_grid_backtest/`). It loads the bars through
  `IHistoricalKlines` and streams the 1-second klines from `IMarketDataRepository.stream_klines`
  through `StreamedFineKlines`, a forward-only `FineKlines`. A week of them is therefore never held
  in memory. It refuses in words for no stored candles (with `missing_candles`, which offers the
  sync), more than 20,000 candles, or unreadable parameters.
- **The UI** (`ui/kinds/grid/backtest/`, `ui/kinds/bot_backtest.py`,
  `ui/bots_screen/kind_backtests.py`). The screen hosts a kind's `BotBacktest` through
  `kind_panels.backtest_for`, so the shell still names no kind. The tab is hidden for a kind
  without one. The Grid's page is an MVP trio:
  - The presenter owns the one tracker.
  - The coordinator owns only a per-run cancel event.
  - Cancel and another bot invalidate the action before stopping the worker, so a result already
    computed is fenced off (tested with a handler that ignores the cancel).
  - The result is drawn by a `BotChart` (`draw_history`, `show_overlay`) and an equity chart, and
    the summary rows come from pure functions.
- **Guards.** `BotsPresenter` stays under 400 lines: its single-shot timer helper moved to
  `support/ui_kit/single_shot_timer.py`, and its wiring is three statements. The duplicated-member
  census stays at 63, because the page's members are named for what they do (`run_button`,
  `start_backtest`, `show_replay`) rather than `run`/`cancel`/`show_result`, which other modules
  also use.

**Deviations from §2–§4, each deliberate:**

1. The signature is `simulate_grid(inputs: GridBacktestInputs, cancelled) -> GridBacktestResult |
   GridBacktestCancelled`. The plan comes from `GridParams` inside the inputs, and the fill rule is
   one fixed rule (`FILL_RULE`), named in the result's provenance. It is not a parameter: a second
   rule would be a second variant, and none was asked for.
2. The integration test replays **two stored hours**, not a week, in real SQLite. A week is about
   600,000 one-second rows: minutes of inserts for the same mechanism.
3. **Fees and filters** are the planner's terms (`GetPlannerMarketQuery`, the venue's rates). They
   cannot be edited in the tab. Until the terms are read, Run says so and stays disabled.
4. The view's files are `ui/kinds/grid/backtest/` (coordinator, view, presenter, summary, equity
   chart), owned by the kind's `BotBacktest`, not by the Bots presenter. The Bots presenter was at
   393 of 400 lines, and the kind-neutral host keeps Grid out of the shell.
5. "Backtest" is a tab of the detail panel, beside Parameters, not a button on the Grid panel. The
   tab reads the parameters on screen, unsaved edits included.

**Review round 1 (PR #338), all seven findings fixed, each with a test that was red first:**

1. **Blocking.** A candle with only part of its 1-second klines was replayed as fully covered. It could erase a crash and its stop loss without being listed as coarse. 1-second klines now order a candle only when they reach its low and high (`grid_fill_rule.spans`); otherwise the candle is coarse and listed.
2. The "Sync candles" offer vanished on the Bots screen's next refresh of the selection (its 30-second clock, a planner answer, an edit). `follow` now redraws the idle state only when the bot or the reason Run is off changed.
3. Closing the page mid-run made the worker emit on a deleted coordinator (it was a child of the page). The coordinator is unparented, emits directly like `BotActionsCoordinator`, and drops answers once closed.
4. "Never kinder" overstated the evidence: a coarse replay completes no more cycles, but its final equity can differ either way. The claim is narrowed to what is tested.
5. A period only partly stored was replayed silently. The result's provenance now carries a `DataWindow` (expected and stored candles of the period asked for); the summary shows "Candles stored", and a shortfall offers the sync.
6. "Grid backtest", "fill rule", "coarse candle" and "buy-and-hold" are in the vocabulary.
7. `grid_replay`'s docstring no longer claims it calls `crossed_exit`.

**Review round 2 (PR #338): PASS**, with one should-fix finding, which is fixed with a test that failed first. The expected candle count used `ceil((end − start) / length)`. A period that does not start and end on candle boundaries (13:01 to 13:29 on 15m) therefore reported a missing candle that no sync could store. It now counts the candles that open at or after the start and close by the end, on epoch-aligned boundaries.

**Review round 3 (PR #338): PASS**, with one should-fix finding, which is fixed with a test that failed first. The stored candles were counted as every bar read, including the candle that opens at an aligned end. That candle could hide one real gap ("4 of 4" with a candle missing). The stored bars are now counted in the same set as the expected ones.

**Not verified:** a backtest of a real stored week on a real display. The check against the
Testnet run of the same period is `029H`'s.

## Resume (optional; while unfinished)
