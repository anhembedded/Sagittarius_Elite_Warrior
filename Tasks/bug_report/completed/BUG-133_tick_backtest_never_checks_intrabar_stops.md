# BUG-133 — Historical Tick Backtest never enforces Stop Loss / Take Profit / liquidation

- **Reported:** 2026-09-22 (discovered while wiring `BOT-106B` MAE/MFE excursion tracking into `PaperExchange.check_intrabar_stops()`)
- **Severity:** 🟡 P2 — every Historical Tick Backtest (`RunHistoricalTickBacktestCommand`, `BOT-076`) silently runs with SL, TP and liquidation completely disabled, so its results overstate performance and risk for any strategy or config that relies on them (which `BOT-041`/`BOT-049` both assume every backtest mode provides). Not 🔴 P1: backtesting only, no live capital at risk directly, but every user decision made from a Historical Tick Backtest report is downstream of this gap.
- **Status:** ✅ Fixed (2026-09-22)
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

**Call rate decided: once per tick, using that tick's own `high_price`/`low_price`** — not once per committed bar. `run_historical_tick_backtest/handler.py`'s `_simulate()` loop now calls:

```python
exchange.check_intrabar_stops(tick.high_price, tick.low_price, tick.close_time)
```

right after the forming-bar bookkeeping (absorbing the tick into `forming`, or starting a new one), and before the branch that decides whether this tick commits the bar or is only provisional. Rejected the "once per committed bar" alternative deliberately: this handler's entire reason to exist (`BOT-076`) is catching a stop the instant a real tick crosses it, at `tick_resolution` (e.g. 1s), not waiting for a whole `interval` bar (e.g. 5m) to close the way Static must — checking only the aggregated per-bar high/low would throw away exactly the resolution advantage tick backtesting is for. Placed before this tick's own signal evaluation/fill, mirroring `run_static_backtest/handler.py`'s own ordering (check existing positions against this unit's range before deciding this unit's own new signal) and `BOT-110`'s established "read state before this tick's own fill" convention already used twice elsewhere in this same file.

Performance: `check_intrabar_stops()` early-returns (`if not self._positions: return []`) whenever no position is open, which is the common case for most of a run — the added per-tick cost when flat is one attribute check, not a new O(ticks) burden on the millions-of-rows counts `BUG-051`/`BUG-033` already tuned this handler for.

## Regression test

`tests/unit/modules/backtesting/application/test_run_historical_tick_backtest.py::test_stop_loss_closes_the_position_with_no_strategy_exit_signal` — mirrors `test_stop_loss_closes_the_position_on_a_bar_with_no_strategy_signal` (`test_run_static_backtest.py`). `_BuyThenHoldStrategy` buys once then holds forever (never emits its own exit), a 5% stop-loss is configured, and the price drops 10% one bar after entry with no recovery. **Failed before the fix** with `exit_reason == ExitReason.END_OF_BACKTEST` (position rode to the final `force_close()`, exactly the reported symptom) instead of `ExitReason.STOP_LOSS` at the exact stop price (95.0). Mutation-verified: replacing the new `check_intrabar_stops()` call with `pass` reproduces the identical original failure; restoring it returns to green.

## Verification

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=.. .venv/bin/python -m pytest tests/unit/modules/backtesting/application/test_run_historical_tick_backtest.py -q
```
16 passed, including the new regression test and the existing `test_one_tick_per_bar_matches_static_exactly` bit-for-bit cross-check (still green — the ema strategy in that test never configures SL/TP, so the new call is a no-op there beyond the flat-position early return).

Full `tests/unit/modules/backtesting` suite: 742 passed. `ruff`/`mypy` clean on all 646 source files.

## Suggested next steps (resolved)

- ~~Decide the call rate deliberately...~~ Done — see Fix above.
- ~~Re-run `test_one_tick_per_bar_matches_static_exactly` once fixed...~~ Done — still green.
- **Re-enabling `BOT-106B`'s MAE/MFE tracking for tick mode is now unblocked** (this bug was the reason it was Static-only), but doing so is out of this bug's own scope — `Trade.mae_percent`/`.mfe_percent` will start populating for tick-mode trades automatically now that `check_intrabar_stops()` runs (it already calls `_update_excursion_tracking()` internally), with no further code change needed; `Tasks/completed/BOT-106B_*.md`'s "vô hiệu ở Historical Tick Backtest" caveat is stale as of this fix and should be revisited when that task file is next touched.
