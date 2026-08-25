# BUG-047 — `test_dashboard_integration_start_stream_chart_rendering`: candlestick history stays empty after Load History + Start Stream

**Reported:** 2026-08-25, surfaced by removing BOT-038's `--ignore` on
`tests/integration/presentation/ui/` — failing on every commit that directory
was excluded from CI, invisibly.
**Severity:** 🟡 P2 — deterministic test failure; production impact not yet
established (candlestick rendering could genuinely be broken, or the mock
setup in this test could no longer match the real data-flow path).
**Status:** ✅ **Fixed 2026-08-25**

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

## Root cause — neither candidate explanation; two independent stale mocks

Neither of the two candidates recorded above was it. `FastCandlestickItem.
update` being patched is unrelated — history population happens before any
paint call. Traced with a debug script constructing the real presenter and
tracing each step (not guessed):

**1. `mock_thread_mgr.submit`'s mock returns `None`, not a `Future`.**
`ExclusiveAction.submit()` (`sagittarius_engine.runtime.tasks`, landed with
**BOT-069**, after this test was first written) does:

```python
future = self._thread_manager.submit(task, *args, **kwargs)
future.add_done_callback(functools.partial(self._release_on_done, key))
```

The fixture's `submit_sync(task, *args, **kwargs): task(*args, **kwargs)`
returns `None` (confirmed empirically: `unittest.mock`'s `side_effect`
returns exactly what the function returns). `None.add_done_callback(...)`
raises `AttributeError` — caught and only logged by `@safe_ui_action`
(**BOT-066**, also landed after this test), never raised in `dev.mode=False`
(this fixture's mode). The crash was invisible; its real effect was that
`ExclusiveAction`'s `"load_history"` slot never released, so the later
`_on_start_stream()` call's own `self._stream_actions.try_start("start_stream")`
returned `False` and silently no-opped — confirmed by tracing: `_on_start_stream`
never even reached its `dispatch()` calls.

**2. `GetHistoricalKlinesQuery`'s mocked response shapes `.data` as a flat
list; production expects a `dict` keyed by symbol.** The query takes
`symbol` as a **list** now (multi-symbol support), and
`GetHistoricalKlinesQueryHandler._execute_multi` returns
`dict[str, list[MarketData]]` (confirmed by reading `handler.py:64-86`
directly). `stream_lifecycle_controller.py`'s `_run_load_history` guards:

```python
results = getattr(response, "data", response) if response else {}
if not isinstance(results, dict):
    self._emit_log("Unexpected response format from history query.")
    return
```

The fixture's `response.data = [mock_kline]` is a `list`, so this guard fires
and returns before ever touching the candlestick — logged, not raised, so
this also stayed invisible.

Both defects are independent; either alone reproduces the failure. Verified
by fixing them one at a time in a throwaway debug script before touching the
real test file — fixing only #1 got the FSM to `LIVE` but `history_data`
stayed `0`; fixing both together produced `history_data == 1`.

## Fix

- `mock_thread_mgr.submit`'s `side_effect` now returns a real
  `concurrent.futures.Future`, populated via `set_result`/`set_exception`
  around the synchronous call — matching what a real thread pool's `submit()`
  contract actually returns.
- `mock_dispatch`'s `GetHistoricalKlinesQuery` response is now
  `{sym: [mock_kline] for sym in cmd.symbol}` — keyed by symbol, matching
  `_execute_multi`'s real return shape.

No production code touched — both defects were in the test's own mocks,
stale against two later, unrelated production changes (BOT-066, BOT-069).
Verified red-then-green: reproduces the original `AssertionError: assert 0 ==
1` before the fix, passes after.

Full gate re-run clean: 1,801 passed, 4 skipped, 0 failed.
