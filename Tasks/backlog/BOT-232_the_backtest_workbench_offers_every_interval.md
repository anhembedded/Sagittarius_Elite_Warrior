# BOT-232 — The Backtest workbench offers every interval the bot's market loads

**Status:** 🟡 In progress
**Board:** The workbench's "More timeframes…" listed only 1m, 5m, 15m and 1h by a deliberate EPIC-040D choice; the replay works on any interval, so the picker now offers 1s to 1M in the chart's groups (Futures without 1s, which it serves no klines for).
**Source:** the owner, 2026-10-22, with screenshots: the Select Timeframe dialog "lists only 1m, 5m, 15m and 1h"; the chart's picker lists every interval; the owner calls the short list a bug.
**Risk:** 🟢 — a wider choice; the replay refuses a period over 20,000 candles in words
**Complexity:** S — one constant dropped, one market hook
**Epic (optional):** [EPIC-040](epics/EPIC-040_backtest_workbench/README.md)
**SPEC (optional):** [SPEC-014](../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None

---

## 1. Context and problem
`interval_toolbar.py` → `INTERVALS` (four intervals) was passed as `offered_codes` at 284a5aa, "offering only what a backtest replays" (EPIC-040D). Nothing in the replay needs that: `run_grid_backtest/handler.py` → `RunGridBacktestQueryHandler.execute` counts and loads stored candles at `query.interval`, derives the step from `interval.to_seconds()`, and reads fine klines at 1s whatever the interval; `MAX_CANDLES` (20,000) refuses an over-long period with "choose a shorter period or a longer interval". The sync (`workbench_selection.py` → `sync_requests`) fetches the chosen interval plus 1s. So the restriction was a choice, not a limit; the one interval that cannot load is `1s` on Futures (`core/vo/market_timeframes.py`: Binance USD-M serves no 1s klines).

## 2. Acceptance criteria
- [x] The picker offers every `TimeFrame` in the chart's groups (SECONDS, MINUTES, HOURS, DAYS AND UP) with the heavy-data warning; default 15m and the pins 1m/5m/15m/1h unchanged.
- [x] A Futures bot is not offered `1s`; a chosen `1s` moves to `1m` when a Futures bot is followed.
- [x] A backtest replays from stored candles at 3m, 4h, 1d and 1w.

## 3. Design
`interval_toolbar()` passes no `offered_codes`; `INTERVALS` becomes `PINNED_INTERVALS` (the first row). The view asks the toolbar's existing `set_market` (BOT-167) from the followed plan's venue, once per market change. The "not replayable" interval was not hidden for `1s` on Spot: the replay's candles and fine klines are then the same series and it runs.

## 3a. Reuse
`ChartToolbar.set_market`, `market_timeframes.supports_timeframe`, `TimeframePickerDialog`: used. Nothing new.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/backtest_workbench/interval_toolbar.py` | no subset; `PINNED_INTERVALS` |
| `src/modules/bots/ui/backtest_workbench/backtest_workbench_view.py` | `offer_intervals_of` |
| `src/modules/bots/ui/backtest_workbench/backtest_workbench_presenter.py` | tells the view the plan's market |
| `tests/unit/modules/bots/ui/backtest_workbench/test_workbench_interval.py` | full picker, groups, warning, Futures |
| `tests/integration/modules/bots/test_grid_backtest_stored_klines.py` | replay at 3m, 4h, 1d, 1w |

## 5. Testing
Unit tier: `test_workbench_interval.py` (four new cases). Integration tier: `test_a_period_replays_at_an_interval_other_than_the_default_from_stored_candles`. Commit tier, architecture guards and the touched tests run locally; the full gate is the PR's `-Full` run.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (workbench paragraph), `Docs/SPEC/SPEC-014_run_a_grid_bot.md` step 9.

## Implementation notes (written when done)
Pending the PR's `-Full` run.
