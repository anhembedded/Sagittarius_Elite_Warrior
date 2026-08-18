# BOT-098F6F — Native Equity/BOTH subplot support

**Parent:** [`BOT-098F6`](BOT-098F6_backtest_chart_host_migration.md)
**Depends on:** `BOT-098F6D` ✅ (wiring exists; this closes the capability gap it deliberately left open)
**Priority:** P2
**Complexity:** L
**Status:** Backlog

## Goal

Extend the native Backtest chart host to cover `ChartDisplayMode.EQUITY` and
`ChartDisplayMode.BOTH`, which `BOT-098F6` (the whole `F6A→F6E` migration)
explicitly scoped out: today, selecting either mode always forces the Python
host regardless of the configured backend
(`NativeBacktestChartHostAdapter.add_subplot_indicator()` and non-candlestick
`set_chart_type()` both raise `NativeUnsupportedFeatureError`, and
`BackTestView._effective_chart_backend()` forces `"python"` for any mode other
than OHLC). This task is what makes native chart backend behave the same
across every Backtest chart mode.

## Why this isn't scoped yet

No prior `BOT-098F` phase designed for this. `NativeChartItem` currently
renders exactly one price plot plus integrated volume; it has no line-series
draw mode and no second, independently-scaled subplot region. Both are new
retained-geometry work in `native/chart_renderer/`, not adapter-level plumbing
— this is why it was cut from `F6A→F6E` rather than deferred as "just wire it
up later."

## Open questions to resolve with the user before implementation

1. **Equity line rendering:** does `NativeChartItem` gain a real polyline/line
   draw mode, or does equity stay a degenerate synthetic-OHLC series reusing
   the existing candle geometry (as `PythonBacktestChartHost` already does via
   `equity_curve_to_candles()`)? The latter is far cheaper but was an
   intentional Python-only shortcut, not necessarily one worth carrying into
   native.
2. **BOTH mode's second plot:** does this need a true native subplot region
   (separate `QQuickItem`/geometry layer, independently scaled Y axis), or is
   an overlay-normalized equity line on the same viewport acceptable?
   `ChartCard._add_or_update_equity_subplot()`'s current Python behavior is
   the baseline to match or consciously diverge from.
3. **Scope boundary:** does this task also need to cover script regions/info
   and arbitrary script marker text (also excluded by `F6A→F6E`), or is that
   deliberately left for a separate follow-on task?

## Acceptance criteria (draft — confirm after the open questions above are answered)

1. `NativeBacktestChartHostAdapter.set_chart_type("line")` and
   `add_subplot_indicator(...)` (or their eventual equivalents) render real
   native geometry instead of raising `NativeUnsupportedFeatureError`.
2. `BackTestView._effective_chart_backend()` no longer forces Python for
   `ChartDisplayMode.EQUITY`/`BOTH` when native is configured.
3. Visual/semantic parity with the existing Python equity curve and BOTH
   subplot (same data, same scale behavior) — proven the same way `F3`/`F4`
   proved OHLC/volume/indicator/marker parity, not just "renders something."
4. Existing OHLC-only native tests and fallback behavior (missing plugin, ABI
   mismatch, other still-unsupported features) remain unchanged.
5. Four-level test contract (`.agents/rules/ci-rule.md` §6): Unit for the new
   geometry/adapter logic, Integration for the Backtest mode-switch flow,
   Sanity for real app boot with native+BOTH configured, Desktop E2E through
   the real running app for the newly-supported modes (mirroring
   `scripts/native_backtest_desktop_e2e.py` from `BOT-098F6D`).
6. `./scripts/ci-local.ps1 -Full` passes.
