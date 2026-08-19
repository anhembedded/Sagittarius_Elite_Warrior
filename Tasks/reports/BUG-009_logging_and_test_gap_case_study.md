# Case study — why the test suite didn't catch BUG-009, and why the first two logging attempts didn't either

**Written:** 2026-08-18, after `BUG-009` was actually root-caused and fixed
(disable the cached-frame preview by default — see
[`Tasks/bug_report/BUG-009_backtest_cached_frame_preview_widget_shift.md`](../bug_report/BUG-009_backtest_cached_frame_preview_widget_shift.md)
for the fix itself). This document exists to answer two questions the user
asked directly: *why didn't the test system catch this*, and *what should the
logging system have done differently*. Read alongside
[`.agents/rules/logging-rule.md`](../../.agents/rules/logging-rule.md), which
this case study justifies.

## Timeline, compressed

1. User reports: dragging the Backtest chart moves the whole graph, then
   snaps back.
2. **Attempt 1** — root-caused as a stale cached pixmap after a mid-drag
   viewport resize. Fixed, tests added, reported resolved.
3. User provides a screenshot: still broken. Real symptom is the axis sliding
   and a blank band — no resize involved at all.
4. **Attempt 2** — root-caused as the pan transform applying to the whole
   cached frame (axes included) instead of just the plot's data region.
   Fixed, tests added, reported resolved.
5. User asks for logs to be added. First logging pass added `logging.getLogger(__name__)`
   calls. User ran the app, pasted back two full session logs. **Neither
   contained a single line from the new logging** — not even a one-time
   "cached interaction enabled" line.
6. Root cause of *that*: `StdLogger` (the engine's logging implementation)
   attaches every handler to the `"App"` logger and sets `propagate = False`
   on it. A `__name__`-based logger elsewhere in the package has no handler in
   its chain; Python's own last-resort handler only shows WARNING and above.
   An entire reproduce-and-send-log cycle was spent discovering the
   instrumentation itself was silent.
7. Logging fixed to use `"App.*"`. User reproduced again and pasted a log
   containing real `[cached-frame]` lines — a 15%-of-plot-width blank band
   was visible in the numbers. **Attempt 3** — tightened the re-anchor
   threshold from a plain percentage to `min(5%, 96px)`, reasoning that a
   percentage alone scales badly on a wide monitor.
8. User: *"what you have apply make the bug look better, but it definitely
   not RC"*, and pointed at the still-present symptom.
9. Asked "do you need more logs" — user's answer, paraphrased: **the log
   system is fine, you are not putting logs in the right places, and dev runs
   should carry more logging by default.**
10. With per-layer logging now covering render backend, data load, and
    per-gesture indicator/volume window state, the user's next log finally
    contained the number that mattered: `visible candles ~155` combined with
    `CHART_CARD_MAX_ZOOM_OUT_CANDLES: 200` in config. That combination says
    the plot never renders more than ~200 candles regardless of loaded
    history — the entire performance premise of the cached-frame preview.
    Benchmarking native pan against the user's real workload (correctly this
    time — see the measurement bug below) showed it costs ~32ms/frame,
    bounded and acceptable. **Root cause:** the cached-frame preview itself.
    It previews a drag by transforming a captured snapshot instead of
    rendering real data; every reported symptom (blank band, chrome sliding,
    a vertical autoscale jump on release, stale indicator lines) follows
    directly from that design and none of them is fixable while the frame
    stays a snapshot. Fix: default it off.

Three attempts, one broken diagnostic channel, before the actual root cause.
The two questions below are about preventing that.

## Why didn't the test suite catch this?

Not because tests were missing — there were nine tests covering the preview
controller before this bug was even reported. The gap is what they checked.

```
$ git grep -c pixelColor <pre-session-commit> -- tests/
(zero matches anywhere in the suite)
```

Every one of the nine existing tests asserted internal state: `is_preview_active`,
the numeric `viewRange()` the preview would commit to, a call count on the
range-update scheduler. All of that state was **always correct** — the
transform math (`shifted_x_range`, `zoomed_x_range`) was right from the start.
The bug was entirely in *what got painted on screen* while that correct state
was being computed. A test suite that never looks at a pixel structurally
cannot see a defect that only exists in pixels.

This was not a one-off oversight in this file. At the point BUG-009 was
reported, `tests/sanity/test_native_chart_qml_plugin_sanity.py` was the only
other file in the entire suite that sampled a pixel — and that covers the
*native* C++ chart, not the *Python* pyqtgraph chart most real sessions
actually run (`BackTestPresenter` falls back to Python whenever a strategy
publishes script regions). The Python chart host — the one this bug lived in
— had **zero** pixel-level coverage at any test level before this session.

Two structural fixes follow, both applied in this session:

- [`scripts/python_backtest_pan_desktop_e2e.py`](../../scripts/python_backtest_pan_desktop_e2e.py) —
  the Python-host counterpart to `native_backtest_desktop_e2e.py`. Drags a
  real window with trending (not flat) synthetic data and asserts, from real
  composited pixels: the price-axis strip never goes empty mid-drag, no more
  than 2% of the plot width is bare overlay background, and the vertical
  jump on mouse release is under 2px. Confirmed to fail (naming the exact
  symptom) when the cached-frame preview is force-enabled, and to pass with
  the fix.
- [`tests/unit/presentation/ui/screens/test_backtest_presenter.py`](../../tests/unit/presentation/ui/screens/test_backtest_presenter.py) —
  `test_backtest_cached_interaction_is_disabled_by_default` pins the actual
  fix (the config default), not just the mechanism inside the feature that
  stays off by default.

The general lesson, now in `.agents/rules/ci-rule.md`'s existing Desktop-E2E
requirement and worth restating here: **a UI/rendering bug report needs a
pixel-level regression test, not a state-level one, at the level (Python host
vs. native host) it was actually observed in.** A green state-level suite is
not evidence a paint defect is fixed.

## Why didn't the logging catch it — three separate failures, not one

**Failure 1: the first diagnostic logging was silent by construction.**
`logging.getLogger(__name__)` inside `src/presentation/ui/components/chart_card/`
produces a logger under `Sagittarius_Elite_Warrior.src.presentation...`.
`StdLogger` never attaches a handler there — only to `"App"`, with
`propagate=False`. The call succeeds, `logger.info(...)` returns normally,
and the message goes nowhere. This is worse than a missing log: it looks
like working instrumentation and consumed a full user round-trip before
being caught, purely because the count of matching lines was zero and that
was noticed. Fixed for the two offending modules
(`cached_frame_interaction.py`, `plot_layout.py`), and now enforced for the
whole tree by
[`tests/unit/test_logging_namespace_guard.py`](../../tests/unit/test_logging_namespace_guard.py),
an AST-based guard that fails CI if any `src/` module logs outside `"App."`.

**Failure 2: even correct logging was placed at the wrong layer, twice.**
After fixing failure 1, the logs were real but still didn't carry the
information that mattered, because they only instrumented the class already
suspected (`CachedFrameInteractionController`) — not the layers around it.
The number that actually broke the case (`~155 candles visible` against a
`CHART_CARD_MAX_ZOOM_OUT_CANDLES` of `200`) required a data-layer log
(`[chart-data]`) that did not exist yet. Fixed by adding `[chart-env]`
(real render backend, OpenGL fallback reason, DPR, platform — logged once at
construction) and `[chart-data]` (candle counts and, per gesture, whether a
coalesced range update is still pending) alongside the interaction-layer
`[cached-frame]` logs. See `.agents/rules/logging-rule.md` §5.

**Failure 3: a benchmark script measured the wrong thing and produced a
confidently wrong number.** Justifying the preview's existence required
comparing it against native panning. The first such benchmark timed
`widget.grab()` around a native `setXRange()` call — but `grab()` is an
offscreen pixmap capture that real interactive panning never performs. It
reported native pan as costing ~52ms/frame; timing the viewport's actual
`paintEvent` on the same workload gave 31.7ms median. The inflated number
made the preview look like a necessary trade-off for another full round,
right up until the `CHART_CARD_MAX_ZOOM_OUT_CANDLES` discovery made its
premise moot regardless of the exact number. Lesson: a rendering benchmark
must time the same code path the real interaction exercises, not a
convenient proxy for it — this project's own `code-rule.md` already says as
much for renderer comparisons generally; this is a concrete instance of
getting it wrong anyway.

## What changed as a result

- `.agents/rules/logging-rule.md` (new) — the eight rules this case study
  justifies: `"App."` namespace only (enforced by a guard test), log
  decisions and fallbacks not just outcomes, mandatory one-shot environment
  lines for UI/rendering code, per-gesture summaries with pixel-scale
  numbers, log what would let a layer be ruled out, `--dev` raises verbosity
  and writes a session log file automatically, stable greppable tags, and
  never trust instrumentation that hasn't been observed to actually emit
  through the real logging configuration.
- `tests/unit/test_logging_namespace_guard.py` (new) — AST scan across all of
  `src/`, fails on any logger that cannot reach `StdLogger`'s handlers.
- `src/presentation/ui/app_bootstrapper.py` — `--dev` now also sets
  `log.level=DEBUG` and `log.file=logs/dev-<timestamp>.log`, so a developer
  session is captured to a file automatically instead of relying on someone
  copy-pasting console scrollback.
- `scripts/python_backtest_pan_desktop_e2e.py` (new) — closes the pixel-level
  coverage gap for the Python chart host specifically.
