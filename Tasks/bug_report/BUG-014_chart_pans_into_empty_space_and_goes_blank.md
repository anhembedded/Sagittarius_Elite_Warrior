# BUG-014 — Chart can be panned/zoomed into empty space and goes completely blank

**Reported:** 2026-08-19 (user: *"chart mất nến"* — recurring; "fixed several
times already")
**Severity:** P1 — the chart, the screen's primary output, can be left showing
nothing at all through ordinary dragging
**Status:** ✅ Fixed — root-caused from dev-mode logs, regression-tested, verified on a real window

## Symptom

Dragging or zooming the Backtest chart eventually leaves a completely empty
plot: axes and grid still drawn, no candles anywhere. It does not recover by
dragging back; the user has to re-run or re-navigate.

## Evidence — the dev-mode log caught it exactly

The `[chart-range]` diagnostics added during BUG-009 recorded the whole slide
into nothing, in one session:

```
155/5000 candles visible  | view extends 0s BEFORE first candle and 0s AFTER last
477/5000 candles visible  | ... 26653s AFTER last   <-- past the newest candle
5000/5000 candles visible | 137057s BEFORE first candle and 363592s AFTER last
0/5000 candles visible    | 1210361s BEFORE first candle and 0s AFTER last
0/5000 candles visible    | ... (stays 0 for the remainder of the session)
```

`0/5000 candles visible` is the bug, stated numerically: the viewport is
somewhere no data exists.

## Root cause

Two independent defects, both required to produce what the user saw.

### 1. The viewport had no positional bounds

`ChartCard.set_max_visible_x_range()` was the only place that constrained the
view:

```python
self.plot_layout.main_plot.setLimits(maxXRange=max_seconds)
```

`maxXRange` caps how **wide** the view may become. It says nothing about
**where** the view may sit. Nothing anywhere set `xMin`/`xMax`, so the user
could pan arbitrarily far from the data — 1 210 361 seconds (about two weeks)
before the first candle, in the logged case — and legitimately be shown an
empty plot, because there genuinely is nothing to draw there.

### 2. The chart loaded only a slice of the run it was drawing

`_CHART_KLINES_FETCH_LIMIT` was a hardcoded `5000`, while the same session
backtested **52 147** candles and drew **960 trade markers** across the whole
range. So even before any panning, the chart was showing the most recent
5 000 candles with markers scattered across a period whose candles had never
been loaded — older markers stood over empty space, and panning left ran out
of candles almost immediately even though the data was present in SQLite.

This also violated the No-Hardcoding rule in `.agents/AGENTS.md`: a bounding
value like this belongs in `config_keys.py`.

## Fix

**1. Clamp the viewport to the loaded data** — `ChartCard._apply_view_bounds()`
sets `xMin`/`xMax` alongside the existing `maxXRange`, derived from the loaded
history and re-applied whenever that history changes
(`render_historical_data`, `prepend_historical_data`, `set_max_visible_x_range`).
Bar spacing is inferred from the data rather than assumed.

A margin of `_VIEW_EDGE_MARGIN_BARS` (30 bars) is deliberately allowed on each
side: clamping to the data's exact extent would glue the newest candle to the
right edge, which traders would rightly report as its own bug. The margin is
far too small to reach a blank chart.

**2. Load the range the backtest actually covered** —
`_CHART_KLINES_FETCH_LIMIT` becomes
`ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT` with a default of `200_000`.
The cap now exists only to bound memory. When it does bite, it is no longer
silent: a `WARNING` plus a `chart_query_truncated` dev-trace fires, naming the
config key and the consequence.

### Why raising the limit is safe — measured, not assumed

Per-frame pan cost is flat in history size, because viewport windowing draws
only the visible ~200 bars regardless of how much is loaded:

| loaded candles | initial load | pan cost |
|---|---|---|
| 5 000 | 63.5ms | 20.9ms/frame |
| 52 147 | 179.4ms | 18.2ms/frame |

Ten times the history costs ~116ms once, and nothing per frame. Incremental
pagination (the Dev Board's `HistoryPaginationController` pattern) was
considered and rejected as unnecessary complexity given these numbers — it
would also have required re-feeding every indicator script over the combined
history on each page, because `BaseIndicatorScript` cannot absorb older
candles after the fact.

## Regression tests

`tests/unit/presentation/ui/components/test_chart_view_bounds.py` — all three
confirmed to fail before the fix:

- `test_cannot_pan_far_past_the_oldest_candle_into_an_empty_view` — asks for a
  view ~1.2M seconds before the first candle, mirroring the logged range, and
  asserts candles remain visible.
- `test_cannot_pan_far_past_the_newest_candle_into_an_empty_view` — the same
  past the newest candle.
- `test_a_reasonable_margin_past_the_newest_candle_is_still_allowed` — guards
  against over-correcting into a clamp that pins the last candle to the edge.

`tests/unit/presentation/ui/screens/test_backtest_presenter.py`:

- `test_chart_klines_fetch_limit_covers_a_whole_backtested_range`
- `test_chart_klines_fetch_limit_is_config_overridable`

## Verification performed

- Full gated suite: **1398 passed, 94.36% coverage**, `ruff check` clean.
- **Real window**, reproducing the reported scenario: 52 147 candles loaded,
  then 24 hard drags alternating in both directions. Worst visible candle
  count across every frame of every drag: **155 — never zero**. The view
  stayed inside the data plus margin throughout.

## Note on the "fixed several times already" history

The user recalled this class of defect recurring. Previous fixes addressed
*renderers dropping candles they should have drawn*. This one is different in
kind: the renderer was correct throughout, and was faithfully drawing a region
that genuinely contains no data. That distinction is why earlier fixes did not
prevent it — and why the regression tests above assert on **visible candle
count for a requested range**, a property no renderer-level fix can satisfy on
its own.
