# BOT-234 — A calendar-aware Backtest replay, so 3d, 1w and 1M can be offered

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** The Backtest workbench leaves out 3d, 1w and 1M because the replay counts expected candles and windows 1-second prices on an epoch-aligned, fixed-length grid that those candles do not follow; make the replay take each bar's end from the venue's calendar, then offer them.
**Source:** PR #721 review round 1 (BOT-232), and the coordinator, 2026-10-22: "File the calendar-aware replay as a backlog BOT task". The owner had asked for the chart's full interval list.
**Risk:** 🟡 — it changes the replay's window arithmetic that every interval shares
**Complexity:** M — the bar end, the expected count and a test per interval, no new layer
**Epic (optional):** [EPIC-040](epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** [BOT-232](BOT-232_the_backtest_workbench_offers_every_interval.md) (the exclusion this lifts)

---

## 1. Context and problem
`src/modules/bots/ui/backtest_workbench/interval_toolbar.py` → `UNREPLAYED_INTERVALS` holds 3d, 1w and 1M out of the picker. Evidence (PR #721 review, round 1, head `bee6c50`):
- `src/modules/bots/domain/grid/grid_simulator.py` → `simulate_grid` uses `bar_length` (`TimeFrame.to_seconds`) as each candle's 1-second window and close date, and `closed_candles` counts expected candles on the epoch-aligned grid.
- `TimeFrame.ONE_MONTH.to_seconds()` is a fixed 30 days: February's bar ends on 3 March and replays March 1–2's 1-second prices, and the March bar then never sees them (`StreamedFineKlines` is forward-only); a 31-day month loses its last day.
- Weekly candles open on Monday and the epoch was a Thursday: with every candle stored, a Thursday-to-Thursday period expects 4 and finds 3, so the page says "partly stored" and offers a Sync that cannot clear it.
- 3d candles open one day off the epoch's multiples of three (measured on `data.binance.vision`, BTCUSDT 3d, 2024-08: Aug 1, 4, 7).

## 2. Acceptance criteria
- [ ] A bar's end is the next bar's open (the last one's from the venue's calendar), so a month's 1-second prices are replayed in that month.
- [ ] The expected candles of a period are counted on the venue's real boundaries per interval (3d, 1w, 1M included), so a fully stored period reads whole.
- [ ] 1d and shorter intervals replay byte-identically to today (`pitfalls/source.md` 2).
- [ ] `UNREPLAYED_INTERVALS` is empty (or removed) and the picker offers 3d, 1w and 1M; the test that locks the set is replaced by one that locks the new truth.
- [ ] Integration tests with Monday-aligned weekly and calendar-month candles **with** 1-second klines assert the data window (expected = stored) and the fills of the right month.

## 3. Design
To be decided at implementation; the seam is where `bar_length` is used as a duration: a `BarCalendar` (a port or a small value object) that answers a bar's end and the closed candles in a period, with the fixed-length one for the intervals up to 1d.

## 3a. Reuse
To be filled when taken: `TimeFrame`, `grid_simulator.closed_candles`, `StreamedFineKlines`.

## 4. Changes, per file
To be filled when taken.

## 5. Testing
Per the acceptance criteria: unit tests of the calendar per interval, the integration tier on real SQLite shards.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (workbench paragraph, `UNREPLAYED_INTERVALS`), `Docs/SPEC/SPEC-014_run_a_grid_bot.md` step 9.
