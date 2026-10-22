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
`interval_toolbar.py` → `INTERVALS` (four intervals) was passed as `offered_codes` at 284a5aa, "offering only what a backtest replays" (EPIC-040D). Nothing in the replay needs that: `run_grid_backtest/handler.py` → `RunGridBacktestQueryHandler.execute` counts and loads stored candles at `query.interval`, derives the step from `interval.to_seconds()`, and reads fine klines at 1s whatever the interval; `MAX_CANDLES` (20,000) refuses an over-long period with "choose a shorter period or a longer interval". The sync (`workbench_selection.py` → `sync_requests`) fetches the chosen interval plus 1s. So the restriction was a choice, not a limit, for 1s to 1d; the one interval that cannot *load* is `1s` on Futures (`core/vo/market_timeframes.py`: Binance USD-M serves no 1s klines). **Review round 1 (PR #721) showed that 3d, 1w and 1M cannot be *judged* truthfully:** `grid_simulator.py` → `_closed_candles` counts expected candles on the epoch-aligned grid, but Binance's 3d candles open one day off it (measured on `data.binance.vision`, BTCUSDT 3d, 2024-08: Aug 1, 4, 7), weekly ones on Mondays and monthly ones on the 1st; and `TimeFrame.to_seconds` gives a month 30 days, so a 1M bar's 1-second window spills into the next month. A fully stored period would read "partly stored" with a Sync that cannot clear it.

## 2. Acceptance criteria
- [x] The picker offers every `TimeFrame` the replay judges (all but 3d, 1w, 1M, see §3) in the chart's groups (SECONDS, MINUTES, HOURS, DAYS AND UP) with the heavy-data warning; default 15m and the pins 1m/5m/15m/1h unchanged.
- [x] A Futures bot is not offered `1s`; a chosen `1s` moves to `1m` when a Futures bot is followed.
- [x] 3d, 1w and 1M are not offered, and the set is locked by a test (`UNREPLAYED_INTERVALS`).
- [x] A backtest replays from stored candles at 3m, 4h and 1d, and its data window reads whole (expected = stored); with 1-second klines at 3m the fine path runs with no coarse period.
- [x] A sync at 1s asks for the 1-second series once.

## 3. Design
`interval_toolbar()` passes no `offered_codes`; `INTERVALS` becomes `PINNED_INTERVALS` (the first row). The view asks the toolbar's existing `set_market` (BOT-167) from the followed plan's venue, once per market change. `1s` on Spot is offered: the candles and the fine klines are then the same series and it runs. 3d, 1w and 1M are left out until the replay takes each bar's end from the venue's calendar and counts expected candles on the venue's boundaries (the mechanism fix, a task of its own); `interval_toolbar.py` → `UNREPLAYED_INTERVALS` records the reason and its retire condition.

**Deferred, with reason (review finding 4):** `sync_requests` always adds the period's 1-second klines, bounded by nothing but `MAX_CANDLES` on the chosen interval, so a year at 1d syncs about 31.5M one-second rows. It is the existing behaviour of the Sync offer for every interval and is cancellable ("Stop"); bounding it is a product decision (refuse in words, or skip the 1-second klines past a limit and replay coarse, which the replay already labels), put to the owner by the coordinator.

## 3a. Reuse
`ChartToolbar.set_market`, `market_timeframes.supports_timeframe`, `TimeframePickerDialog`: used. Nothing new.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/backtest_workbench/interval_toolbar.py` | no subset; `PINNED_INTERVALS` |
| `src/modules/bots/ui/backtest_workbench/backtest_workbench_view.py` | `offer_intervals_of` |
| `src/modules/bots/ui/backtest_workbench/backtest_workbench_presenter.py` | tells the view the plan's market |
| `tests/unit/modules/bots/ui/backtest_workbench/test_workbench_interval.py` | full picker, groups, warning, Futures |
| `tests/integration/modules/bots/test_grid_backtest_stored_klines.py` | replay at 3m, 4h, 1d with the data window asserted; the 3m fine-klines path |

## 5. Testing
Unit tier: `test_workbench_interval.py` (the full picker without 3d/1w/1M, the locked excluded set, Futures without 1s, the 1s sync once). Integration tier: `test_a_period_replays_at_an_interval_other_than_the_default_from_stored_candles`. Commit tier, architecture guards and the touched tests run locally; the full gate is the PR's `-Full` run.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (workbench paragraph), `Docs/SPEC/SPEC-014_run_a_grid_bot.md` step 9.

## Implementation notes (written when done)
Pending the PR's `-Full` run.
