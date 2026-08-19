# BUG-017 — Backtest screen's "Đồng bộ ngay" re-downloads the entire requested range from Binance even when most of it is already cached locally

**Reported:** 2026-08-20, user noticed the sync progress bar climbing to
684,801 candles for a 7-day `BTCUSDT` range and asked whether it checks the
local database first.
**Severity:** P2 — wasted network I/O and needless wait time on every sync,
not a correctness bug (no duplicate rows are created; see Investigation).
**Status:** Open — root cause found and confirmed by reading, not yet fixed.

## Symptom

Backtest screen, `BTCUSDT` / `Ema Trend Confirm Pullback` / `1m` / "7 ngày
qua" (Realtime execution mode, so the actual synced interval is
`tick_resolution`, not the `1m` shown in the toolbar — see
`BackTestPresenter._effective_data_interval()`). Coverage check correctly
reports a narrow gap: `"Thiếu nến từ 2026-08-19 12:51 UTC."` — meaning
everything before that timestamp is already in the local DB. Despite that,
clicking "Đồng bộ ngay" shows `Đang đồng bộ nến: 192,000/684,801` — a total
consistent with re-fetching the **entire** ~7-8 day range at 1s resolution
from Binance, not just the missing ~10-hour tail.

## Root cause

Two pieces, confirmed by reading (no execution needed — the logic is
unconditional):

1. `GetBacktestRangeCoverageQueryHandler` (`src/application/use_cases/queries/get_backtest_range_coverage/handler.py`)
   correctly queries the DB and finds the real gap start
   (`coverage.missing_open_times[0]`) — the coverage-detection side of this
   is DB-aware and working as intended.
2. `BackTestPresenter._run_sync()` (`src/presentation/ui/screens/backtest/backtest_presenter.py:2384-2395`)
   ignores that gap entirely and always builds
   `SyncMarketDataCommand(start_time=config.start_time, ...)` — `config.start_time`
   is the **original requested range's start** (e.g. "7 ngày qua"'s own
   start), not the gap's start.

`SyncMarketDataCommandHandler._determine_start_time()`
(`src/application/use_cases/sync/sync_market_data/handler.py:92-114`) does
have exactly the logic that would fix this — resume from
`self.repo.get_latest_kline_time(symbol, interval)` when no explicit start
is given — but that branch only runs `if command.start_time` is falsy.
Because the Backtest screen's sync trigger always supplies an explicit
`start_time`, that branch never has a chance to run in this code path, even
though it demonstrably works correctly elsewhere (this is the exact
mechanism a plain incremental sync with no explicit range relies on).

`IExchangeClient.get_historical_klines()`
(`src/infrastructure/binance/client.py:120-148`) also does not consult the
local DB itself — it always fetches over the network for whatever
`[start_str, end_str]` it's given, so nothing downstream of the presenter
catches this either.

**Not a data-correctness bug**: `IMarketDataRepository.save_klines()` is
presumed idempotent per-timestamp (re-saving already-present candles does
not duplicate rows) — this needs a one-line confirmation read of
`save_klines()`'s implementation before the fix lands, but even without
that confirmation the observed symptom (huge total count, slow sync) is
explained entirely by the redundant network fetch, independent of whatever
the save step does with the redundant rows.

## Suggested fix (not yet attempted)

In `BackTestPresenter._run_sync()`, pass the coverage-detected gap start
instead of the full requested range start when a gap was already found —
i.e. thread `coverage.missing_open_times[0]` (already computed by
`_probe_data_coverage()` just before `_start_sync_for_config()` is called)
through to the `SyncMarketDataCommand(start_time=...)` construction, falling
back to `config.start_time` only when there is no prior coverage probe
result to use (e.g. a cold DB with zero cached candles, where the whole
range genuinely is missing). Needs a regression test that seeds the DB with
a partial range, triggers sync, and asserts the dispatched
`SyncMarketDataCommand.start_time` equals the gap start, not the original
requested start — a `Mock`-based assertion on the dispatched command is
the right tier here (no real network call needed to prove the fix, per
this repo's own gotcha about mocks hiding real logic: this one specifically
must NOT mock away `_probe_data_coverage`/`GetBacktestRangeCoverageQuery`,
or the test would pass without ever exercising the real gap-detection value
being threaded through).

## Reproduction

1. Sync a real symbol/interval for a short range so the DB has data through
   some known timestamp `T`.
2. Open Backtest screen, pick the same symbol, a range starting well before
   `T` and ending after it (so the DB covers the first portion only).
3. Click "Đồng bộ ngay" and watch `Đang đồng bộ nến: X/Y` — `Y` will be
   sized for the full requested range, not just the portion after `T`.
