# BUG-178 — Panning or zooming a chart past its oldest candle loads no older candles (regression)

- **Reported:** 2026-10-07 (the owner, via the coordinator: "this worked before"; Trade mode, ETHUSDT live chart, master `6aa3586`)
- **Severity:** 🟡 P2 — a chart cannot be scrolled back beyond its first 500 candles; Market's View → Load older is the only way, and only for stored candles
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** `ChartCard.sig_near_left_edge` lost its only listener when the Dev Board (and its `HistoryPaginationController`) was deleted (`c7914f0`); the shared `LiveCandleChart` never listened, and the old path read the store only. Fixed in the shared chart: `OlderCandlesBackfill` loads the window before the oldest candle (store, else the chart's own market) when a pan or zoom reaches the left edge, on every chart.
- **Context:** Trade desk, Market and Bots charts (`Docs/SPEC/SPEC-002_watch_the_live_market.md`) → `src/support/charting/live_chart/` → application of the chart; port `ICandleFeed` implemented in `src/modules/market_data/contracts/`
- **Environment:** Owner: Windows, 2560x1440. Reproduced and fixed on Linux, Qt `offscreen`.

## Reproduction
1. Any live chart (desk, Market tab, a bot's), with candles drawn.
2. Pan or zoom left past the oldest candle.

Expected older candles appear (from the store, else from the exchange); actual an empty plot to the left, forever.

## Symptom
No log line, no error: nothing listens. `EdgeScrollDetector` emitted `sig_near_left_edge` on every manual range change near the left edge and `ChartCard` relayed it (`chart_card.py:68`, `:264`), to no one.

## Root cause
The mechanism was the Dev Board's: `DashboardPresenter` connected `ChartCard.sig_near_left_edge`, `HistoryPaginationController` held one load per symbol with a cooldown, and `_run_load_more_history` read older candles from the store (BOT-035; its docstring: "Phase 1 has no auto-sync-from-Binance"). **Breaking commit: `c7914f0` "refactor(epic-033): delete the Dev Board"** (EPIC-033P stage 3) removed the presenter, the controller and 252 tests; its message lists what the Market mode and the desks took over, and the left-edge load is not in it. `EPIC-033S` re-created only a manual View → Load older on the Market chart (`MarketChart.load_older`, stored candles only). The shared `LiveCandleChart` (EPIC-029 ADR D15, which the desk and a bot's chart also use) never had the listener, so the desk and Bots charts have had no backfill since the board's charts were the only ones that did. `git log -S"sig_near_left_edge"` shows the signal's last consumer going away in `c7914f0`.

The gate was green because the signal's tests (`test_edge_scroll_detector.py`, `test_chart_card.py`) prove the emit, and no test proved that anything is done with it: a signal with no listener is not a failing test. No case study: the net that was silent (a test per emitter) is the shape of every orphaned signal, and a guard for "every signal of a shared chart has a connected listener" would be a repo-wide census, which this fix does not take on.

## Fix
Restored at the mechanism, in the shared chart, for every chart:
- `ICandleFeed.load_older(OlderCandlesRequest, cancelled)` (new abstract method; every implementer in `src/` and `tests/` updated). `MarketDataCandleFeed` reads the store's window before the oldest drawn candle; when the store holds fewer than a window it syncs the span from **the feed's own market** through its own `IMarketDataSync` (so the venue's source, never the global setting: since #421 each chart's feed is built from its venue's own ports; a refusal for good, such as a timeframe or symbol the testnet does not serve, is `CandlesUnavailableError` and is said as its own sentence), then reads the store again.
- `LiveChartCoordinator.load_older` runs it on the worker pool and reports through two new callbacks.
- `OlderCandlesBackfill` (new, `live_chart/older_candles_backfill.py`): listens to `sig_near_left_edge`, one load at a time, 1.5 s cooldown (a drag fires many events), 30 s after an empty answer, draws only candles that open before the oldest drawn one, fences by the chart's first-window token, drops a load when a whole history is drawn meanwhile, and tells a failure on the message bar with a Retry (`INotifier`, never a box).
- `LiveCandleChart` owns it (`older_candles`), so `DeskChart`, `MarketChart` and `BotChart` have it; `MarketChart.load_older` and View → Load older now use it (store, else exchange) and its own `ChartHistory.older_than` is gone. `live_candle_chart.py` stays at 400 lines by moving `opening_interval` and `draw_live_candle` out.

## Regression test
- `tests/unit/support/charting/live_chart/test_live_candle_chart_older.py`: panning past the oldest candle draws the older candles (red before: the feed's older read is never made), volume too, a live tick during the load is kept, no candle twice, one load at a time, backoff on an empty answer, a failure is told, a load in flight when the symbol changes or a range is drawn is dropped. Mutations checked: no freshness filter, no token fence and a kept ask after a range each fail a test.
- `tests/unit/modules/market_data/contracts/test_market_data_candle_feed_older.py`: store first, exchange when short, the span asked, the feed's own market, no gap and no duplicate at the window's edge, a failing sync raised.
- `tests/integration/modules/market_data/test_each_venue_charts_from_its_own_market.py::test_older_candles_are_fetched_from_the_charts_own_venue`: all four venues under both global settings, the fake server answering only the venue's own environment; red (8 failures) when the feed's sync is another venue's.
- `tests/integration/modules/market_data/test_chart_backfills_older_candles.py`: real worker pool, real feed, real `ChartCard`: from the store; from the exchange with an empty store; live ticks arriving during the backfill; an unreachable exchange. Red with the edge listener unhooked (timeout).

## Verification
Local, `QT_QPA_PLATFORM=offscreen`: `tests/unit` and `tests/integration` (9,767 passed) except `test_workbench_conformance[True-1024x700]`, which fails the same way without this change (known, local only). Commit tier and `tests/unit/architecture`: see the PR. Not verified: a real chart on a real exchange (this sandbox has no egress to Binance); the owner's check is to open a desk chart, drag left past the oldest candle and watch older candles arrive.
