# EPIC-027A — Every stored candle knows which market it came from, and a sync asks for one

**Status:** 🔵 Backlog
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
- [ ] `MarketType` lives in the shared kernel (`src/core/vo/`). The unused copy in
      `src/domain/value_objects/` is removed or re-exported, and the architecture guards stay green.
- [ ] A candle is stored under a (market, symbol) identity. Spot and Futures candles of the same symbol
      and interval can coexist, and neither overwrites the other.
- [ ] The sync command and the repository read ports take a `MarketType`. No read path defaults to a
      market silently.
- [ ] On the mainnet public venue, Spot candles come from `/api/v3/klines` and USDⓈ-M candles from
      `/fapi/v1/klines`. A test against the fake exchange shows which path each request hit.
- [ ] Existing shards are migrated once, following the user's answer to ADR O3. The migration is logged
      and idempotent, and a test covers a legacy shard.
- [ ] Data Management shows and filters by market. Export/import (`BOT-112D`) carries the market.

## 3. Design
- **Per-market shards** (e.g. `<data>/spot/BTCUSDT.db`, `<data>/futures_usd_m/BTCUSDT.db`) rather than
  a key column. Gap scan, vacuum and export/import already work per shard, so they need no change
  (ADR §3).
- The venue keeps choosing the **environment** (mainnet public or testnet). The **market** comes from
  the request. `_KLINES_TYPE` becomes a function of the market, not of the venue.
- The migration renames legacy shards into the market folder chosen by O3. It never deletes data.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/vo/market_type.py` | `MarketType`, moved from `src/domain/value_objects/` |
| `src/modules/market_data/adapters/persistence/database_manager.py` | shard path includes the market |
| `src/modules/market_data/contracts/` (repository/sync ports) | `market_type` parameter on read, count and sync |
| `src/support/binance_gateway/contracts/binance_endpoints.py` | klines type resolved from `MarketType` |
| `src/modules/market_data/ui/` (Data Management) | market column and filter |
| `tests/sanity/fake_exchange/` | `/fapi/v1/klines` served on the mainnet public host |

## 5. Testing
- Unit: shard path per market; the endpoint resolver per (venue, market).
- Integration: sync one Spot and one Futures range of the same symbol against the fake exchange, then
  read both back unchanged.
- Migration: a fixture legacy shard, migrated twice, gives the same result.
- Not run yet.
