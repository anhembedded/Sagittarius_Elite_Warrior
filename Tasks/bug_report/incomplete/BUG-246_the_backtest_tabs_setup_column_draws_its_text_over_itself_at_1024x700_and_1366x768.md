# BUG-246 — The Backtest tab's setup column draws its text over itself at 1024×700 and 1366×768

- **Reported:** 2026-10-21 (the independent review of PR #661, round 1, from the CI frames `bots~backtest-with-a-bot@1024x700.png` and `@1366x768.png`)
- **Severity:** 🟡 P2 — the sandbox's own explanation and the verdict lines are unreadable where they overlap, on the window sizes the rule calls usable
- **Status:** Open
- **Board:** On the Bots mode's Backtest tab the setup column's sandbox sentence is clipped and the "OK: Not checked in a simulation…" lines are drawn over each other and over the "Suggest from ATR" group at 1024×700 and 1366×768; no check measures overlap.
- **Context:** Backtest workbench (`EPIC-040D`–`040F`) → `src/modules/bots/ui/backtest_workbench/` (`backtest_workbench_view.py` `_build`, the setup column: `source`, `question`, the scrolling editor, `changed`, `verdicts`) → `ui/`
- **Environment:** Qt offscreen platform, the CI run's frames of PR #661 head `2f5f11b` (the artifact `ui-screenshots`); not seen on a real display.

## Reproduction
1. Select a Grid bot, show the Backtest tab, at 1024×700 or 1366×768 (`test_bots_mode_with_a_bot_conformance.py` saves both).
2. Expected: the sandbox sentence, the editor, the "same as the bot's plan" line and the verdicts each in its own space. Actual: they overlap in the setup column, which is narrow beside the result tabs.
Frequency: every run of the case at those two sizes. Not seen at 1920×1080.

## Symptom
The frames: `bots~backtest-with-a-bot@1024x700.png` and `bots~backtest-with-a-bot@1366x768.png` in the `ui-screenshots` artifact of PR #661's run. `fits_the_window` passes (the page fits the mode's minimum) and no other check reads overlap, so the gate is silent.

## Root cause
Not yet established. Suspected: word-wrapped labels in a column whose width the splitter gives the setup side as little as its stretch factor allows, so each wrapped label's height hint is computed for a wider column than the one it is laid out in. Not verified.

## Fix
Pending.

## Regression test
Pending: a check that no two visible, sibling text widgets of a page overlap, run by the conformance case, is what would have caught this; none exists (`workbench_layout_checks.py` measures fit, not overlap).

## Verification
Not run.

## Suggested next steps
1. Reproduce under the real width of the setup column and read each label's `heightForWidth`.
2. Add an overlap check to `workbench_layout_checks.py`, red against this page, then fix the layout and leave the check.
