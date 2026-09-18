# SPEC-001 — Bring a symbol's candle history up to date

- **Status:** ✅ built and proven
- **Actor:** trader (from a screen), operator (from the command line)
- **Origin:** measured from the code. The behaviour predates this directory; `BUG-010`,
  `BUG-025`, `BOT-121` and `BOT-122` are the four reports that shaped it.
- **Surfaces:** Data Management screen (one symbol, and bulk) · Dev Board's *Load History* and
  *Start Live* (their fetch phase) · Backtest screen's data sync · `sync` on the command line and
  at the interactive prompt.

## 1. Trigger

*"I want candles for this symbol and timeframe, and I do not know how much of it I already
have."*

That last clause is the whole use case. The actor never asks for a **range**; they ask for the
store to be current, and the app decides where to start reading from.

## 2. Preconditions

1. The app is running — either the desktop window, `python -m src.main sync …`, or `sync` typed
   at the interactive prompt.
2. The symbol is a Binance Futures pair. An unknown symbol is a failure row below, not a
   precondition the actor has to check first.
3. The timeframe is one of the sixteen `TimeFrame` values (`1s` … `1M`); the command line
   restricts `--interval` to exactly that list through `src/config/cli_commands.json`.
4. No API credentials are needed. This use case reads public market data.

## 3. Main flow

1. The actor names a symbol and a timeframe, and starts the sync.
2. The app looks in the local store for the newest candle it already holds for that pair.
3. **If there is one**, the app continues from it. **If the store is empty for that pair**, the
   app reaches back a default window — 30 days from the command line's `--days`, or whatever the
   calling screen asked for.
4. The app fetches from the exchange in chunks and writes **each chunk to disk as it arrives**,
   rather than holding the whole range in memory first (`BUG-025`).
5. After each chunk the app publishes progress — the symbol, the timeframe, how many candles so
   far, and how many it expects — carrying a correlation id so a screen can tell its own sync
   apart from another screen's sync of the same pair (`BOT-122`).
6. The actor may cancel. The app polls the actor's cancellation between fetches and stops there.
7. When the range is covered, the app finishes. The command line prints `✅ Sync complete.`; a
   screen returns to idle and re-reads what is now stored.
8. **On the Backtest screen only**, the same worker then caches that symbol's exchange order
   filters — minimum notional, lot step, price tick — so the screen's market-rule check has
   something to check against (`BUG-127`). It reads the **same** `exchangeInfo` payload the symbol
   list already fetches, so it costs no extra request, and it runs here rather than where the check
   runs because the check is on the Qt main thread and must not make a network call. A failure at
   this step does **not** fail the sync: the candles are already on disk, and the screen keeps
   saying *"not verified yet"* — see §6.

## 4. What must be true afterwards

- Re-opening the chart, or re-running the same `sync`, shows the new candles **without another
  fetch** — the second run finds the store current and has almost nothing to do.
- A cancelled sync leaves every chunk it had already written in place. Cancelling is not an
  undo; it is a stop.
- Two syncs of the same symbol and timeframe never fetch it twice concurrently. The second one
  is skipped with a log line, not queued, and not run in parallel (`BOT-121`).
- Coverage is answered by what is **stored**, not by how many rows came back: a range is covered
  when the store says so (`BUG-010` is the report where row-counting said otherwise).

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| The timeframe is not a `TimeFrame` value | `Invalid interval: …` with the full list, exit code 1 | Checked before anything is dispatched; the command line's `choices` catches most of it earlier |
| The symbol does not exist on the venue | The exchange's own refusal, reported as `❌ Sync failed: …` | The app does not keep its own list of valid pairs to guess from |
| No network, or the exchange is unreachable | `❌ Sync failed: …` on the command line; the screen leaves its progress banner and returns to idle | The sync raises rather than answering "done with nothing", so no caller can mistake a failed fetch for an empty market |
| The same pair is already syncing elsewhere | Nothing happens, and a log line says why | Skipping is the designed answer (`BOT-121`); blocking the second caller would freeze a screen behind another screen's work |
| The actor cancels mid-fetch | Progress stops; what was written stays | Cancellation is cooperative, polled between fetches |

## 6. What this use case does NOT promise

- **It does not promise a range.** `IMarketDataSync.sync()` returns `None` on purpose: what the
  caller does next is read the store or watch the progress events. There is no result object
  saying "you now have candles from X to Y" — asking the store is the only truthful answer.
- It does not fill an *interior* gap discovered later. Repairing a hole in the middle of stored
  history is a different use case (SPEC-008, planned).
- It does not promise the newest candle is closed. The most recent candle a fetch returns may
  still be forming.
- It does not promise an ETA. Step 5's `total` is an **estimate** computed from the range and
  the timeframe, and the app says so rather than presenting it as a countdown.
- **It does not promise step 8's filters arrived.** A sync reported as complete means the candles
  are on disk; the exchange-rule check is a separate, best-effort read, and a Backtest screen that
  still says *"not verified against exchange rules"* after a successful sync is telling the truth
  rather than hiding a failure. Before `BUG-127` that message was permanent for every symbol,
  because nothing ever cached a filter — the honest transient is the fix, and this line is the
  promise that it stays a transient rather than becoming a guarantee.

## 7. Ports and modules it exercises

`market_data`: `IMarketDataSync` (the published sentence — every one of the four callers goes
through it), `IMarketDataRepository` (what is stored), `IExchangeClient` (the fetch),
`IRangeCoverage` (what a later reader asks about coverage), and — for step 8, on the Backtest
screen's path only — `ISymbolMetadataProvider` (fetches the filters) writing through
`ISymbolMarketMetadataCache` (what the main-thread check reads). `InFlightSyncGuard` is internal to
the module and deliberately not published.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| Start point, chunked persistence, cancellation between fetches | `tests/unit/modules/market_data/application/sync/test_sync_market_data_handler.py` | unit |
| Many symbols in one request, per-target dispatch | `tests/unit/modules/market_data/application/sync/test_bulk_sync_market_data.py` | unit |
| The second concurrent sync of a pair is skipped | `tests/unit/modules/market_data/application/sync/test_in_flight_sync_guard.py` | unit |
| Both implementations of the port answer the same way | `tests/unit/modules/market_data/contracts/test_market_data_sync_contract.py` | contract |
| Progress events reach the screen, with cancellation | `tests/unit/modules/market_data/ui/test_sync_coordinator.py` | unit |
| The Backtest screen's own sync path | `tests/unit/modules/backtesting/ui/coordinators/test_data_sync_coordinator.py` | unit |
| `sync` on the command line, and at the prompt | `tests/unit/modules/market_data/cli/test_sync_cmd.py` · `tests/unit/modules/market_data/cli/test_sync_cli_handler.py` | unit |
| Coverage answered by the store, not by row count | `tests/integration/modules/market_data/adapters/persistence/test_bug010_sync_range_coverage_regression.py` | integration |
| A real fetch against the real venue | **the user runs it**: `sync --symbols BTCUSDT --interval 1m --days 2`, then re-run it and see the second run finish at once | human |
