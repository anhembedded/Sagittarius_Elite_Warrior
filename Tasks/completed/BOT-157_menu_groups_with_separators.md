# BOT-157 — A menu's related commands are grouped, with a separator between groups

**Status:** ✅ Done (2026-10-06)
**Source:** the independent review of PR #372 (finding 3): "In Backtest, View → Chart is one flat list of 14 items with no separators … Please record a backlog task".
**Risk:** 🟡 — a field on a shared contract that every module's commands use
**Complexity:** M — `CommandContribution` and the Engine's menu building both change
**Epic (optional):** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md)
**Depends on:** Engine (`shell_menus._fill`)

---

## 1. Context and problem
- **What reads badly:** Backtest's View → Chart holds three kinds of command in one unbroken list of 14 items: what the chart draws (Candlestick, Equity curve, Side by side, exclusive), its layers (three check items) and the chart's navigation (More timeframes…, the zooms, Go live).
- **Why it matters:** Microsoft's `cmd-menus` guidance separates groups of related items, so a reader sees a choice, its options and the commands beside it at a glance (`ui-presentation-rule.md` §6).
- **Why it is not a local fix:** `CommandContribution` (`src/core/contracts/command_contribution.py`) has no group or separator field, and the Engine's `shell_menus._fill` adds items in the order contributed, so no module can say where a group ends.

## 2. Acceptance criteria
- [x] A command can name the group it belongs to in its menu, and the menu draws one separator between adjacent groups, never at either end and never two together.
- [x] Backtest's View → Chart shows three groups: chart mode, layers, navigation; Market's View shows its market choice apart from its chart commands.
- [x] The conformance suite fails a menu whose separators are doubled or at an end.

## 3. Design
- **Seam:** an optional `group` on `CommandContribution` (Qt-free, default `None` for every existing command); the Engine's menu filler inserts a separator where the group changes. Extension cases: a group order key; a group title, as a disabled section header on macOS.
- **Alternative rejected:** a separator pseudo-command; it is not a command, and the menu bar is the catalogue of commands (`ui-presentation-rule.md` §6).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/command_contribution.py` | the `group` field |
| Engine `workbench/shell_menus.py` | a separator between groups (an Engine PR) |
| `src/modules/backtesting/ui/backtest_commands.py`, `src/support/charting/chart_commands.py`, `src/modules/trading/ui/market/market_commands.py` | name the groups |
| `tests/integration/presentation/ui/workbench_widget_checks.py` | a separator check |

## 5. Testing
- **Unit:** the menu filler puts one separator between groups and none at the ends.
- **Integration:** the conformance suite, with the separator check.

## Implementation notes (written when done)
- **Engine (PR #230, `engine.ref` 6c6eab6).** `ActionDescriptor.group`; `ActionRegistry.menu_action_groups()` yields a menu's commands by group, in the order each group's first command was contributed and never an empty group; `shell_menus._fill` puts one separator between adjacent groups, and before the shell's own extras, never first. The Engine's tests cover the filler (the unit level of §5).
- **App.** `CommandContribution.group` (Qt-free, default `None`), passed through by `action_descriptor()` (`src/presentation/ui/command_actions.py`), the one place the app builds `ActionDescriptor`s. Backtest's View → Chart is three groups: the chart mode (`CHART_MODE`, also its exclusive group), the layers (`CHART_LAYERS`) and the chart's navigation (`chart_commands.NAVIGATION_GROUP`, shared by every mode that contributes the chart toolbar's commands). Market's View sets Spot market / Futures market (`MARKET_CHOICE`) apart from Load older candles, Load range… and Back to live (`CHART_HISTORY`).
- **Proof.** `test_menu_groups.py` reads both menus from the booted window (red when `action_descriptor` drops the group, or when a load command loses its group). The conformance suite's `menu_separators_between_groups` (`workbench_widget_checks.py`) fails a menu, or submenu, that starts or ends with a separator or shows two together, in every mode at every size; its probes are in `test_workbench_check_probes.py`. Every mode passes it, so it has no baseline row.
