# BUG-151 — The status bar's progress bar shows "busy" from start-up, with no task running

- **Reported:** 2026-10-06 (the user, in chat, with a screenshot of the Market mode; seen the same day in the booted workbench's pictures and by the PR #372 reviewer)
- **Severity:** 🟡 P2 — the window says work is going on when none is; the person cannot tell real work (a sync, a backtest) from nothing, so the indicator loses its meaning (`ui-presentation-rule.md` §10: feedback only for work of 2 s or more)
- **Status:** Open
- **Context:** Every mode (the window's status bar) → `shell/` / `presentation/ui/` main window → status bar, `ui/` layer
- **Environment:** Seen on the user's desktop and in the headless capture (`QT_QPA_PLATFORM=offscreen`) at `claude/confident-dirac-le8m4x`, PR #372 head `3e78162`. OS of the user's run: not captured.

## Reproduction
1. Start the app (or boot the workbench as `tests/integration/presentation/ui/test_workbench_screenshots.py` does).
2. Look at the status bar at the bottom right, in any mode.

**Expected:** no progress bar, or an idle one, while nothing runs; a bar appears only for a running task, with a way to stop it.
**Actual:** an indeterminate ("busy") progress bar fills the status bar's progress slot from the first frame and keeps animating. Nothing the person started is running. Beside it is an empty box with no label.

**Frequency:** every start, every mode seen (Market, Backtest, Trade). Seen at 1024×700, 1366×768 and 1920×1080.

## Symptom
- The user's words (2026-10-06): "cai progess bar alway runing when open app, i consider it is a red flag".
- The user's screenshot (Market mode; not saved in the repository): the status bar reads `Exchange: not checked  Market data: live  Records: —  Database: —`, followed by a fully blue animated bar and an empty white box.
- The same state in the booted workbench, headless: [`BUG-151_status_bar_progress.png`](BUG-151_status_bar_progress.png) (`market@1366x768`, from `test_workbench_screenshots.py` at `3e78162`).
- The PR #372 review (https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/372#issuecomment-6008561907): "The status-bar progress bar shows busy with no task running (H7)."

## Root cause
Not yet established. Not investigated, at the user's request (2026-10-06: "not invest, not fix, just leave the doc").

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Find what owns the status bar's progress widget and what sets its range to busy at boot.
- Find what the empty box beside it is meant to show.
- A test in the conformance or screenshot tier could assert that, with no task running, no progress bar in the status bar is busy (`ui-presentation-rule.md` §10).
