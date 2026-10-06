# BUG-151 — The status bar's progress bar shows "busy" from start-up, with no task running

- **Reported:** 2026-10-06 (the user, in chat, with a screenshot of the Market mode; seen the same day in the booted workbench's pictures and by the PR #372 reviewer)
- **Severity:** 🟡 P2 — the window says work is going on when none is; the person cannot tell real work (a sync, a backtest) from nothing, so the indicator loses its meaning (`ui-presentation-rule.md` §10: feedback only for work of 2 s or more)
- **Status:** ✅ Fixed (2026-10-06)
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
In the Engine (engine `BUG-021`). `WorkbenchShell.add_status_widget()` put each screen's status widget straight into the status bar, and `_sync_status_widgets()` (`sagittarius_engine/extensions/pyside_mvc/workbench/workbench_shell.py`, run on every mode change) called `widget.setVisible(scope is None or scope == current)` on it. This app adds every status widget for every mode (`src/presentation/ui/main_window.py:228`), so each mode change showed all of them, over their owners' own `hide()`.

The Data mode's view hides its task label and progress bar while no task runs (`src/modules/market_data/ui/data_management_view.py`, `_sync_progress`), and while hidden the bar is indeterminate, because `progressMaximum` is 0 until a sync sets it. Shown by the shell, that is the animated "busy" bar of the screenshot, and the empty task label is the empty box beside it. The Backtest mode's run progress bar (`prgBacktestProgress`) is hidden the same way and was shown the same way: on engine `07f647f` it is visible in all six modes the conformance suite boots (the PR #384 review measured it).

The app's conformance suite had no check of the status bar at rest, so the gate stayed green.

## Fix
In the Engine (PR #233): each status widget sits in a `StatusSlot`. The shell sets only the slot's scope, the owner keeps its widget's visibility, and the slot shows only when both agree. This app's `engine.ref` moves to `68b4d29`, which carries #233 and its follow-up #234 (engine `BUG-022`: the first slot showed itself as a top-level window for an instant at start-up, which the sanity tier caught on the bump to `495d654`). No app source changes: the views already hide and show their own widgets correctly.

## Regression test
- `tests/integration/presentation/ui/workbench_status_checks.py`, registered as `no_progress_at_rest` in `test_workbench_conformance.py` and run for every mode at 1024×700, 1366×768 and 1920×1080. With no task started, the status bar shows no progress bar and no empty item; an item is empty when nothing in it shows text, a picture or a control. Its probes (`test_workbench_check_probes.py`) plant an idle progress bar, an empty label in a slot, a blank label straight in the bar and a slot whose only label was hidden, and each is seen; every rule of the check was mutated and a probe went red. **Before** (engine `07f647f`): red in all six modes, `progress bar prgDataTask is shown with no task running`. **After** (the fixed engine installed): green at all three sizes.
- In the Engine: `test_workbench_shell.py::TestStatusBarOutputAndOptions::test_a_status_widget_its_owner_hid_stays_hidden_in_every_mode` and `test_a_status_widget_its_owner_shows_appears_in_its_scope`, both red before and green after, each mutation-checked.

## Verification
- Positive proof in the booted app, with the fixed engine installed: the Data bar's parent is a `StatusSlot`. After `set_progress(0, 0, True, "Syncing BTCUSDT")` (the seam `SyncCoordinator` uses), the bar is visible and indeterminate in Market and in Backtest. After `hide_progress()`, the bar and its slot are hidden, and they stay hidden after a mode change.
- Scan: nothing else sets a widget's visibility from a mode scope, in the Engine or here.
