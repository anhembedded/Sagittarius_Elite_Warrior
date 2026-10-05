# EPIC-033Q — The Market mode shows Spot or Futures candles, as the person chooses

**Status:** ✅ Done (2026-10-05)
**Source:** the user, 2026-10-05, deciding where the Dev Board's Spot/Futures combo goes when the Dev Board is deleted (EPIC-033P): "Market mode thêm Spot/Futures" (the Market mode gains Spot/Futures)
**Risk:** 🟢 — the Watchlist and charts read one more choice; a mixed-market tick feed is the trap
**Complexity:** S — one choice, read where `MARKET` is read today
**Epic (optional):** [EPIC-033](../README.md)
**SPEC (optional):** [SPEC-002](../../../../Docs/SPEC/README.md)
**Depends on:** EPIC-033H (merged)

---

## 1. Context and problem
The Market mode watches Spot only: `src/modules/trading/ui/market/market_dependencies.py` fixes `MARKET = MarketType.SPOT`. The only place a person sees Futures candles outside the Futures desk is the Dev Board's Spot/Futures combo box, which EPIC-033P deletes.

## 2. Acceptance criteria
- [x] Market → Spot and Market → Futures are two checkable actions in one exclusive group; Spot is the default and the choice persists per mode.
- [x] The Watchlist and every open chart show the chosen market's candles; a tick from the other market never reaches them.
- [x] Switching the market reloads the open charts and the Watchlist; nothing from the previous market stays on screen.

## 3. Design
The market is a value of the mode, not of each chart: one exclusive `QActionGroup` (HLD §11.2.3 "Market" menu), read by the presenter where it reads `MARKET` today.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/market/market_commands.py` | the two checkable actions |
| `src/modules/trading/ui/market/market_presenter.py` | the market as state; reload on change; filter ticks by market |
| `src/modules/trading/ui/market/market_choice.py` (new) | the market, its two checks and its remembered slice, out of the presenter (which would pass 400 lines) |
| `src/modules/trading/ui/market/market_dependencies.py`, `market_chart.py` | one candle feed per market; a chart takes the feed of its market |
| `src/core/contracts/command_contribution.py`, `src/presentation/ui/command_actions.py`, `src/presentation/ui/main_window.py` | `exclusive_group`: the window makes one exclusive `QActionGroup` per group a command names |

## 5. Testing
Unit: the actions are exclusive and persist; a tick of the other market is dropped (mutation-verified). Integration: switching reloads the charts against the in-memory store.

## Implementation notes (written when done)
- **One exclusive `QActionGroup`, built by the window.** The Engine's `ActionDescriptor` has no group, so a contributed command names one (`CommandContribution.exclusive_group`, checkable only, refused otherwise) and `MainWindow` makes one `QActionGroup` per name right after contributing, before any presenter binds (`command_actions.exclusive_groups`). Checking the checked action keeps it checked, so the choice never reads "none". `tests/command_actions.bound_actions` makes the groups the same way, so presenter tests bind against what the window builds. No Engine change.
- **Market menu (`Mar&ket`, Alt+K) with `&Spot` and `F&utures`, also on the mode's toolbar.** K is no other menu-bar title's key and no key of the Backtest run setup, which holds M (`&Market:`; the first push took Alt+M and `test_the_run_setup_takes_no_access_key_of_the_menu_bar` caught it in CI); S and U are no title's key either (`F` is File's). HLD §11.2.3's table and its list of menu-bar keys say so.
- **`MarketChoice` (`market_choice.py`).** Holds the market (Spot by default), binds the two commands with a `checked` signal each, and is the `IStateContributor` (scope `market`, `{"market": "<MarketType value>"}`): restored through `UiStateCoordinator` when the application has one (`find_state_coordinator`), marked dirty on a change. A remembered market the mode does not offer (Coin-M) restores Spot. Futures means USDⓈ-M, the market the Futures desk trades.
- **Switching (`MarketPresenter._on_market_changed`).** Every open chart closes (load cancelled, stream released) and reopens in tab order on the new market's `MarketDataCandleFeed`, the tab in front stays in front; the Watchlist's rows go blank; once live, the Watchlist's stream is started again for the new market (a start replaces, `IMarketStream.start`). A restored, not-yet-live mode stays quiet (`BUG-104`).
- **Ticks.** `MarketTickFeed` already filters by the market callable, but it asks on the publishing thread and the signal is queued to the Qt thread, so a tick of the old market can land after a switch; `_on_tick` drops any tick whose market is not the chosen one.
- **Verification:** commit tier PASS (`ci-local.ps1 -SkipTests`); architecture guards and the trading UI, presentation, core, shell and trading integration tests pass (1,760); sanity tier run. Mutation-checked: removing the group, the restore, the dirty mark, the tick fence, the Watchlist blanking, the stream restart, the per-market feed, the front-tab restore, the same-market guard, the offered-markets check, the exclusive-group refusal, and a clashing `&Futures` key each turns a test red. The review of PR #359 found that the window's `exclusive_groups` call, the per-market feeds in `market_dependencies_for` and its coordinator lookup were tested only through mirrors (`bound_actions`, hand-built `MarketDependencies`); `test_main_window_commands.py::test_the_window_makes_a_commands_exclusive_group_one_action_group` and `test_market_dependencies.py` now go red when any of the three lines is removed. `test_presenter_duplication_only_shrinks` caught a `market` member shared with Backtest's run setup; the property is `current`.
- **Still open:** the Watchlist's tracked symbols are the same for both markets (a Futures-only symbol is a Settings choice); the status bar does not name the market (the checked toolbar action does).
