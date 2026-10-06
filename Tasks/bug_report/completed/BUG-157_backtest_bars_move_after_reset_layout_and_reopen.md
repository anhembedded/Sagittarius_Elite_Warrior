# BUG-157 — Backtest mode: after Reset layout, the banner and chart-view bar sit in the wrong place when the app is reopened

- **Reported:** 2026-10-06 (the user, in chat, with two screenshots)
- **Severity:** 🟢 P3 — the Backtest layout is misplaced after a restart; the area stays usable
- **Status:** ✅ Fixed (2026-10-06)
- **Board:** Root cause: the environment banner was a `QToolBar`, so it sat in the layout `saveState`/`restoreState` keep, and a saved layout that put another toolbar ahead of it on its line shifted it by that bar's width (measured: 376 px); the chart-view bar was never displaced, it only sits under the banner. Fixed by making the banner the surface's menu widget, outside every layout, in `WorkbenchSurface._add_environment_banner`.
- **Context:** Restore the window layout (Window → Reset layout, saved layout on start) → `shell/` and `src/modules/backtesting/` → workbench layout, `ui/` layer
- **Environment:** Windows (the user's desktop). App commit, engine commit and Python version not captured. Backtest mode, Spot, BTCUSDT, Ema Crossover, 30m, trading off.

## Reproduction
1. In the Backtest mode, reset the layout.
2. Close the app and open it again.

**Expected:** the layout as Reset layout produced it.
**Actual (the user's words, translated):** "when resetting the layout, this bar jumps here when the app is reopened." In the first screenshot the "Trading is OFF. Data view only." banner and the chart-view bar (Candlestick, Equity curve, Side by side, Strategy indicators, Volume, Buy/sell flags, filters) start to the right of the Run setup panel, below an empty strip, and the Run setup panel starts below them; the user outlined that strip.

**Frequency:** Not yet established (one occurrence reported). Which of the two screenshots shows the state before the restart was not stated. Not yet reproduced here.

## Symptom
- The user's words: "khi rest layout mà cái thanh này nhảy về đây khi mở app lại".
- The misplaced bars, outlined by the user: [`BUG-157_bar_moved_after_reopen.webp`](BUG-157_bar_moved_after_reopen.webp).
- The second screenshot sent with it, where the banner spans the full width under the toolbar and the chart-view bar sits above the chart: [`BUG-157_second_screenshot.webp`](BUG-157_second_screenshot.webp).
- The banner itself is reported as [BUG-156](BUG-156_trading_off_banner_takes_a_full_width_strip.md).

## Root cause
`src/support/ui_kit/workbench_surface.py` (`_add_environment_banner`, before this fix) built the banner as a `QToolBar` in the top toolbar area. A toolbar is part of the state `QMainWindow.saveState` writes and `restoreState` applies: its line, its position along the line (`pos`) and its break. The perspective store restores that state at every start (`ModePerspectives`, `RegionHost.restore_perspective`), so the banner's place was whatever the saved layout said.

Measured here (offscreen, the engine pinned by `engine.ref`): a layout saved with a sibling toolbar ahead of the banner on its line (item `pos` 0x174 = 372 px for the banner) restored into a surface with the default arrangement put the banner 376 px from the left edge, the sibling's width. That is the user's first screenshot: the banner starts to the right of where the full-width row of the second one starts, by about a toolbar's width. The chart-view bar (`BacktestChartControls`, `chart_controls.py:47`) is inside the central widget, not a window toolbar; in both screenshots it is at the same place relative to the docks, so it was never displaced: it only seems to move because the banner above it did.

**Unknown:** which sibling toolbar the user's saved layout had ahead of the banner. A build earlier than this tree can have written it; the user's saved state was not available to this session. The mechanism, a layout restoring a banner that is part of it, is proven; the user's file is not.

Offscreen, with the current build, Reset layout, close and reopen of the Backtest mode keeps the banner at 0 px (checked with the real `MainWindow` over a state file): the defect needs a layout that already holds the banner off its row.

## Fix
The banner is the surface's menu widget (`QMainWindow.setMenuWidget`): above every toolbar and dock, across the full width, in no layout. Nothing the user arranges or a restart restores can reach it, and, as `BUG-154` wanted, no toolbar menu lists it. An old saved layout that still names the `::environment` toolbar is harmless: Qt ignores a name no toolbar has. The factory registered by the composition root may now answer `None` for a run with nothing to warn of (used by `BUG-156`).

`tests/integration/presentation/ui/workbench_layout_checks.py` no longer skips the banner when it rearranges a mode, as it did for a locked toolbar (there is no such bar now).

## Regression test
`tests/unit/support/ui_kit/test_workbench_surface.py::TestTheEnvironmentBanner::test_a_restored_layout_never_moves_the_banner` restores a layout written by the old build (the bytes are in the test) into a surface and asserts the banner starts at 0 and spans the width. Red before the fix (`the banner starts 376px from the left edge`), green after. Also `test_environment_banner_all_screens.py::test_the_user_can_neither_move_nor_hide_the_banner` for every route.

## Verification
- Regression test: red before (376 px), green after.
- Commit tier (`ci-local.ps1 -SkipTests`): PASS; `tests/unit/architecture`, `tests/unit/support/ui_kit`, `tests/unit/presentation/ui` green; integration `main_window_state` and `dialog_screenshots` green.
- `test_workbench_conformance[True-1024x700]` fails here with `backtest@1024x700/fits_the_window: needs 719x706`, and fails the same on `master-warrior` without this change.

## Suggested next steps
- If the banner is still displaced after this, send the saved perspective for `surface::backtest` (the state store file), to confirm the layout that held it.
