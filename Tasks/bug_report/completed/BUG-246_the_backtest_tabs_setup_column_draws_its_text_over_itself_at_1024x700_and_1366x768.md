# BUG-246 — The Backtest tab's setup column draws its text over itself at 1024×700 and 1366×768

- **Reported:** 2026-10-21 (the independent review of PR #661, round 1, from the CI frames `bots~backtest-with-a-bot@1024x700.png` and `@1366x768.png`)
- **Severity:** 🟡 P2 — the sandbox's own explanation and the verdict lines are unreadable where they overlap, on the window sizes the rule calls usable
- **Status:** Fixed (2026-10-21)
- **Board:** On the Bots mode's Backtest tab the setup column's wrapped sentences were clipped (the source line needed 135 px of a 44 px label, the verdicts 630 px) because they sat in a layout the splitter squeezed below their height-for-width; fixed by laying the column out as the Live Plan's own class, `PlanColumn`, one scroll holding every part (BOT-218).
- **Context:** Backtest workbench (`EPIC-040D`–`040F`) → `src/modules/bots/ui/backtest_workbench/` (`backtest_workbench_view.py` `_build`, the setup column: `source`, `question`, the scrolling editor, `changed`, `verdicts`) → `ui/`
- **Environment:** Qt offscreen platform, the CI run's frames of PR #661 head `2f5f11b` (the artifact `ui-screenshots`); not seen on a real display.

## Reproduction
1. Select a Grid bot, show the Backtest tab, at 1024×700 or 1366×768 (`test_bots_mode_with_a_bot_conformance.py` saves both).
2. Expected: the sandbox sentence, the editor, the "same as the bot's plan" line and the verdicts each in its own space. Actual: they overlap in the setup column, which is narrow beside the result tabs.
Frequency: every run of the case at those two sizes. Not seen at 1920×1080.

## Symptom
The frames: `bots~backtest-with-a-bot@1024x700.png` and `bots~backtest-with-a-bot@1366x768.png` in the `ui-screenshots` artifact of PR #661's run. `fits_the_window` passes (the page fits the mode's minimum) and no other check reads overlap, so the gate is silent.

## Root cause
`backtest_workbench_view.py` → `BacktestWorkbenchView._build` (at `4fbf1b28`) put the setup column's labels in a plain `QVBoxLayout` inside a `QSplitter` pane, and gave only the editor a scroll area of its own. A `QSplitter` sizes a pane by minimum size hints, not by `heightForWidth`, so at the 127 px the result tabs left it, the labels got less height than their wrapped text needs: `lblBacktestSource` was 44 px tall and its text needs 135 px, `lblBacktestVerdicts` 44 px against 630 px. Measured with `wrapped_text_problems` (below), red on the page before the change.

## Fix
`BOT-218` replaced the layout: the setup column is the Live Plan's own class, `bots_screen/plan_column.py` → `PlanColumn`, one `QScrollArea` holding the banner, what sits under it, the editor, the checks and the foot. A scroll area asks its content's `heightForWidth` at its viewport width, so a wrapped label has the height its text needs; the column's `minimumSizeHint` is its content's width, so a splitter never cuts the editor's right edge and the Bots mode gives the column the width it asks for.

## Regression test
`tests/integration/presentation/ui/workbench_layout_checks.py` → `wrapped_text_problems`: a visible word-wrapped label is as tall as `heightForWidth` at its width. `test_bots_mode_with_a_bot_conformance.py` runs it on the Live Plan and on the Backtest page at 1024×700, 1366×768 and 1920×1080 (red on the old layout with `lblBacktestSource` 44 px against 135 px, green on `PlanColumn`). The check finds the same defect elsewhere, filed as BUG-248; it runs on these two columns only until that is fixed.

## Verification
The conformance case at three sizes; the frames `bots~{live,backtest}-with-a-bot[~dark]@*.png` of the pull request's CI artifact show the sentences whole beside the chart or the results.
