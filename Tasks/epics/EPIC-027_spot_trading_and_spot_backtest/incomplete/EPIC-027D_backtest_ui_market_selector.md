# EPIC-027D — The Backtest screen chooses Spot or Futures, and shows only what that market can do

**Status:** 🔵 Backlog
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
- [ ] The top panel offers a market choice: Spot or Futures (USDⓈ-M). It is persisted with the
      screen state and changes the symbol list to that market's catalog.
- [ ] In Spot, the leverage controls are hidden, not merely disabled. Short-only filters and
      liquidation markers are not offered.
- [ ] The result panel shows "N short signals ignored (Spot)" when N > 0.
- [ ] Changing the market marks the config dirty through the existing FSM (`CONFIG_DIRTY`).
- [ ] The limitations text states what is true today, including the market being simulated.

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

## 5. Testing
- Unit (ViewModel/logic): market to config, dirty flag, visibility rules.
- Integration (`tests/integration/presentation/ui/`): switch to Spot, run, see no short trade and see
  the ignored count.
- Not run yet.
