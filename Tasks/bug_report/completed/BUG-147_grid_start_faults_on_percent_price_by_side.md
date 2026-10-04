# BUG-147 — A Grid whose range reaches outside Binance's price band faults at Start with an unreadable error

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
- **Every order, not only the Grid.** `OrderPreview.price_band_check` (`price_band_policy.check_price_band`) judges any order that has its own price and a `last_price`, using the same reference the stop gate uses.
  - `ExecuteOrderCommandHandler` refuses `OUTSIDE_PRICE_BAND` before any request, as `MIN_NOTIONAL` is refused (`BUG-090`). Desk orders and strategy orders are covered.
  - The order panel and the CLI say it in words: "The price is too far from the market: Binance accepts this side only within its price band around the current price".
- **No silent filter again (P1).** `UNREAD_SPOT_FILTERS` names every Spot filter the app deliberately does not read, with a reason.
  - A guard test requires Binance's whole documented filter list to be either read or declared unread.
  - A filter in neither group is logged once per catalog load as an `[exchange-filters]` WARNING. See [CS-007](../../../Docs/CASE_STUDIES/CS-007_the_filter_nobody_read.md).
- **Limit:** the band follows the market, and the app judges it at the last price where Binance uses the average over `avgPriceMins`. An order sent without a `last_price` skips the check, for example the Grid's reaction orders, which sit next to a level that just filled.
- **Not changed:** the Futures parser does not read `PERCENT_PRICE` (CS-007, still open).

## Regression test

- `tests/unit/modules/bots/domain/grid/test_grid_price_band_check.py` was red before the fix: no band verdict existed.
  - A BUY below the band refuses and names both prices.
  - A BUY exactly at the floor passes. Changing `<=` to `<` turns this red.
  - A SELL above the band refuses. Skipping the SELL loop turns this red.
  - No band means the check did not run.
- `tests/unit/modules/trading/adapters/binance/spot/test_spot_metadata_parser.py`: the band is parsed when published and is `None` otherwise.
- `tests/unit/modules/bots/application/services/test_bot_exchange_terms.py`: the band reaches the bot's terms.
- `tests/unit/modules/trading/application/orders/test_execute_order_price_band.py` was red before the fix: the order outside the band reached the client.
  - A BUY below the band and a SELL above it are never sent.
  - Both edges pass.
  - No last price means no verdict.
- `test_execute_order_block_reason.py`: the refusal is explained in words.
- `test_spot_metadata_parser.py::test_every_spot_filter_is_read_or_declared_unread` turns red when a declaration is removed. `test_a_filter_nobody_declared_is_logged_once_by_name` checks the WARNING.

## Verification

- Trading, strategy and bots unit tests and the application integration tests passed (2973).
- **Not yet run:** a live Start on Spot Testnet with a range below the band. The user's next run is the live check.
