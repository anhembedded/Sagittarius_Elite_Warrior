# BUG-154 — The environment banner, the trading-safety warning, can be switched off with one right click

- **Reported:** 2026-10-06 (the workbench's first desktop E2E run, `scripts/workbench_desktop_e2e.py`, on an X server in the cloud session)
- **Severity:** 🟡 P2 — the row that says "Trading is OFF" or names the venue live orders go to could be hidden, and stayed hidden until the next start
- **Status:** ✅ Fixed (2026-10-06)
- **Board:** Root cause: the environment banner row (`WorkbenchSurface._add_environment_banner`) was locked in place but its toggle stayed in the toolbar menu every `QMainWindow` offers on a right click, so one click hid the warning. Fixed by taking the toggle off that menu at the one place every mode builds the banner; the offscreen restart check never saw it because its boot registers no banner.
- **Context:** Every mode (the workbench) → `support/ui_kit` → `workbench_surface.py`, the environment banner of `EPIC-021K` §4
- **Environment:** Linux, Xvfb 1600×1000, the real `app_bootstrapper.build()` boot; master `2f99305` plus `BOT-163`

## Reproduction
1. Start the app; any mode.
2. Right-click the toolbar area of the mode: the menu lists "Environment" beside the docks.
3. Untick it: the banner row disappears. Restart: it is back.

## Symptom
The desktop E2E rearranged the Trade mode, restarted, and reported:
`trade: surface::trade/surface::trade::environment is TopToolBarArea, shown after a restart, BottomToolBarArea, hidden when it closed`.
The banner is deliberately not movable ("a warning the user can drag into a corner is a warning that stops working", `workbench_surface.py`), so a user should never be able to change it at all. Expected: the banner can be neither moved nor hidden.

## Root cause
`src/support/ui_kit/workbench_surface.py` `_add_environment_banner` set `setMovable(False)` and `setFloatable(False)` but left the toolbar's `toggleViewAction()` visible, and `QMainWindow.createPopupMenu()` lists every toolbar's toggle. The offscreen restart check (`test_main_window_state.py`) never saw the banner: its boot registers no banner factory. Only the real boot does, which the new desktop E2E uses.

## Fix
- `workbench_surface.py`: the banner's `toggleViewAction()` is hidden, so the right-click menu no longer offers it. One place, every mode: each mode's surface builds its banner here.
- `tests/integration/presentation/ui/workbench_layout_checks.py`: `rearrange` skips a bar the user cannot arrange (a locked toolbar whose toggle is off the menu). Otherwise the check would move what no user can move.

## Regression test
`tests/unit/presentation/ui/test_environment_banner_all_screens.py::test_the_user_can_neither_move_nor_hide_the_banner`, one case per navigable mode. Before the fix it failed in all five modes for the right reason: `'Environment'` was in the visible actions of `createPopupMenu()`. After the fix it passes. It builds the real views and the real menu Qt shows.

## Verification
- Regression test red before the fix (5 failed), green after.
- `test_main_window_state.py` and `test_workbench_conformance.py`: 19 passed.
- `scripts/workbench_desktop_e2e.py` under Xvfb: `RESULT: FAIL` with the line above before the fix, `RESULT: PASS` after. That is the positive proof the repaired path ran.
