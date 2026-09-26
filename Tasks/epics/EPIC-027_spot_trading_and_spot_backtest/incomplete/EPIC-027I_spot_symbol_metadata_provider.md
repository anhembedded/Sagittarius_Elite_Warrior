# EPIC-027I — Live Spot orders are rounded with Spot's own exchange filters

**Status:** 🔵 Backlog
**Source:** found while measuring the Spot gap, 2026-09-26. It is part of the user's *"giao dịch spot"* request.
**Risk:** 🟢 — a pure parser and provider; the rounding policy itself is already exchange-agnostic.
**Complexity:** S — one provider, one parser branch, a market-neutral port name.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027G](EPIC-027G_spot_testnet_venue_and_credentials.md)

---

## 1. Context and problem
- `IMarketMetadataProvider` is typed to `FuturesSymbolMetadata`
  (`contracts/futures_symbol_metadata.py:344-363`).
- `FuturesMetadataProvider` always reads `futures_exchange_info()` on a testnet client and ignores the
  venue (`adapters/binance/futures_metadata_provider.py:57-58`).
- The Futures parser reads `MIN_NOTIONAL` (`notional` or `minNotional`), but **not** the `NOTIONAL`
  filter Spot uses today. On a Spot payload it would silently default the minimum notional to 5
  (`futures_metadata_parser.py:31-36,62,116-131`). It also ignores `MARKET_LOT_SIZE`.
- `OrderQuantityRoundingPolicy` is Decimal and exchange-agnostic, so it can be reused
  (`domain/policies/order_quantity_rounding_policy.py:87-130`).

## 2. Acceptance criteria
- [ ] A market-neutral metadata type and port. The Futures provider and a new Spot provider both
      implement it. The provider is chosen by the venue's `market_type`.
- [ ] The Spot provider reads `GET /api/v3/exchangeInfo` and parses `PRICE_FILTER`, `LOT_SIZE`,
      `MARKET_LOT_SIZE` and `NOTIONAL` (`minNotional`, `applyToMarket`). A missing filter is an error,
      not a silent default.
- [ ] A Spot MARKET order is rounded with `MARKET_LOT_SIZE` when present, and a LIMIT order with
      `LOT_SIZE`.

## 3. Design
- Reuse, not reinvent: the backtest side already parses Spot filters into float
  `SymbolMarketMetadata` (`market_data/adapters/binance/market_metadata_parser.py`). The live side
  needs Decimal, so the parsing rules are shared and the numeric type is not. Decide in the PR whether
  one Decimal parser serves both; record the choice.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/` | market-neutral symbol metadata + port |
| `src/modules/trading/adapters/binance/spot/spot_metadata_provider.py` | new |
| `src/modules/trading/adapters/binance/futures_metadata_parser.py` | shared filter parsing, no silent default |

## 5. Testing
- Unit: real Spot `exchangeInfo` fixtures (BTCUSDT, a low-price pair); a missing filter; MARKET vs LIMIT lot size.
- Not run yet.
