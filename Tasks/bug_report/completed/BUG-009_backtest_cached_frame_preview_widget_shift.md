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

## Suspected area (original guess — SUPERSEDED, see Root cause below)

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

## Root cause (FINAL — two earlier writeups in this file were wrong)

**Superseded twice.** The first pass blamed a stale pixmap after a mid-drag
viewport *resize*. The second blamed the pan transform being applied to the
whole cached frame including the axes. Both were real defects and both fixes
are kept, but neither is the root cause: after each one the user re-tested and
reported the bug still present, finally stating plainly *"what you have apply
make the bug look better, but it definitely not RC"*.

**The root cause is the cached-frame preview itself.** It replaces live
rendering, for the duration of a drag, with a 2D transform of a `QPixmap`
snapshot of the last rendered frame. Every symptom reported follows from that
single design decision, and none of them is fixable while the frame is a
snapshot:

1. **Blank band at the leading edge.** The snapshot contains no pixels beyond
   its own edge, so panning reveals area it can only fill with flat
   `_BACKGROUND_COLOR`. Bounding it (see below) shrinks the band but cannot
   remove it.
2. **Vertical jump on release.** The main plot runs `setAutoVisible(y=True)`,
   so a horizontal pan genuinely changes the Y range. A translated snapshot
   cannot re-autoscale, so the correct Y arrives only at commit. Measured on
   trending data: a 70px drag produces a ~3px vertical jump on release, and
   it recurs at every re-anchor.
3. **Indicator and volume lines missing over newly revealed area.** Their
   viewport windowing is applied through `RangeUpdateScheduler`'s coalescing
   timer, so a frame captured before it fires holds candles at the new range
   and indicators at the old one.

**The decisive evidence was the user's own A/B test.** They observed that
dragging from the *volume* subplot never shows the defect. `begin_pan()`
returns `False` for a press outside the main plot, so that gesture bypasses
the preview entirely and pans through pyqtgraph natively — confirmed from
instrumentation: `is_preview_active` stays `False`, the overlay is never
shown, and the X range updates live throughout. The renderer was never at
fault. The user exercised both paths side by side and judged the native one
correct.

**The preview's premise no longer holds.** It exists to avoid expensive
re-renders on large histories, but `CHART_CARD_MAX_ZOOM_OUT_CANDLES` caps the
plot at ~200 visible candles, so render cost is bounded by the viewport, not
by history size. Measured on the user's real workload (5 000 candles loaded,
~155 visible, 4 EMA overlays, 959 trade markers, 1636x279 viewport), timing
the viewport's actual `paintEvent` rather than an offscreen grab:

| path | frame cost |
|---|---|
| native live pan (what the volume subplot does) | 31.7ms median, 42.6ms p95 (~32 fps) |
| cached preview repaint | 0.4-0.5ms (from the user's own logs) |

An earlier benchmark in this file reported native pan as more expensive than
it is, because it timed `widget.grab()` — an offscreen pixmap capture real
panning never performs. That error is what kept the preview looking
justified.

## Fix

`backtest.chart.cached_interaction_enabled` now defaults to **false**
(`BackTestPresenter`), so the Backtest chart pans and zooms through
pyqtgraph natively — the same path the volume subplot always used. The
feature and all its fixes remain available by setting that key to true.

The three defects found on the way are all still fixed, because they matter
to anyone who opts back in:

1. **Chrome no longer moves.** `_CachedFrameOverlay` takes a list of
   `_PannableRegion`s: the untransformed frame is drawn first so axes and
   labels stay pinned, then each plot's ViewBox rect is redrawn transformed
   and double-clipped — once in device space, and again *after* the transform
   so only that region's own source pixels can be sampled (without the second
   clip the axis strip slides in and paints a ghost axis over the candles).
   The time-label band pans horizontally only, so timestamps keep tracking
   their candles.
2. **Blank band bounded.** `_reanchor_pan()` re-renders and re-grabs once a
   drag passes `min(5% of plot width, 96px)`. A percentage alone was not
   enough: at 15% on the user's 2218px plot that was a 333px strip.
3. **Deferred work settled before capture.** An injected
   `on_before_frame_grab` hook (wired to `range_updates.flush_pending`) runs
   before every grab.
4. **Mid-drag resize commits** rather than stretching a stale pixmap.

## Diagnostics added

Logging under the `"App."` namespace at several layers, because the first
attempt logged under `__name__` and emitted nothing at all: `StdLogger`
attaches handlers only to the `"App"` logger with `propagate = False`, so any
other logger has no handler in its chain and only Python's last-resort
WARNING+ fallback would emit it. An entire reproduce-and-send-log cycle was
lost to that. `plot_layout.py` had the same bug and is fixed too.

- `[chart-env]` — one-shot: real render backend and any OpenGL fallback
  reason, antialias mode, LOD, DPR, Qt platform, screen size.
- `[chart-data]` — data loads, and a per-gesture summary of real range
  updates applied, visible-candle count and whether a coalesced range is
  still pending.
- `[cached-frame]` — per gesture: BEGIN with viewport/overlay/frame sizes and
  regions, each re-anchor with its cost, and END with the max exposed band in
  pixels and overlay repaint statistics. Also logs presses outside the main
  plot, which is what identified the native-pan path.

## Regression tests

All in `tests/unit/presentation/ui/components/test_cached_frame_interaction.py`
unless noted; each was confirmed to fail when its fix is reverted:

- `test_backtest_cached_interaction_is_disabled_by_default` and
  `test_backtest_cached_interaction_can_be_re_enabled_by_config`
  (`tests/unit/presentation/ui/screens/test_backtest_presenter.py`) — pin the
  new default and keep the opt-in working.
- `test_pan_preview_moves_only_the_data_region_not_the_axes` — the price axis
  must be pixel-identical during a drag; the data must still change; the time
  axis must move with the data.
- `test_long_drag_does_not_expose_a_large_blank_band` — at most 25% of the
  plot width may be bare background. Judges whole columns: an earlier version
  sampled one row, hit the crosshair line, and passed even with the fix
  disabled.
- `test_reanchoring_mid_drag_lands_on_the_same_range_as_one_continuous_pan` —
  chained re-anchors must not drift from a single continuous pan.
- `test_viewport_resize_mid_pan_preview_commits_instead_of_stretching_stale_frame`.

## Verification performed

- Full gated suite: **1184 passed, 94.47% coverage**, ruff clean.
- Every step reproduced on a **real Windows window**, not offscreen.
- Environment note: the suite could not collect until `pydantic` and
  `python-binance` were installed — both in `requirements.txt`, both missing
  from this interpreter.

## Open question for the user

Native pan measures ~32 fps on this workload, against the preview's much
cheaper frames. That is the trade being made: correctness now, at a lower
frame rate on large annotated charts. If the drag feels sluggish in real use,
the next step is to make the *renderer* faster (the native C++ chart of
`BOT-098F`, which the Backtest screen already selects when script regions are
not in play) rather than to reinstate a snapshot-based preview.
