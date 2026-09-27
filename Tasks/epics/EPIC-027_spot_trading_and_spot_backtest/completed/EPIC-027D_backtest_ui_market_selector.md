# EPIC-027D — The Backtest screen chooses Spot or Futures, and shows only what that market can do

**Status:** ✅ Done (2026-09-27)
**Source:** the user, 2026-09-26: *"back test theo spot"* ("backtest on spot").
**Risk:** 🟢 — presentation only, over the engine behavior `EPIC-027B` already proves.
**Complexity:** M — a selector, conditional controls, run-config plumbing, state persistence.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027B](EPIC-027B_spot_mode_in_the_backtest_engine.md), [EPIC-027A](EPIC-027A_market_aware_kline_storage_and_download.md)

---

## 1. Context and problem
- The Backtest top panel has no market choice (`src/modules/backtesting/ui/backtest_top_panel.py:181-224`).
- `BacktestRunConfig` has no market (`ui/logic/backtest_fsm_matrix.py:280-320`).
- Strategy Properties always shows Long and Short Leverage spinboxes, range 1–125
  (`ui/backtest_modals/strategy_properties_dialog.py:189-196`).
- The chart and the trade log always offer a "Liq" marker and long/short filters
  (`ui/logic/chart_canvas_view.py:149,197-200`).
- The limitations text is stale: it says "does not simulate slippage" and "No Stop Loss / Take Profit
  yet" (`ui/logic/backtest_limitations_view.py:21,27`).

## 2. Acceptance criteria
- [x] The top panel offers a market choice: Spot or Futures (USDⓈ-M). It is persisted with the
      screen state and changes the symbol list to that market's catalog.
- [x] In Spot, the leverage controls are hidden, not merely disabled. Short-only filters and
      liquidation markers are not offered.
- [x] The result panel shows "N short signals ignored (Spot)" when N > 0.
- [x] Changing the market marks the config dirty through the existing FSM (`CONFIG_DIRTY`).
- [x] The limitations text states what is true today, including the market being simulated.

## 3. Design
- Use a plain `QComboBox` bound through the ViewModel (`ui-presentation-rule.md` §1: standard parts).
  The orphaned `MarketPickerDialog` is kept only if it fits the Backtest header without a second
  picker pattern; otherwise it is deleted in this task.
- The market is part of `BacktestRunConfig`, so run history and "re-run" reproduce it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/backtesting/ui/backtest_top_panel.py` | market selector |
| `src/modules/backtesting/ui/logic/run_config_builder.py`, `backtest_fsm_matrix.py` | market in the run config and in its diff summary |
| `src/modules/backtesting/ui/backtest_modals/strategy_properties_dialog.py` | leverage section hidden in Spot |
| `src/modules/backtesting/ui/logic/backtest_limitations_view.py` | truthful text |
| `src/modules/backtesting/ui/preview.py` | preview in both markets |
| `src/modules/backtesting/application/run_static_backtest/handler.py`, `run_historical_tick_backtest/handler.py` | read candles from the chosen market instead of the Spot pin (`EPIC-027B` left the pin: following `BrokerSimulationConfig.market_type`'s `FUTURES_USD_M` default before a user can choose would send every existing run to Futures shards nobody has downloaded) |

## 5. Testing
- **Unit, new:**
  - `ui/test_backtest_market_selector.py`:
    - The selector offers exactly Futures (USDⓈ-M) and Spot and binds both ways.
    - The toolbar places it.
    - The leverage section is hidden, not disabled, in Spot.
    - The short trade-log tab disappears, and a selected one falls back to "all".
    - The chart drops "Short Only".
    - A market switch re-points the catalog, the rule check, the config and the preview, in
      that order.
  - `ui/logic/test_run_config_builder.py`:
    - The market reaches the run config.
    - An unknown or COIN-M stored value falls back to the default.
    - The snapshot carries the market, so a switch reads as a change, with the diff
      "Market (futures_usd_m → spot)".
  - `ui/test_backtest_presenter.py`:
    - Switching the market goes to `CONFIG_DIRTY` with that diff.
    - The picker lists the new market's catalog.
    - Spot pins both leverages to 1×.
  - `ui/test_backtest_limitations_view.py`: no line claims a missing feature the engine has. The
    running mode, the market (with the ignored shorts) and the exchange filters are stated per run.
  - `presentation/ui/screens/test_performance_metrics_view.py`: "N short/cover signal(s) ignored
    (Spot is long-only)" appears when N > 0, and so does the rejected-entries note.
  - `application/test_spot_market_backtest.py`: each run fills at its own market's prices when
    Spot and Futures candles of one symbol differ.
  - `market_data`: the catalog, the catalog repository, the klines and coverage contract suites
    each gained a market-isolation test. The symbol-options coordinator discards a fetch for the
    previous market.
- **Persistence:** the new `market` row in `BACKTEST_STATE_FIELDS` is covered by the table-driven
  round-trip and notifier tests in `test_backtest_presenter_state.py`.
- **Mutation:** deleting the `marketChanged` connection in `signal_wiring.py` turned both
  presenter market tests red. It was restored.
- **Integration, fixed:** three real-server/real-flow suites broke on the new required `market`
  arguments and a Spot-seeded fixture the Presenter no longer reads by default:
  `test_symbol_catalog_real.py` (`JsonSymbolCatalogRepository.get_symbols`/`save_symbols`, plus a
  new "each market writes its own file" test), `test_session_factories_against_fake_server.py`
  (`PythonBinanceClient.get_available_symbols`), and `test_backtest_user_flow.py` (its
  `FakeMarketDataRepository` fixture now seeds `MarketType.FUTURES_USD_M`, the screen's own
  default, instead of the port's default Spot).
- **Duplication guard, fixed:** `test_presenter_duplication_only_shrinks.py` caught a genuine new
  collision — `BrokerSimViewModel.set_market` (a property setter) and
  `SymbolOptionsCoordinator.set_market` (retargets the picker's cache) shared a name across the
  `backtesting.ui`/`market_data.ui` boundary the guard scans, with no shared body to extract
  (same "accept as debt" call the guard's own docstring makes for `_handle_market_tick`) — except
  here a same-file rename was available, so the coordinator's method became `retarget_market`,
  which also reads truer to what it does (drops a cache, not just a field).
- **Integration** (`tests/integration/presentation/ui/`): no new desktop-flow test added beyond
  the `test_backtest_user_flow.py` fixture fix above. The presenter tests drive the real presenter
  with the verified fakes. A desktop E2E run of the switch is not claimed.
- **Suites:** 5612 unit passed. 168 integration passed, 4 skipped. 32 sanity passed.

## Implementation notes (written when done)
- **The market lives on `BrokerSimViewModel.market`.** It is persisted as the `market`
  state-field row, placed before the leverage rows.
  - Switching to Spot pins both leverages to 1× on the single writer, so no restored state can pair
    Spot with leverage.
  - The run config carries it in `broker_config.market_type`. The dirty-tracking snapshot carries
    the market only, so fees and leverage stay at their defaults, which is pinned by a test.
  - The default is USD-M Futures, the same as `BrokerSimulationConfig`. A user who never touches
    the selector keeps Futures semantics and, per ADR D2, now reads **Futures** candles; the
    pre-run sync downloads them.
- **Everything market-scoped follows the selector.** The pre-run sync, the coverage probe, the
  chart preview and feed, the symbol catalog, the exchange-rule check, and both handlers' candle
  reads (`command.market`) all follow it.
  - This needed `market_data`'s read ports to take a market: `IHistoricalKlines`,
    `IRangeCoverage`, `ISymbolCatalog` and its repository (`tradeable_symbols.json` stays Spot's
    file; Futures gets `tradeable_symbols_futures_usd_m.json`), and `IExchangeClient`'s catalog
    reads.
  - A Futures catalog lists perpetuals only. A dated contract's `_` cannot be a shard name.
  - Every screen without a selector pins `SPOT` at its call site.
- **`MarketSelectionCoordinator`** handles a switch. The presenter file sits at its god-file
  ceiling, so the handler is a coordinator that the factory builds, like the other ten.
- **Short filters follow the screen's market, not the displayed result's.** After a Futures run,
  switching to Spot hides the short tab while that run's short trades are still listed; the run
  is marked stale at that point. Following the result instead needs a result-market field on
  the view model, which the view model's ceiling did not allow in this pass.
- **The orphaned `MarketPickerDialog` is deleted.** It offered COIN-M, which the engine refuses
  (ADR D1), and a toolbar combo needs no second picker pattern.
- **`BacktestResult.market_type`** records what a run simulated, so the limitations text can name
  it without a presenter change. A result built without one reads as the engine default, as a
  pre-`EPIC-027E` report does.
- **The limitations list is truthful again.** The claims "does not simulate slippage", "No Stop
  Loss / Take Profit yet" and a blanket "Running mode: Static" are gone. Running mode, market and
  exchange filters are now stated per run.
- **Preview** shows a Spot run: the selector on Spot, leverage hidden, no short tab, and the
  ignored-shorts and exchange-filter notes.
- **God-file ceilings** held by condensing comments in the same files. The baseline is tightened
  for four files, and the tick handler dropped under 400 lines and left the baseline.
