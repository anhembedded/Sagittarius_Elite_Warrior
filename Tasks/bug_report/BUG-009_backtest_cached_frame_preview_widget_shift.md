# BUG-009 — Backtest chart's cached-frame drag preview appears to move the whole widget, then snaps back

**Reported:** 2026-08-18
**Severity:** P2 — visual defect during a common interaction (pan-drag), Python backend, not a crash
**Status:** ✅ Fixed 2026-08-18 (same day) — root-caused, reproduced, regression-tested, verified on a real window

## Symptom

User report (screenshot attached in conversation, not yet saved to this repo):
while dragging to pan the Backtest chart (Python/pyqtgraph backend, default
`backtest.chart.backend`), the visible content appears to be the *whole chart
widget* shifting position — most of the chart area goes blank/black around a
small remaining patch of candles — rather than the candles panning smoothly
within a stationary widget. Releasing the mouse snaps the view back and the
chart re-renders correctly.

User's own words: "sao move chart mà nó lại move cái widget chart. sau khi
nhấy chuột thì nó trở về chỗ cũ và show chart."

## Suspected area (not yet confirmed)

`src/presentation/ui/components/chart_card/cached_frame_interaction.py` —
`CachedFrameInteractionController` / `_CachedFrameOverlay`. This is a
pre-existing performance feature (predates BOT-098F6, native chart work),
enabled by default (`BACKTEST_CHART_CACHED_INTERACTION_ENABLED` defaults to
`True` in `BackTestPresenter.__init__`): during a drag, a static `QPixmap`
snapshot of the last-rendered frame is shown in a transparent overlay
`QWidget`, translated/scaled cheaply (`shifted_x_range()`/`zoomed_x_range()`)
to simulate panning/zooming without a real re-render, then the overlay is
hidden and the real chart re-renders at the final range on mouse release.

The reported symptom (large blank area, small remaining chart patch, "snaps
back") is consistent with the overlay `QWidget`'s geometry (position/size) not
matching the underlying live plot widget's geometry during the drag — but
this has not been confirmed by reading `_CachedFrameOverlay`'s geometry-sync
code, reproduced locally, or traced to a specific line. Do not assume this
hypothesis is correct without verifying it first.

## Scope note

Confirmed **unrelated to BOT-098F6D** (the native chart opt-in cutover work
done the same day) — `cached_frame_interaction.py` is Python-only,
predates F6A-F6D, and none of F6A-F6D's changes touch it (`PythonBacktestChartHost`
wraps `ChartCard` without modifying its internals, per BOT-098F6A's own
architecture contract).

## Root cause (confirmed, not the originally suspected one)

The original hypothesis above — overlay *position* not matching the live
plot widget — was **not** confirmed. Direct measurement on a real window
(`overlay.mapToGlobal(0,0)` vs. `viewport.mapToGlobal(0,0)`) showed the
overlay tracks the viewport's position and size exactly, at every point
during a drag; `eventFilter`'s `QEvent.Type.Resize` branch already called
`self._overlay.setGeometry(self._viewport.rect())` on every viewport resize.

The actual bug is the **cached pixmap's size**, not the overlay widget's
geometry. `_CachedFrameOverlay.begin()` grabs `self._viewport.grab()` once,
at whatever size the viewport is *when the drag starts*, and stores it as
`self._frame`. `paintEvent()` always `drawPixmap(0, 0, self._frame)` — the
frame's native size — after first `fillRect`-ing the *entire current overlay
rect* with `_BACKGROUND_COLOR`. The Resize branch kept the overlay widget's
geometry in sync with the live viewport, but never re-grabbed or rescaled
`self._frame`. So if anything resizes the viewport while a pan/zoom preview
is active — a window resize, a splitter drag, or any dynamic layout reflow —
the overlay grows to the new size while the cached pixmap stays the old,
smaller size: the old frame keeps painting as a small patch in the corner,
and the newly-added area is raw `_BACKGROUND_COLOR`. That is exactly "most
of the chart area goes blank/black around a small remaining patch of
candles" — confirmed both numerically (`overlay.geometry().height() >
frame.size().height()` after a resize) and visually, via a real (non-
offscreen) window screenshot showing the defect, then its absence after the
fix. A plain window resize while holding the mouse button down is enough to
trigger it — no native-chart or BOT-098F6D interaction required, consistent
with this bug's Python-only scope.

## Fix

`CachedFrameInteractionController.eventFilter`'s `QEvent.Type.Resize` branch
(`src/presentation/ui/components/chart_card/cached_frame_interaction.py`)
now commits the in-progress preview (`commit_pan()`/`commit_zoom()`, same
codepath as a normal mouse-release) *before* resizing the overlay geometry,
whenever a preview is active. This hides the overlay immediately on any
mid-drag resize and applies the pan/zoom-so-far to the live plot, which then
resizes correctly on its own — there is no code path left where a stale,
wrong-sized pixmap can be painted across a larger overlay.

## Regression test

`tests/unit/presentation/ui/components/test_cached_frame_interaction.py::test_viewport_resize_mid_pan_preview_commits_instead_of_stretching_stale_frame`
— begins a real pan preview, resizes the card mid-drag, asserts (a) the
overlay geometry does exceed the stale cached pixmap's size (the
precondition for the defect), (b) the preview is committed/hidden rather
than left dangling, and (c) a pixel sampled in the region that used to sit
past the stale frame's bottom edge is **not** the overlay's own
`_BACKGROUND_COLOR` sentinel — i.e., an actual live-rendered pixel, not a
leftover blank patch. Verified failing against the pre-fix code (asserted
`is_preview_active is False` failed with `True`), then passing after the
fix. Kept permanently as a regression guard, per this repo's own
test-first-then-keep bug-fix rule — not a temporary debugging scaffold.

## Verification performed

- New regression test passes; 73/73 pre-existing tests in
  `test_cached_frame_interaction.py` + `test_chart_card.py` still pass.
- `ruff check` / `ruff format --check` clean on both touched files.
- Manually reproduced and re-verified on a **real** (non-offscreen) Windows
  window: resizing `ChartCard` mid-drag showed the blank-patch defect before
  the fix and the correct, fully-rendered live chart after it (screenshots
  taken during investigation, not committed to the repo).
- Could **not** run this repo's full coverage-gated suite
  (`Sagittarius_Elite_Warrior/tests`) in this session's Python environment —
  it fails at collection with `ModuleNotFoundError: No module named
  'pydantic'` across ~34 unrelated test files, a pre-existing environment
  gap (`pydantic` is in `requirements.txt` but not installed here), not
  something introduced by this fix. Whoever picks up this repo next should
  `pip install -r requirements.txt` (or otherwise get `pydantic` installed)
  and re-run the full gated suite before trusting coverage numbers.
