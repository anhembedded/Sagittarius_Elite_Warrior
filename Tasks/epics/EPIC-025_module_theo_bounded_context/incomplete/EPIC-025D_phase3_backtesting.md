# EPIC-025D — Phase 3: `modules/backtesting`

- **Status:** 🔴 Backlog
- **Repository:** Elite
- **Blocked by:** C · **Blocks:** E
- **Read first:** HLD §3.4; ADR D12. This is the **largest phase by line count** (the backtest
  screen is 12,309 lines in 74 files) but the **least entangled**: it depends only on
  `market_data.contracts` and `strategy.contracts`.

## 1. What to do

1. `modules/backtesting/`: `domain/backtesting` (`PaperExchange`, `_OpenPosition` — **not** merged
   with `LivePosition`, HLD §1 C3), `use_cases/backtest`, the backtest screen.
2. Fix the existing layer violation at `backtest_presenter.py:43` (an import of
   `infrastructure/persistence`) by going through `market_data.contracts`.
3. Build the Anticorruption Layer: `backtesting/adapters/` translates `PaperExchange` state into
   `strategy.contracts.StrategyContext`. (Round-3 correction: `strategy_context.py` does **not**
   import backtesting today; the wrong-direction import is `trading → backtesting` and is handled
   under ADR O4 before Phase 1.) `backtesting` sizes paper fills through `strategy.contracts.ISizingPolicy` (ADR D17), so backtest and live sizes are one number by construction.
4. Delete the dead use cases `RunBacktestCommand`, `StopBacktestCommand` and `BacktestState`
   (bound in the composition root, dispatched by nobody). Fill and marker overlays go through
   `IChartHost`.

## 2. Done when

- A backtest runs end to end with **bit-identical** results on the same data (the trade log before
  and after is compared — this is a pure refactoring).
