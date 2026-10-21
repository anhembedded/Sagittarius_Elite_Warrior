# BOT-211 — The Bots mode has a menu command for the timeframe picker (EPIC-040 F1)

**Status:** ✅ Done (2026-10-21)
**Board:** View → Chart → More timeframes… (and the zoom commands) now exist in the Bots mode and follow the chart in front: the Live chart's toolbar on the Live tab, the workbench's interval row on the Backtest tab; both reached only by mouse before (`ui-presentation-rule.md` §6).
**Source:** the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu), 2026-10-21: the owner said "OK làm 5 task 1-5 luôn" ("OK, do tasks 1 to 5 now"); item 1 is the follow-up F1 of [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md), found in PR #642's review.
**Risk:** 🟢 — menu commands over actions that already exist; the suite refuses a command with no key or two with one
**Complexity:** M — one object, one signal, one contribution, two tabs
**Epic (optional):** [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** None

---

## 1. Context and problem
The Bots mode contributed no `chart_commands`, so the pinned timeframes of the Live chart's toolbar and of the workbench's interval toolbar (`EPIC-040`, PR #642) were reachable only by mouse; `ui-presentation-rule.md` §6 requires every toolbar action in a menu, and a favourite reached through a chooser names the chooser's command (`menuEquivalent`). Market and Backtest contribute `chart_commands` and follow the chart in front through `ChartCommandMirror.follow_chart`.

## 2. Acceptance criteria
- [x] View → Chart in the Bots mode holds the chart commands (More timeframes…, zoom, Follow latest), in the order and with the keys Market and Backtest have.
- [x] On the Live tab they drive the selected bot's chart and follow its enabled and checked state; on the Backtest tab More timeframes… drives the workbench's interval row and the others are off.
- [x] A tab that shows a note (no bot, no account yet, a kind with no backtest) leaves every command off; switching tabs re-follows at once.
- [x] The conformance suite measures the mode with a bot selected ([BOT-212](BOT-212_a_conformance_case_with_a_backtestable_bot_selected.md)) and finds no toolbar action outside the menus.

## 3. Design
`BotsChartCommands` (`bots/ui/bots_screen/bots_chart_commands.py`) is the presenter-owned mirror for a mode with two tabs: it owns one `ChartCommandMirror` and re-follows when `BotsView.front_chart_changed` fires (the tab, the chart slot or the page slot changed). What is in front is read from the view, the single truth of what is shown (`BotsView.shown_chart`, `shown_backtest_page`), not tracked a second time in the presenter. `bind_bots_commands` creates it, parented to the view model like `KindCommands`. The contribution is `chart_commands(...)` unchanged, at `View › Chart` as the other modes.

## 3a. Reuse
`chart_commands`, `ChartCommandMirror`, `chart_command_actions` (the catalog row "Put a chart's toolbar actions in a mode's menu as commands"): used. `replace_in` (widget slot): used, with a new `held_in` reader beside it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/bots_screen/bots_chart_commands.py` | new: `BotsChartCommands` |
| `src/modules/bots/ui/bots_screen/bots_commands.py` | contributes `chart_commands`; `CHART_MENU`, `CHART_PREFIX` |
| `src/modules/bots/ui/bots_screen/bots_command_binding.py` | creates and binds it |
| `src/modules/bots/ui/bots_screen/bots_view.py` | `front_chart_changed`, `shown_chart`, `shown_backtest_page` |
| `src/modules/bots/ui/bots_screen/widget_slot.py` | `held_in` |

## 5. Testing
`tests/unit/modules/bots/ui/bots_screen/test_bots_chart_commands.py` (six cases, each mutated red: the Backtest-tab mapping, the tab signal); `tests/integration/presentation/ui/test_bots_mode_with_a_bot_conformance.py` (the real window; the command removed turns it red).

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (the centre's tabs), `Docs/HLD/11_desktop_workbench.md` §11.2.3 (the View → Chart row).

## Implementation notes
Delivered with BOT-211 to BOT-214 in one pull request (`EPIC-040` follow-ups F1 to F4). Frames: the CI artifact `ui-screenshots` of the `-Full` run, `bots~*` files (see the pull request).
