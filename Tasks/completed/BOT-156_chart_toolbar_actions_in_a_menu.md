# BOT-156 — Every action of the shared chart toolbar is also in a menu

**Status:** ✅ Done (2026-10-06)
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
- [x] In the Market and Backtest modes, every action of the chart in front's toolbar is reachable from a menu and in step with it: checked state, enabled state and the timeframe shown.
- [x] The `market` and `backtest` `toolbar_actions_in_a_menu` rows leave `baseline_workbench_conformance.json`.

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

## Implementation notes (written when done)
- **Commands.** `support/charting/chart_commands.py` (Qt-free, so a module's `contribute()` stays headless) declares one command per toolbar action: More timeframes…, Zoom in, Zoom out, Zoom in vertically, Zoom out vertically, Box zoom (checkable), Reset zoom, Go live. Each mode contributes them under View → C&hart with its own id prefix; their texts read as the toolbar's, and their access keys (m, n, o, t, y, z, r, g) avoid the letters of Backtest's chart-mode and layer items in the same submenu.
- **Mirror.** `support/charting/chart_command_mirror.py`: `chart_command_actions(card)` gives a `ChartCard`'s actions by key, and `ChartCommandMirror` drives the actions of the chart it follows (`trigger`, or `setChecked` for Box zoom) and follows their `enabledChanged`/`toggled`. Following another chart drops the connections to the previous one; following none turns every command off. Not in `chart_card.py`, which sits at its god-file ceiling.
- **Market.** `ChartHistoryCommands`, which already tracks the chart in front, holds the mirror and follows the front chart on every refresh (a tab opened, brought forward or closed).
- **Backtest.** `IBacktestChartHost.command_actions()` (its one implementer delegates to `chart_command_actions`); `ChartDisplayCommands` holds the mirror and follows the first card, the one the chart controls drive, alongside the toolbar it already followed. `bind_backtest_commands` now takes the view, so it follows the chart drawn at bind time as `BOT-155` does for the toolbar.
- **Pinned timeframes.** They are a person's favourites, changing per symbol, not commands of their own. Each carries `menuEquivalent` = "More timeframes…", whose picker reaches every timeframe and shows the one in effect; the conformance check `toolbar_actions_in_a_menu` judges such an action by that name, and `ui-presentation-rule.md` §6 says so.
- **Tests.** `tests/unit/support/charting/test_chart_command_mirror.py` (9), `tests/unit/modules/trading/ui/market/test_market_chart_commands.py` (3, the real presenter), two presenter-graph tests in `test_chart_display_commands.py`, and a probe for `menuEquivalent`. Mutation-checked: no disconnect on a new chart, no `menuEquivalent`, Market not following on refresh, Backtest not following a redrawn card, and the check ignoring the property each turn a test red.
- **Review of PR #372.**
  - Zoom in and Zoom out take the platform's `QKeySequence.ZoomIn` and `QKeySequence.ZoomOut` keys (§11), held only by the mode in front.
  - The mirror drops an action that goes with its chart (`destroyed`), so a command never reaches a deleted action, whatever order a host closes a chart and follows the next in.
  - HLD §11.2.3 lists View → Chart in both modes and how Go live differs from Back to live.
  - Grouping the 14 items of Backtest's View → Chart needs a field on `CommandContribution`: `BOT-157`.
