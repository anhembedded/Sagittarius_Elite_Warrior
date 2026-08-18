# BUG-009 — Backtest chart's cached-frame drag preview appears to move the whole widget, then snaps back

**Reported:** 2026-08-18
**Severity:** P2 — visual defect during a common interaction (pan-drag), Python backend, not a crash
**Status:** Reported — investigation deliberately deferred by user, not yet root-caused in code

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

## Next steps (when picked up)

1. Reproduce locally with a real drag on the real running app
   (`./scripts/run-ui.ps1`, default Python backend) — confirm the visual
   defect firsthand before reading code, per this project's own "diagnose
   root cause first" bug rule.
2. Read `_CachedFrameOverlay`'s geometry setup (`begin()`, any `resize`/`move`
   calls, parent widget relationship) to find where its position/size
   diverges from the live plot widget.
3. Write a regression test that reproduces the geometry mismatch before
   fixing it (this project's standing rule: test first, then fix).
