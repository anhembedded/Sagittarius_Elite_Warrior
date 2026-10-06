# BOT-164 — The Run backtest command reads as a button

**Status:** ✅ Done (2026-10-06)
**Board:** Decision: Run backtest gets the play icon and the mode toolbar writes text beside icons, so it reads as a button, not a flat label; the cause was a text-only toolbar entry, not a missing one. No Engine change: the host's own toolbar takes the stock style (BUG-161).
**Source:** the owner, 2026-10-06: "tui ko thấy nút F7, nên tưởng ko run dc" (I didn't see the F7 button, so I thought it couldn't run); approved the coordinator's proposal ("như bạn đề xuất"): make Run more prominent, for example a text-labelled button on the Backtest toolbar.
**Risk:** 🟢 — one icon on one command and a toolbar button style; every other command is unchanged
**Complexity:** S — one contract field, one line in the window, one line in the mode host
**SPEC (optional):** None; `Docs/HLD/11_desktop_workbench.md` §11.2.3 is updated
**Depends on:** None

---

## 1. Context and problem
[BUG-161](../bug_report/completed/BUG-161_backtest_does_not_run.md) and [BUG-160](../bug_report/completed/BUG-160_run_backtest_leaves_no_backtest_in_the_log.md): the owner's first backtest never started because they did not see how. The command was there (Tools → Run backtest, F7, and the Backtest toolbar), but the toolbar showed the words "Run backtest" with no icon and no button frame, in the same plain look as the "Emergency stop" and "Stop backtest" beside it. In the platform's flat toolbar style a word alone reads as a label (`BOT-164_assets/backtest_toolbar_before.png`).

## 2. Acceptance criteria
- [x] On the Backtest mode's toolbar the Run backtest button shows its text beside an icon.
- [x] The button is enabled while a run can start (no run going), and Stop backtest is not.
- [x] Stock controls only: no style sheet, no colour chosen by hand (the icon is drawn in the palette's text colour); the command is still one action shared by the menu, the toolbar and F7.
- [x] HLD §11.2.3 says so, in the same pull request.

## 3. Design
- The toolbar's button style, not a per-button widget: `ModeHost.add_command` sets `ToolButtonTextBesideIcon` on the mode's commands toolbar (Qt `QToolBar.setToolButtonStyle`; the stock way). The Engine's workbench only sets a style on its own mode bar, so this needs no Engine change.
- The icon is data on the command: `CommandContribution.icon` (the extension its docstring already named), set on the one action by `apply_icons` (the same `IconLoader` and palette colour the mode bar uses). The menu entry shares the action and shows it too.
- Only Run gets an icon. The library's outline square for Stop reads as a check box once the button is greyed, so Stop keeps its text; Emergency stop is not this task's.
- Rejected: a Run push button in the setup panel. `ui-presentation-rule.md` §6 forbids a push button repeating a command of its mode.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/command_contribution.py` | `icon: str \| None` |
| `src/presentation/ui/command_actions.py`, `main_window.py` | `apply_icons`, called once after the actions are built |
| `src/support/ui_kit/mode_host.py` | the commands toolbar writes text beside icon |
| `src/modules/backtesting/ui/backtest_commands.py` | Run names `play` |
| `Docs/HLD/11_desktop_workbench.md` | §11.2.3 note |
| `tests/integration/presentation/ui/test_backtest_run_is_findable.py` | the four tests below |

## 5. Testing
Integration tier, on the booted window (`test_backtest_run_is_findable.py`): Run's button has style text-beside-icon, the text "Run backtest" and a non-null icon; the icon is no taller than a line of text (without it the toolbar grew 9 px and the mode needed 715 px of height, over 706 before); Run is enabled and Stop disabled at idle; Stop keeps its text on the same toolbar. Mutation-checked, each caught by the named test: no toolbar style (the two style tests fail), no line-high icon size (the icon-size test fails), no icon on Run (the Run test fails), idle state forced false (the enabled test fails).

## Implementation notes
Pictures, 1366×768 Backtest mode toolbar, from `test_workbench_screenshots.py`'s capture (offscreen): `BOT-164_assets/backtest_toolbar_before.png` and `backtest_toolbar_after.png`. The toolbar is about 9 px taller with the icon. Not run on a real Windows desktop: the look there is the platform's own style for the same stock button.
