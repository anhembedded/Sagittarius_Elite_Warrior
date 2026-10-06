# BOT-157 — A menu's related commands are grouped, with a separator between groups

**Status:** 🔵 Backlog
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
- [ ] A command can name the group it belongs to in its menu, and the menu draws one separator between adjacent groups, never at either end and never two together.
- [ ] Backtest's View → Chart shows three groups: chart mode, layers, navigation; Market's View shows its market choice apart from its chart commands.
- [ ] The conformance suite fails a menu whose separators are doubled or at an end.

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
