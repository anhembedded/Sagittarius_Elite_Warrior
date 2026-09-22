# BUG-133 — Historical Tick Backtest never enforces Stop Loss / Take Profit / liquidation

- **Reported:** 2026-09-22 (discovered while wiring `BOT-106B` MAE/MFE excursion tracking into `PaperExchange.check_intrabar_stops()`)
- **Severity:** 🟡 P2 — every Historical Tick Backtest (`RunHistoricalTickBacktestCommand`, `BOT-076`) silently runs with SL, TP and liquidation completely disabled, so its results overstate performance and risk for any strategy or config that relies on them (which `BOT-041`/`BOT-049` both assume every backtest mode provides). Not 🔴 P1: backtesting only, no live capital at risk directly, but every user decision made from a Historical Tick Backtest report is downstream of this gap.
- **Status:** Open
- **Context:** Use Case: Historical Tick Backtest (`BOT-076`) → Module: `src/modules/backtesting/` → Sub-module / Layer: `application/run_historical_tick_backtest/`
- **Environment:** Current `master-warrior` tip plus every commit since `BOT-041` (2026-xx-xx, SL/TP) and `BOT-049` (2026-09, leverage/liquidation) — both were wired only into `PaperExchange.check_intrabar_stops()`, never into this handler's own loop.

## Reproduction

1. Run any `RunHistoricalTickBacktestCommand` (Historical Tick Backtest) against a strategy/config with a stop-loss, take-profit, or leverage > 1x configured.
2. Compare against the same config run as a `RunStaticBacktestCommand` (Static Backtest) over the same range.
3. **Expected:** both engines apply the same SL/TP/liquidation rules to open positions every bar, per `BOT-041`'s and `BOT-049`'s stated design ("SL/TP are a property of the position that `PaperExchange` itself watches, every bar, regardless of run mode" — `Tasks/backlog/BOT-077_calc_on_order_fills.md` §2 states this explicitly as the reason `BOT-077` is *not* needed to protect the user from SL delay).
4. **Actual:** Static enforces every rule every bar (`run_static_backtest/handler.py:286`, `exchange.check_intrabar_stops(...)` runs unconditionally every bar). The Historical Tick Backtest handler (`run_historical_tick_backtest/handler.py`) never calls `check_intrabar_stops()` anywhere in `_simulate()` or `_commit_bar()` — a position opened in tick mode can only ever close via a strategy-emitted signal or the final `force_close()`, never via its own stop-loss, take-profit or liquidation price. Frequency: 100%, every run of this handler.

## Symptom

```
$ grep -n "check_intrabar_stops" src/modules/backtesting/application/run_historical_tick_backtest/handler.py
# (no output — zero matches)
$ grep -n "check_intrabar_stops" src/modules/backtesting/application/run_static_backtest/handler.py
286:            exchange.check_intrabar_stops(
```

No traceback, no exception — a silent behavioral gap. A leveraged or SL/TP-bearing position opened mid-run in tick mode rides to whatever price the strategy's own next signal (or the run's final tick) happens to close it at, including past its own `liquidation_price` with no clamp (`MarginRiskPolicy.clamp_liquidation_settlement()` is dead code on this path).

## Root cause

`check_intrabar_stops()` was added to `PaperExchange` alongside `BOT-041`, and `run_static_backtest/handler.py:281-288`'s own comment ("must run every bar, signal or not") shows the author was aware it needs an explicit per-bar call site outside the signal-fill path. `run_historical_tick_backtest/handler.py` (`BOT-076`) was written as, and is documented as ("the second, permanently parallel backtest mode... never merged into" Static — module docstring, `handler.py:53-60`), a structurally separate loop that mirrors Static's shape (`on_tick`/`on_forming_bar_tick`, `exchange.fill(...)`) but never received the equivalent call. `BOT-049` (leverage/liquidation, landed later) extended `check_intrabar_stops()` further without any check for other call sites, so the same gap silently widened to cover liquidation too, then again to MAE/MFE while investigating this (`BOT-106B`). This is a missing mechanism at one specific call site, not a design defect in `PaperExchange`/`check_intrabar_stops()` itself — the fix is one line per handler branch, but *where* to call it needs care: unlike Static's one bar-close per iteration, this handler has two candle representations per tick (the still-forming bar, `_commit_bar`'s just-closed bar) and the correct call rate (once per tick vs. once per committed bar) affects both correctness and performance at the tick counts this handler is optimized for (`BUG-051`/`BUG-033`, both in this same file, exist specifically because this handler runs on millions of rows).

## Fix

Not yet implemented — filed as Open per `create-bug-report-rule.md` §2 rather than folded silently into `BOT-106B`, which discovered it but does not own fixing it (`ONBOARDING.md` §7: no unrequested scope expansion). `BOT-106B`'s own MAE/MFE tracking is therefore honestly scoped to Static-mode-only until this closes, documented in `Tasks/completed/BOT-106B_*.md`.

## Regression test

Not yet written — belongs with the fix. Candidate: a test mirroring `test_one_tick_per_bar_matches_static_exactly` (`tests/unit/modules/backtesting/application/test_run_historical_tick_backtest.py`) but with a stop-loss/leverage config that both engines resolve differently absent this fix.

## Verification

Not run.

## Suggested next steps

- Decide the call rate deliberately (once per tick vs. once per committed bar vs. once per forming-bar evaluation) with the same performance discipline `BUG-051`/`BUG-033` already established for this handler, before wiring it in.
- Re-run `test_one_tick_per_bar_matches_static_exactly` once fixed — it is the existing bit-for-bit cross-check between the two engines and should keep passing.
- Re-enable `BOT-106B`'s MAE/MFE tracking for tick mode as part of, or immediately after, this fix.
