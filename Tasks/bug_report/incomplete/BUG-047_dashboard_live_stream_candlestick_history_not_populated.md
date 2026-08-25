# BUG-047 — `test_dashboard_integration_start_stream_chart_rendering`: candlestick history stays empty after Load History + Start Stream

**Reported:** 2026-08-25, surfaced by removing BOT-038's `--ignore` on
`tests/integration/presentation/ui/` — failing on every commit that directory
was excluded from CI, invisibly.
**Severity:** 🟡 P2 — deterministic test failure; production impact not yet
established (candlestick rendering could genuinely be broken, or the mock
setup in this test could no longer match the real data-flow path).
**Status:** 🔴 Open

## Symptom

```
tests/integration/presentation/ui/test_dashboard_live_stream.py:114: in test_dashboard_integration_start_stream_chart_rendering
    assert len(card.candlestick.history_data) == 1
AssertionError: assert 0 == 1
 where 0 = len([])
 where [] = ...FastCandlestickItem(...).history_data
```

`presenter.active_charts` does contain the expected `"ETHUSDT"` card (that
assertion passes) — only the candlestick's `history_data` is empty after
`_on_load_history()` + `_on_start_stream()` are called in sequence.
Deterministic — fails standalone, reproduces identically at `f27649e`.

## Not yet root-caused

Two candidate directions, neither confirmed:

1. The test patches `FastCandlestickItem.update` (to track render calls without
   a real paint), and that patch may be intercepting more than intended — e.g.
   if `update()` is also where history gets appended, mocking it would silently
   swallow the append instead of only suppressing the repaint.
2. A real regression in the Load History → Start Stream → candlestick
   population pipeline, independent of the test's own mocking.

## Regression test

This test itself is the regression test once fixed. Follow
`.agents/rules/bug-fix-rule.md`: confirm the fail reason first (mock leaking
into data population vs. a genuine pipeline break) before changing either the
test or `src/`.
