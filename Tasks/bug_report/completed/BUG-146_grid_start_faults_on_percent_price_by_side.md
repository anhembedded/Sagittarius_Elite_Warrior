# BUG-146 — A Grid whose range reaches outside Binance's price band faults at Start with an unreadable error

- **Reported:** 2026-10-04 (the user, in chat, with the bot's log)
- **Severity:** 🟡 P2. The bot goes from STARTING to ERROR on its first rejected order. The message names a Binance filter the user cannot act on.
- **Status:** ✅ Fixed (2026-10-04)
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (start a Grid bot) → `src/modules/bots/domain/grid/grid_checks.py`; `src/modules/trading/adapters/binance/spot/spot_metadata_parser.py`
- **Environment:** Windows, Spot Testnet, BTCUSDT at about 85 300.

## Reproduction

1. Create a Grid on BTCUSDT on `spot_testnet` whose lower limit is far below the market. The user's ladder reached a BUY level at 2 222.
2. Press Start.

Expected: the plan is refused before Start, with the price that is too far and the range Binance accepts.

Actual: the following log lines.

```
Bot ym3jxj: L10 BUY 0.16365000 @ 2222.000000 -> price_filter: APIError(code=-1013): Filter failure: PERCENT_PRICE_BY_SIDE
Bot ym3jxj: STARTING -> ERROR on fault (order_failed: L10 BUY: ...)
```

## Root cause

- Binance Spot's `PERCENT_PRICE_BY_SIDE` filter sets the accepted price range by order side, as multiples of the symbol's average price.
  - A BUY is accepted only between `bidMultiplierDown` and `bidMultiplierUp` times that average.
  - A SELL is accepted only between `askMultiplierDown` and `askMultiplierUp` times it.
  - On mainnet BTCUSDT the multipliers are 0.2 and 5, so a BUY at 2 222 against about 85 000 is far below the floor.
- `parse_spot_symbol_metadata` read only `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE` and `NOTIONAL`, so neither `SymbolOrderMetadata` nor the bot's `ExchangeTerms` knew the band.
- The Grid checks therefore could not refuse the plan. `GridStartPreconditions` passed it, and the first order outside the band faulted the run.
- Domain-truth rule: exchange rules come from the symbol's metadata. This one was never read.

## Fix

- `SymbolOrderMetadata.price_band` (`PercentPriceBand`) holds the filter. It is optional: `None` when the symbol publishes none.
- `spot_metadata_parser._price_band` reads the filter. A filter that is present must carry all four multipliers.
- `ExchangeTerms.price_band` (`PriceBand`, the bots module's own value) is filled by `exchange_terms_for`, the one place a bot's terms are built.
- `check_price_band` is a fifth refusal, `LEVEL_OUTSIDE_PRICE_BAND`. At the current price it checks every BUY level against the buy band and every SELL level against the sell band.
  - The verdict names the level and the range, and asks to narrow the range, for example: "A BUY level at 2222 is outside the 17058.4–426460 the exchange accepts".
  - `GridStartPreconditions` already refuses any plan with a REFUSED verdict, so Start is refused before the `start` transition, with nothing to clean up. The Grid panel shows the same verdict while the user edits.
  - A venue with no band gets the OK verdict `PRICE_BAND_NOT_PUBLISHED`, which says the check did not run.
- **Limit:**
  - The band follows the market. The check uses the last price where Binance uses the average over `avgPriceMins`.
  - A level that is inside the band at Start can leave it if the price moves far. A reaction order would then be rejected as before.
- **Not changed:**
  - The Futures parser does not read `PERCENT_PRICE`. The Grid runs on Spot only.

## Regression test

- `tests/unit/modules/bots/domain/grid/test_grid_price_band_check.py` was red before the fix: no band verdict existed.
  - A BUY below the band refuses and names both prices.
  - A BUY exactly at the floor passes. Changing `<=` to `<` turns this red.
  - A SELL above the band refuses. Skipping the SELL loop turns this red.
  - No band means the check did not run.
- `tests/unit/modules/trading/adapters/binance/spot/test_spot_metadata_parser.py`: the band is parsed when published and is `None` otherwise.
- `tests/unit/modules/bots/application/services/test_bot_exchange_terms.py`: the band reaches the bot's terms.

## Verification

- Bots unit tests, the Spot adapter tests, the trading application tests and the bots integration tests passed (845 + 769).
- **Not yet run:** a live Start on Spot Testnet with a range below the band. The user's next run is the live check.
