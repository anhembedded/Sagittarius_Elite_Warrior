# BOT-156 — Every action of the shared chart toolbar is also in a menu

**Status:** 🔵 Backlog
**Source:** the conformance check `toolbar_actions_in_a_menu` (PR #371) and its independent review, which asked for an owner of the rows it recorded: "the market and backtest `toolbar_actions_in_a_menu` baseline rows name no owning task"
**Risk:** 🟡 — the chart's timeframe, zoom and Go live actions become commands, and every chart host must keep them in step
**Complexity:** M — `ChartToolbar`'s actions are built per chart card, while commands are contributed per mode
**Epic (optional):** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md)
**Depends on:** None

---

## 1. Context and problem
- **What is unreachable:** the shared `ChartToolbar` (`src/support/charting/`, object name `chartToolbar`) holds the timeframe buttons (1m/5m/15m/1h/1d), More timeframes…, Zoom in, Zoom out, Box zoom, Reset zoom and Go live. None of them is in a menu.
- **Why it matters:** a toolbar's buttons take no keyboard focus (`Qt::NoFocus`), so a keyboard user cannot reach any of these, against `ui-presentation-rule.md` §2 and §6.
- **Baseline:** the check records `market` and `backtest` → `toolbar_actions_in_a_menu` at every size. `dashboard` also has this row, but that row goes when EPIC-033P deletes the Dev Board.
- **Prior art:** `BOT-155` solved the same gap for the Backtest chart's own controls with View → Chart, driven by `ChartDisplayCommands` (`src/modules/backtesting/ui/chart_display_commands.py`).

## 2. Acceptance criteria
- [ ] In the Market and Backtest modes, every action of the chart in front's toolbar is reachable from a menu and in step with it: checked state, enabled state and the timeframe shown.
- [ ] The `market` and `backtest` `toolbar_actions_in_a_menu` rows leave `baseline_workbench_conformance.json`.

## 3. Design
- **Seam:** one seam in `support/charting` that any mode can bind, so the code is not repeated per mode (`fix-bug-rule.md` §1). It gives the chart toolbar's actions by key, and a small command object follows the chart in front, as `ChartDisplayCommands` does.
- **Placement:** View → Chart (Backtest already has the submenu) or a Chart menu. Access keys come from the View menu's free letters, checked by the conformance suite's `access_keys_unique`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/charting/chart_card/…` | the toolbar's actions by key |
| `src/modules/trading/ui/market/`, `src/modules/backtesting/ui/` | the commands and their binding |
| `tests/integration/presentation/ui/baseline_workbench_conformance.json` | remove the two rows |

## 5. Testing
- **Unit:** each command drives and follows its toolbar action, and is off with no chart.
- **Integration:** the conformance suite, with the rows gone.
