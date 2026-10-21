# BOT-218 — The Plan is one column, on the Live tab and on the Backtest tab

**Status:** ✅ Done (2026-10-21)
**Board:** The Live tab holds the bot's Plan beside its chart and the Backtest tab holds the sandbox's setup column beside its results, both the one class `PlanColumn` (banner, editor, checks); no Plan dock any more, and BUG-246's clipped column is gone with the layout that made it. Decided by the owner, 2026-10-21 (below); the Strategies dock is BOT-219.
**Source:** the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu), 2026-10-21, quoting the owner: "Nếu chuyển qua backtest thì đâu cần control của live làm gì. tui nghĩ 2 panel này phải thấy sự tương đồng nhau. nên có 1 panel chung. panel của live thì nên đi chung với tab live luôn, xóa cái strategy luôn đi." ("If we switch to Backtest, why keep the Live controls? I think the two panels should look alike, so one shared panel; the Live panel should go with the Live tab, and delete the Strategies one.") The coordinator approved the design for the owner.
**Risk:** 🟡 — the Bots mode's layout changes; its minimum size and a saved layout both had to be shown to hold
**Complexity:** M — one new column class, two views re-laid, tests and frames
**Epic (optional):** [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** None

---

## 1. Context and problem
The Plan was a window-level dock on the right, shown on both tabs, while the Backtest tab had a setup column of its own with different parts (a label, a verdict wall). Switching to Backtest left Live's controls on screen beside a second, different plan, and the setup column was 100–130 px wide with its sentences clipped (BUG-246: `lblBacktestSource` 44 px tall, its text needing 135 px, at `4fbf1b28`).

## 2. Acceptance criteria
- [x] The Plan is a pane of the Live tab, a splitter with the chart, and no dock is titled Plan; the Backtest tab shows none of it (`test_the_plan_belongs_to_the_live_tab.py`).
- [x] One class, `PlanColumn`, is the layout of both: the Live Plan and the Backtest setup column share its banner, editor slot and checks list; the sandbox's source line is its banner and its verdicts are its checks, reusing BOT-209 (`PlanChecksView`, `PlanStatusBanner`) and BOT-206's rows for the Live figures; no widget code is copied.
- [x] A layout saved while the Plan was a dock restores without error and without the dock.
- [x] No wrapped label is clipped on either column at 1024×700, 1366×768 and 1920×1080 (`wrapped_text_problems`, red on the old layout).
- [x] The mode still fits 1024×700 (`fits_the_window` on both tabs).
- [x] Frames of both tabs with a bot selected, light and dark, at the three sizes, in the pull request's CI artifact.
- [x] The Strategies dock is removed: done by [BOT-219](BOT-219_the_strategies_dock_is_removed_from_the_bots_mode.md) after the owner chose how arming stays reachable (the dock was the only way to arm).

## 3. Design
`PlanColumn` (a `QScrollArea`) owns the order: head, banner, intro, figures, editor, checks, foot. The Live `BotPlanPanel` fills head (name, state), intro (Venue) and figures (the property table); `BacktestWorkbenchView` fills the banner with the source line, intro with its question, the Replace and Keep buttons and the changed-fields line, and the foot with what a simulation cannot check (a verdict that did not run is never counted among the passed checks). The column's `minimumSizeHint` is its content's width, so a splitter never cuts the editor's right edge and the window keeps the width the column asks for. Both views put the column on the left, the chart or the results on the right.
Alternatives: keeping the Plan dock and hiding it on Backtest (two places for one plan, and the dock is the window's, not the tab's); a min-width on the column (refused by `ui-presentation-rule.md` §3 and `test_stock_controls_only.py`).

## 3a. Reuse
`PlanStatusBanner`, `PlanChecksView`, `plan_checks_of` (BOT-209), `PlanPropertyGrid` (BOT-206), `replace_in` (`widget_slot.py`): used. `NoticeBar`: used through the banner. New: `PlanColumn`, the one layout.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/bots_screen/plan_column.py` | new: the one column of a bot's plan |
| `src/modules/bots/ui/bots_screen/bot_plan_panel.py` | built on `PlanColumn`; same attributes |
| `src/modules/bots/ui/bots_screen/bots_view.py` | the Live tab is a splitter of Plan and chart; no Plan dock |
| `src/modules/bots/ui/bots_screen/plan_status_banner.py` | the banner takes its object name |
| `src/modules/bots/ui/backtest_workbench/backtest_workbench_view.py` | the setup column is `PlanColumn`; checks and the unchecked note replace the verdict label |
| `src/modules/bots/ui/backtest_workbench/{workbench_state,backtest_workbench_presenter}.py` | the state carries `checks` and `unchecked_lines` |
| `src/modules/bots/ui/backtest_workbench/interval_toolbar.py` | the interval chooser moved out of the view (400-line ceiling) |
| `tests/…/test_the_plan_belongs_to_the_live_tab.py` | new: the structure and the saved layout |
| `tests/integration/presentation/ui/{workbench_layout_checks,test_bots_mode_with_a_bot_conformance}.py` | `wrapped_text_problems`; dark frames; the Plan absent on Backtest |

## 5. Testing
Unit: `test_the_plan_belongs_to_the_live_tab.py` (mutation-checked: the Plan placed as a dock, and the workbench's own banner, each turn it red); the existing Bots view, Plan and workbench tests re-pointed. Integration (UI tier): the with-a-bot conformance case at three sizes. Gate: the pull request's `ci-local.ps1 -Full` run.

## 6. Docs touched
`Docs/HLD/11_desktop_workbench.md` (the Bots row), `Docs/MODULES/bots/05-building-blocks.md` (the Bots screen hosts it; the Plan). EPIC-040G D11 is untouched here: the Strategies dock stays until BOT-219 is decided.

## Implementation notes (written when done)
- `PlanColumn.minimumSizeHint`: a splitter shrank the column below its editor's width and cut the editor's right edge (no horizontal scroll), seen in the 1366×768 frame; the hint now carries the content's width.
- The Backtest splitter's `setSizes([1, 1])` gives the column a share at first show; stretch factors alone left it at the width of its empty first state.
- `test_plan_dock_frames.py` now waits for the property table's last row to be inside the table before asserting it: the table takes its height a layout pass after its rows are set, and the extra layout level makes that pass visible to the test.
- The Live tab's Plan width is not remembered across runs: the Plan dock's width was kept by the surface's `saveState`, the splitter's is not, and the Plan has no View toggle now (the splitter is non-collapsible). Filed as BOT-220 rather than widened into this task (review round 1 of PR #673).
- `BOTS_SURFACE` still accepts `Place.RAIL`: it is the shell's declaration of the Bots surface (`shell/surfaces.py`, held equal by `test_bots_view_renders_the_surface_the_shell_declares`), and the saved-layout test uses it to rebuild the old Plan dock. Dropping it is a shell change for a later task, not this one.
- The last criterion (the Strategies dock) is left open on purpose: BOT-219 holds it, the coordinator knows.
