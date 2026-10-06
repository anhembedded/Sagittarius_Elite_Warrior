# BUG-164 — An armed live strategy commits its indicators on every forming-candle update

- **Reported:** 2026-10-06 (found while diagnosing BUG-163; BUG-164 reserved by the coordinating session)
- **Severity:** 🟡 P2 — an armed live strategy decides on indicators built from forming prices, not bars; no order can leave while trading is OFF
- **Status:** ✅ Fixed (2026-10-06)
- **Board:** Fixed: `LiveStrategySession.dispatch_tick` fed every kline update, forming ones included, to `StrategyEngine.on_tick`, the closed-candle commit, so indicators took about 240 prices a minute as bars; it now passes only closed candles.
- **Context:** Live strategy → `src/modules/strategy/` → `application/services/` (`LiveStrategySession`)
- **Environment:** Linux reproduction, master-warrior after PR #394; any live armed strategy.

## Reproduction
1. Arm a strategy on a venue; the stream pushes the forming kline roughly every 250 ms (`is_closed=False`, the owner's log shows `Closed: False`).
2. `dispatch_tick` passes each update to `engine.on_tick`.

## Symptom
Unit tier: `engine.on_tick` called once for a candle with `is_closed=False`.

## Root cause
`live_strategy_session.py:198` filtered symbol and interval but not `is_closed`. `IStrategyEngine.on_tick` is documented as evaluating a **closed** candle and committing the indicators (`i_strategy_engine.py:63`); `StrategyEngine._update_indicators` calls `indicator.update(close)` for each, a commit per call. The intended forming-bar path is `on_forming_bar_tick`, provisional and uncommitted (`BOT-042D`), used by the historical-tick backtest only. So BOT-042 did not make `on_tick` provisional; the live session called the committing method with forming data. No net covered it: the session tests only ever used the default `is_closed=True`.

## Fix
`dispatch_tick` returns for a candle that is not closed, next to the symbol and interval filter it already owns. Live does not use `on_forming_bar_tick`: a live order on a provisional bar is a design decision for the owner, not a bug fix.

## Regression test
`tests/unit/modules/strategy/application/services/test_live_strategy_session.py::test_a_forming_candle_never_reaches_the_engine_only_the_closed_one_does` — red before: `Expected 'on_tick' to not have been called. Called 1 times.`; green after.

## Verification
The test red then green; the commit tier and the strategy unit tests (see the PR).
