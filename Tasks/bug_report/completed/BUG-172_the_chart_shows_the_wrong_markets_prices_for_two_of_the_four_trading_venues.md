# BUG-172 — Futures Testnet's chart shows mainnet prices while its orders fill on the testnet ("Price shown ≠ fill price")

- **Reported:** 2026-10-07 (the owner, a screenshot of Trade mode on `master-warrior` at `6aa3586`; the coordinator agreed it is a bug and asked for it to be fixed)
- **Severity:** 🔴 P1 — the price a person looks at is not the price their order fills at, for two of the four venues at all times; with `exchange.market_data_venue = futures_testnet` the mismatch turns over and the two mainnet venues show testnet prices behind real money
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** Every desk, bot chart and venue backtest read one process-wide `exchange.market_data_venue` (one exchange client, one candle store, one live stream), so two of the four venues were always charted from the wrong market. Fixed: each venue reads its own market (`TradingVenue.market_data_venue` → `IMarketDataSources.ports_for`), the candle store, the stream and every tick are kept apart by venue, the setting is read only by the screens that act on no venue, and the mismatch banners are gone with the states they described.
- **Context:** Trade mode and Bots (`Docs/SPEC/SPEC-002_watch_the_live_market.md`, `SPEC-014_run_a_grid_bot.md`) → `src/modules/market_data/` (`composition/`, `application/`, `contracts/`, `adapters/`) → `src/modules/trading/ui/desk/`, `src/modules/bots/`, `src/modules/strategy/`, `src/support/ui_kit/environment_banner/`
- **Environment:** `master-warrior` at `6aa3586`; default configuration (`exchange.market_data_venue = mainnet_public`); every venue always on since `EPIC-034B`, mainnet venues since PR #420. Tested here against the fake Binance server only: this sandbox cannot reach `*.binance.com` (HTTP 451), so no real price was compared.

## Reproduction
1. Start the app with the default configuration and open Trade mode on Futures Testnet (or Spot Testnet).
2. Look at the banner and the desk's chart: the banner warns "Chart is showing MAINNET prices, orders fill on TESTNET".

Expected: the chart a person looks at shows the market of the venue they trade on. Actual: the chart, its live stream and the venue's backtests read the one setting. Every time; no precondition. Reproduced in code by `tests/integration/modules/market_data/test_each_venue_charts_from_its_own_market.py` (red on `6aa3586`, below).

## Symptom
The owner's screenshot (banner text above). Nothing in a log: the app did what it was wired to do. In the regression test on `6aa3586`, with only the testnet's host answering, Spot Testnet's chart sync fails on the mainnet host:
```
requests.exceptions.ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=57263): Max retries exceeded with url: /api/v3/ping (Caused by NewConnectionError(... Connection refused))
sagittarius_engine.exceptions.DependencyResolutionError: Failed to resolve 'exchange_client' for SyncMarketDataCommandHandler: ...
```
and a candle synced for a mainnet venue is served to the testnet one (`assert (MarketData(...),) == ()`).

## Root cause
`market_data` held one of each thing, picked once at boot from `exchange.market_data_venue`: `composition/adapter_bindings.py` bound a single `MarketDataVenue` (`_build_market_data_venue`, from `resolve_market_data_venue(config)`), a single `IExchangeClient`, a single `DatabaseManager`/`IMarketDataRepository` (shards named `<market>_<symbol>`, no source in the key) and a single `BinanceWebsocketService` built with that venue's `testnet` flag; `composition/port_bindings.py` published `IMarketDataSync`/`IHistoricalKlines`/`IMarketStream`/`IRangeCoverage` over them. Every consumer resolved those singletons: `trading/ui/desk/desk_screen/desk_dependencies.py:127-129`, `trading/ui/market/market_dependencies.py:117-120`, `bots/ui/bots_screen/spot_candle_feed.py:36-43`, `bots/application/queries/run_grid_backtest/handler.py`. The venue therefore chose where an order went and the setting chose where the chart came from, and with all four venues always on no setting was right for more than two. `MarketTickEvent` named only its market, so even a correct stream would have been drawn, and traded on, by the other venue's screens.

The gate was green because the mismatch was accepted knowingly, not missed: `support/binance_gateway/contracts/venue_alignment.py` said "no setting is right for every venue (the full fix is a market-data source per trading venue)" and PR #420 turned it into banners. No case study: no net failed to see it.

## Fix
One market-data source per venue, chosen where a screen is built, with the store, the stream and the tick kept apart by it:
- `support/binance_gateway/contracts/`: `MarketDataVenue.SPOT_TESTNET` (Spot's testnet, `testnet.binance.vision`, is another exchange than Futures'); `TradingVenue.market_data_venue` maps each of the four venues to the environment its orders fill in.
- `market_data/contracts/`: `IMarketDataSources.ports_for(venue)` returns that venue's `IMarketDataSync`, `IHistoricalKlines`, `IMarketStream`, `IRangeCoverage` and store (`MarketDataPorts`); `IMarketDataVenues` is the module's own routing of a venue to its client, store and stream. `MarketTickEvent.market_data_venue` is required (keyword-only), as its market is: a producer that forgot it is a `TypeError`, not a candle labelled with the wrong venue.
- `market_data/application/`: the sync and stream services are bound to a venue and put it on their commands; the handlers reach the venue's client, store and stream through `IMarketDataVenues`, so there is still one dispatcher path per use case. `InFlightSyncGuard` keys by venue and market too, so two desks opening on the same `BTCUSDT 1h` do not skip each other's sync.
- `market_data/composition/market_data_venues.py` + `adapters/persistence/venue_directory.py`: the default venue keeps the container's own bindings (so the CLI, bulk sync, Data mode and shutdown are as before); every other venue gets a store of its own (a subdirectory named by the venue, the mainnet keeping the configured directory its shards were always in), a stream and a lazily built client, all closed with the module.
- Consumers: the desks ask `IMarketDataSources` for their venue (`desk_dependencies.py`), a bot's chart and Grid backtest for the bot's venue (`bots_screen/venue_candles.py`, `KindBacktests` builds a page per kind **and venue**, `RunGridBacktestQuery.venue`), and every listener of `MarketTickEvent` keeps only its venue's candles: `MarketTickFeed` (desk, Market mode), `BotTickFeed`, `BotEventRouter.on_tick`, and `VenueStrategySessions.built_for`, so a testnet candle can never drive a mainnet strategy or bot.
- `exchange.market_data_venue` stays, for the screens that act on no venue (Data mode, the Market mode, a plain historical backtest, the CLI); its Settings row and `ConfigKeys` comment say so. `test_a_venue_screen_charts_its_own_venues_market.py` lists its only readers.
- Legacy candles are labelled with the configured venue, or quarantined (see Verification).
- Banners: `VenueAlignment`, `compute_venue_alignment` and the three mismatch messages are deleted — no venue screen can show another market any more. The banner keeps what is still true: each enabled venue and whether its funds are simulated or real (`venue_banner_content`).
- Testnet limits: Binance's `-1120` (Futures has no `1s` klines) and `-1121` (the testnet does not list a symbol) become `ExchangeRefusedKlinesError` (`adapters/binance/kline_refusal.py`), `CandlesUnavailableError` at the chart's feed, and a message bar with the reason in words and "the chart shows the stored candles", with no retry. A short history is an ordinary sync that stores what exists.

## Regression test
- `tests/integration/modules/market_data/test_each_venue_charts_from_its_own_market.py` — the real app over the fake Binance server, one environment answering and the other a closed port, each of the four venues under both values of `exchange.market_data_venue`. Red on `6aa3586` for the right reason: the four mismatched combinations (`spot_testnet`/`futures_testnet` under `mainnet_public`, `spot_mainnet`/`futures_mainnet` under `futures_testnet`) fail with a connection refused on the wrong host; `test_testnet_candles_are_never_served_as_mainnet_ones` fails because the store serves one venue's candle to the other. Green after.
- Venue-parametrised proofs per layer: `test_a_venue_screen_charts_its_own_venues_market.py` (every venue's chart source is its own order environment; the setting's readers; no venue screen resolves the default ports), `test_venue_stores_are_apart.py` (real SQLite per venue), `test_market_tick_feed.py`, `test_bot_tick_feed.py`, `test_desk_live_feeds.py`, `test_market_tick_event_handler.py`, `test_bot_event_router.py`, `test_run_grid_backtest.py`, `test_kind_backtests_per_venue.py`, `test_sync_market_data_venues.py`, `test_market_data_venues.py`, `test_market_data_sources_contract.py`.
- Testnet limits: `test_client_refused_klines.py`, `test_live_candle_chart_failures.py`, and the Futures `1s` / Spot short-history cases at the end of the regression file.

## Verification
- Commit tier `pwsh scripts/ci-local.ps1 -SkipTests`: PASS (log read, no `FAILED|ERROR|Traceback|ResourceWarning`). `tests/unit/architecture`: green. `tests/unit`, `tests/integration`, `tests/sanity`: green apart from the known local-only `test_workbench_conformance[True-1024x700]`.
- Positive proof the new mechanism ran, from the regression run for Spot Testnet under the default setting:
  ```
  App.Database - INFO - Database Manager initialized at directory: .../database/spot_testnet
  App.MarketDataVenues - INFO - Market data venue spot_testnet opened.
  App.SyncMarketData - INFO - Starting sync for symbols: ['BTCUSDT'] at interval 1m from spot_testnet
  App.Database - INFO - Created dedicated database for spot/BTCUSDT
  App.SyncMarketData - INFO - [BTCUSDT] Successfully synced 1 klines.
  ```
- Not proven here: a real chart on the real testnets and mainnet (HTTP 451 from this sandbox). The owner's manual check is to open Trade mode on each of the four venues and compare the chart's last price with the venue's order book.
- Legacy candles (coordinator's review): rows stored before this fix carried no source. `label_legacy_store` (`adapters/persistence/legacy_store_label.py`, called once from `_build_database_config`, before any store opens) gives them the venue `exchange.market_data_venue` names at that moment: `futures_testnet` moves them into the Futures Testnet store, `mainnet_public` leaves them as the mainnet's. An absent setting is the default the old resolver read (`mainnet_public`); one that is present but names no venue quarantines them in `legacy_unlabelled/` — served to no venue, nothing deleted — and the history syncs again. A marker file makes it run once. Tests: `test_legacy_candles_keep_their_source.py` (each case, absent setting, non-shard files left alone, once-only, a clash quarantines instead of aborting boot) and the booted-app wiring test in the regression file (red with the call removed). Limit worth knowing: the setting at migration time is the only evidence of origin; a user who changed it between syncing and updating would still get the rows labelled by the later value.
