# EPIC-027A — Every stored candle knows which market it came from, and a sync asks for one

**Status:** ✅ Done (2026-09-26)
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot và back test theo spot"* ("I want to trade spot and backtest on spot").
**Risk:** 🔴 — touches every stored shard; a wrong migration silently mixes Spot and Futures prices.
**Complexity:** L — storage layout, sync port, download endpoint, migration and the Data Management screen.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** None. ADR open question O3 must be answered before the migration step.

---

## 1. Context and problem
- The kline primary key is `(symbol, interval, open_time)`. It records no market
  (`src/modules/market_data/adapters/persistence/models.py:11-13`). There is one SQLite shard per
  symbol (`database_manager.py:46-56`).
- The download endpoint is chosen by the market-data venue, not by the user's intent:
  `MAINNET_PUBLIC → HistoricalKlinesType.SPOT` and `FUTURES_TESTNET → FUTURES`
  (`src/support/binance_gateway/contracts/binance_endpoints.py:51-54`). Mainnet Futures klines
  (`/fapi`) are never downloaded.
- As a result, every "Futures" backtest on the default venue runs on Spot prices, and the screen
  never says so. If the venue is switched, both markets write into the same shard.
- A Spot backtest cannot be distinguished from a Futures one without this task, and a Futures
  backtest cannot be made truthful.

## 2. Acceptance criteria
- [x] `MarketType` lives in the shared kernel (`src/core/vo/`). The unused copy in
      `src/domain/value_objects/` is removed or re-exported, and the architecture guards stay green.
- [x] A candle is stored under a (market, symbol) identity. Spot and Futures candles of the same symbol
      and interval can coexist, and neither overwrites the other.
- [x] The sync command and the repository read ports take a `MarketType`. No read path defaults to a
      market silently.
- [x] On the mainnet public venue, Spot candles come from `/api/v3/klines` and USDⓈ-M candles from
      `/fapi/v1/klines`. A test against the fake exchange shows which path each request hit.
- [x] Existing shards are migrated once, following the user's answer to ADR O3. The migration is logged
      and idempotent, and a test covers a legacy shard.
- [x] Data Management shows and filters by market. Export/import (`BOT-112D`) carries the market.

## 3. Design
- **Per-market shards** via compound shard names inside one shared `SqliteShardManager`
  (`spot_BTCUSDT`, `futures_usd_m_BTCUSDT`) rather than per-market subdirectories — a subdirectory
  design was rejected during implementation because it silently breaks `SqliteShardManager`'s
  `IN_MEMORY = ":memory:"` sentinel, which matches by exact string equality
  (`os.path.join(":memory:", "spot")` is not `":memory:"`). Gap scan, vacuum and export/import already
  work per shard, so they need no change (ADR §3).
- The venue keeps choosing the **environment** (mainnet public or testnet). The **market** comes from
  the request. `_KLINES_TYPE` is now a function of `MarketType`, not of `MarketDataVenue`; a single
  `PythonBinanceClient` resolves `klines_type` per call, so one client instance built against the
  mainnet-public venue serves every market (`python-binance`'s `Client` always knows both `API_URL`
  and `FUTURES_URL`, independent of the `testnet` flag).
- The migration renames legacy (bare-symbol) shard files into the market-qualified name chosen by O3
  ("tag as Spot"). It never deletes data, and is idempotent (a second run finds no legacy shards left).
- **Phase 1 deferral, applied uniformly:** every screen and port with no market selector yet (all of
  Data Management, the Backtest screen, the sync CLI) pins its calls to `MarketType.SPOT` explicitly —
  documented once in `MarketType`'s own docstring rather than repeated per file — since Phase 1 has no
  second market with real data. `EPIC-027D`'s Backtest market selector is the first real second case.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/vo/market_type.py` | `MarketType`, moved from `src/domain/value_objects/` (now-empty `domain/` zone retired from the architecture guard) |
| `src/modules/market_data/adapters/persistence/database_manager.py` | `shard_name()`/`parse_shard_name()`; every method takes `market: MarketType`; `list_legacy_shard_names()`/`migrate_legacy_shards()` |
| `src/modules/market_data/contracts/i_market_data_repository.py` + `sqlalchemy_repository.py` + fakes/contracts | every method takes `market: MarketType` |
| `src/modules/market_data/contracts/i_market_data_sync.py`, `application/sync/**` | `MarketDataSyncRequest`/`SyncMarketDataCommand` carry a required `market` |
| `src/support/binance_gateway/contracts/binance_endpoints.py` | `_KLINES_TYPE`/`klines_type_for()` re-keyed from `MarketDataVenue` to `MarketType` |
| `src/modules/market_data/contracts/i_exchange_client.py`, `adapters/binance/client.py`, `market_data_session_factory.py` | `get_historical_klines`/`stream_historical_klines` take `market: MarketType`; `PythonBinanceClient` no longer fixes `klines_type` at construction |
| `src/modules/market_data/ui/database_status_table_model.py` | `DatabaseStatusRow.market` + `MARKET_COLUMN` |
| `src/modules/market_data/application/database/export_market_data/`, `import_market_data/` | `market: MarketType` on both commands; CSV/JSON/Parquet all carry a `market` field/column |
| `tests/sanity/fake_exchange/spot_routes.py`, `futures_routes.py` | `/api/v3/klines` and `/fapi/v1/klines` each answer one fixed, distinguishable row |
| `tests/integration/infrastructure/binance/test_market_data_client_routes_klines_by_market.py` | new — proves a single client routes Spot vs Futures calls to their own endpoint |
| ~40 further call sites across `src/`, `scripts/`, `tests/` | threaded `market` through per `architecture-rule.md` §2 ("every implementer of a port stays complete") |

## 5. Testing
- **Unit** (`tests/unit`): 5515 passed, 0 failed. Covers `DatabaseManager` market isolation and legacy
  migration (`test_database_manager_shards.py`), repository/sync port market-scoping
  (`test_market_data_repository_contract.py`, `test_market_data_sync_contract.py`), `klines_type_for`
  per `MarketType` (`test_binance_endpoints.py`), `PythonBinanceClient` per-call market resolution
  (`test_python_binance_client_unit.py`), the Data Management market column
  (`test_database_status_table_model.py`), and export/import carrying `market` through CSV/JSON/Parquet
  (`test_export_market_data.py`, `test_import_market_data.py`).
- **Integration** (`tests/integration`): 165 passed, 4 skipped (pre-existing, unrelated). Includes the
  new `test_market_data_client_routes_klines_by_market.py`, which drives one real
  `MarketDataSessionFactory`-built client against the fake exchange server (both `/api/v3/klines` and
  `/fapi/v1/klines` served by the same server instance, mirroring real mainnet's two host families) and
  asserts each `MarketType` call reaches its own endpoint by the distinguishing fixed row it returns.
- **Architecture** (`tests/unit/architecture`): 445 passed — module-boundary guard updated for the
  retired `domain` zone; shrink-only god-file ratchet still holds on every touched `src/` file.
- **mypy**: `Success: no issues found in 702 source files` (`src` + `scripts`, correct parent-directory
  invocation per `install-rule.md`).
- **ruff check` / `ruff format --check`**: clean on every touched file.

## Implementation notes (written when done)
- Real bug caught during implementation: compounding `market.value + "_" + symbol` for shard names let
  an empty `symbol=""` produce a still-valid-looking shard name (`"spot_"`), silently bypassing the
  intended security check that rejects empty/invalid symbols. Fixed by validating the symbol against
  `_VALID_SYMBOL_PATTERN` before compounding.
- Real design correction before any code was written: an initial "one `SqliteShardManager` per market
  subdirectory" design was rejected once it was checked against the engine's `IN_MEMORY` sentinel
  (exact-string match) — replaced with compound shard names in one shared manager.
- `EPIC-027A`'s own acceptance criterion asked for a fake-exchange test proving which endpoint a
  request hits; the fake exchange already served both `/api/v3/klines` and `/fapi/v1/klines` from one
  process (`tests/sanity/fake_exchange/{spot,futures}_routes.py`, pre-existing from `EPIC-021J`) — only
  their canned kline rows needed to become distinguishable (fixed `open_price`, one row each, still
  well under any pagination page size) to prove routing by content rather than needing new server
  instrumentation.
- Every `market` parameter added to an already-large file honored the shrink-only god-file ratchet
  (`tests/unit/architecture/test_god_files_only_shrink.py`) by condensing pre-existing comment
  verbosity in the same file rather than requesting a baseline bump, which that guard's own docstring
  forbids.
- Delivery: implemented on branch `claude/wizardly-cerf-fc5b5x`, uncommitted at the time this file was
  written (commit pending in the same batch as this file). Full gate: unit, integration, architecture
  and mypy all green as recorded above; GitHub Actions' `ci-local.ps1 -Full` check run is the pre-merge
  full-gate authority per `ci-rule.md` §1 and has not run yet at this point. Per `ONBOARDING.md` §7,
  merge to `master-warrior` requires an independent reviewer session; not yet requested at this point.
