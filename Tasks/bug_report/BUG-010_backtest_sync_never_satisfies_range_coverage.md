# BUG-010 — "Đồng bộ dữ liệu ngay" never satisfies Backtest range coverage, no matter how many times it's clicked

**Reported:** 2026-08-18
**Severity:** P1 — user-visible, blocks running a Backtest at all in this state
**Status:** Reported — not yet root-caused in code

## Symptom

Screenshot evidence (Backtest screen, range = "Toàn bộ lịch sử", symbol
BTCUSDT, 1m): the coverage banner keeps showing "Thiếu nến từ 2026-08-18
10:37 UTC." and "Đồng bộ thất bại: Đồng bộ chưa đủ để chạy Backtest: Dữ liệu
local chưa đủ cho khoảng Backtest đã chọn." User clicked "Đồng bộ dữ liệu
ngay" repeatedly — it never clears.

Real log for one such session (`run-ui.ps1`, default Python chart backend —
this is unrelated to native/F6D):

```
17:41:05 Executing query: GetBacktestRangeCoverageQuery
17:41:05 Executing command: SyncMarketDataCommand
17:41:06 [BTCUSDT] Syncing from latest timestamp: 2026-08-18 10:36:00+00:00
17:41:07 Successfully fetched 6 klines for BTCUSDT.
17:41:07 Executing query: GetBacktestRangeCoverageQuery
17:41:09 Executing command: SyncMarketDataCommand
17:41:09 [BTCUSDT] Syncing from latest timestamp: 2026-08-18 10:41:00+00:00
17:41:10 Successfully fetched 1 klines for BTCUSDT.
17:41:10 Executing query: GetBacktestRangeCoverageQuery
17:41:12 Executing command: SyncMarketDataCommand
17:41:12 [BTCUSDT] Syncing from latest timestamp: 2026-08-18 10:41:00+00:00
17:41:12 Successfully fetched 1 klines for BTCUSDT.
17:41:13 Executing command: SyncMarketDataCommand
17:41:13 [BTCUSDT] Syncing from latest timestamp: 2026-08-18 10:41:00+00:00
17:41:14 Successfully fetched 1 klines for BTCUSDT.
```

Every sync reports success (never an error), but the checkpoint
("Syncing from latest timestamp: ...") stops advancing past `10:41:00` even
though several syncs complete afterward, each fetching exactly 1 kline. The
coverage query never comes back satisfied, so the UI banner never clears.

## Suspected area (not yet confirmed)

Two candidate mechanisms — neither verified against the actual source yet,
do not assume either is correct without checking:

1. **Unclosed-candle boundary:** `BackTestPresenter._run_backtest()` is
   known to compute a `_published_candle_cutoff(datetime.now(UTC), timeframe)`
   specifically to avoid ever requesting/using a still-forming candle
   (lookahead-bias guard). If `GetBacktestRangeCoverageQuery` and/or the
   auto-sync loop's target end-time do *not* apply that same cutoff — i.e.
   they treat "now" as the target instead of "last published candle" — then
   coverage could be permanently checking for a candle that can never exist
   yet (the currently-forming one), which sync then can never satisfy no
   matter how many times it runs, since a new "now" appears the instant the
   previous one closes.
2. Alternatively: the sync checkpoint advancing to `10:41:00` and then
   fetching 1 kline per subsequent call without the checkpoint itself
   advancing suggests the newly-synced candle may not be getting persisted/
   counted as the new "latest" before the next `GetBacktestRangeCoverageQuery`
   /`SyncMarketDataCommand` pair runs — worth checking for a read-after-write
   consistency issue or an off-by-one in what counts as "latest."

## Scope note

Confirmed **unrelated to BOT-098F6D** — this is `SyncMarketDataCommand` /
`GetBacktestRangeCoverageQuery` application-layer logic, nothing to do with
chart rendering (native or Python). The log shows the default Python chart
backend was active in this session.

## Next steps (when picked up)

1. Reproduce with `--dev` for full trace logging, and inspect exactly what
   end-time `GetBacktestRangeCoverageQuery` computes for the "Toàn bộ lịch
   sử" range vs. what `_run_backtest()`'s own `_published_candle_cutoff()`
   would compute for the same moment — confirm or rule out hypothesis 1
   directly by comparing the two.
2. Check whether the auto-sync-then-recheck loop has any retry/backoff limit
   at all, or whether it is designed to loop indefinitely on principle —
   if the true fix is "align the coverage check's cutoff with the
   backtest-run cutoff," that's a different fix than "cap the retry loop and
   surface a clear terminal error."
3. Write a regression test reproducing the exact coverage-vs-cutoff mismatch
   before fixing it (this project's standing rule: test first, then fix).
