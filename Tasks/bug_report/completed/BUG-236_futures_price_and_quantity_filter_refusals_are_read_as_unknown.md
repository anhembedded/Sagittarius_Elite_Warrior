# BUG-236 — A Futures order refused for its tick, step or price band is reported as an unknown rejection

- **Reported:** 2026-10-20 (found by the stricter fake exchange of EPIC-037E, PR 617 round 1)
- **Severity:** 🟢 P3 — the Grid checks tick, step and band before sending, so a live order rarely reaches the exchange off-filter; when one does (a desk order, a stale `ExchangeTerms`), the user is told "rejected" with no reason to act on
- **Status:** Fixed (2026-10-20)
- **Board:** A Futures order refused for its tick, step or price band read as `UNKNOWN`; the translator mapped none of the USDⓈ-M filter codes. Fixed: a table of the family (`-4001`/`-4002`/`-4006`/`-4007`/`-4013`/`-4014`/`-4016`/`-4024`/`-4183`/`-4184`/`-4210`/`-4211` → `PRICE_FILTER`, `-4004`/`-4005`/`-4023` → `LOT_SIZE`) in `binance_error_translator.py`.
- **Context:** Place a manual order (`Docs/SPEC/SPEC-005_place_a_manual_order.md`) → Module `src/modules/trading/` → `adapters/binance/`
- **Environment:** Unknown (found by reading code against Binance's USDⓈ-M error-code page, fetched 2026-10-20); app at `01d188a`.

## Reproduction
Not yet reproduced against a live exchange. On the fake exchange of PR 617 (it answers the page's codes): send a Futures `LIMIT` order at `63000.05` on `BTCUSDT` (tick `0.10`) through `FuturesTradingClient.place_order`; expected `OrderRejectionReason.PRICE_FILTER`, actual `UNKNOWN`.

## Symptom
`_UNAMBIGUOUS_CODE_TO_REASON` in `src/modules/trading/adapters/binance/binance_error_translator.py` maps `-4164`, `-1111` and `-4003` for Futures, and `-1013` by message text (Spot's shape). The page lists `-4014` "Price not increased by tick size.", `-4023` "Qty not increased by step size.", `-4005` "Quantity greater than max quantity.", `-4013` "Price less than min price.", `-4002` "Price greater than max price."; none is mapped, and on Futures `-1013` is `INVALID_MESSAGE`, not a filter failure.

## Root cause
`binance_error_translator.py` → `_UNAMBIGUOUS_CODE_TO_REASON` (line 36 at `b83e34c5`) held `-4164`, `-1111`, `-4003` and `-4131` of the Futures filter family, and `translate_binance_error` (line 92, the `.get(exc.code, UNKNOWN)` at line 102) turned every other code into `UNKNOWN`. The table was written from a partial reading of Binance's page, so `-4014`, `-4023`, `-4005`, `-4013`, `-4002` and their siblings were never entered. Spot has no such gap: its filters all arrive as `-1013` with the filter name in the text, which `_translate_dash_1013` reads.

## Fix
`_FUTURES_FILTER_CODE_TO_REASON`, one table merged into the translator's map: `PRICE_FILTER` for `-4001`, `-4002`, `-4006`, `-4007`, `-4013`, `-4014`, `-4016`, `-4024`, `-4183`, `-4184`, `-4210`, `-4211`; `LOT_SIZE` for `-4004`, `-4005`, `-4023`. The page's symbol-configuration codes (`-4008`..`-4012`, `-4017`, `-4018`, `-4025`, `-4029`, `-4030`, `-4058`) stay `UNKNOWN` on purpose (the exchange's own table is wrong, nothing the order can fix). Retry: a filter refusal is a sizing defect, so it is not retryable; `order_outcome._NAMED_REFUSALS` already files both reasons under `ORDER_INVALID` (a grid rung is left empty, the bot halts when refused twice within a minute). No change to order sizing.

## Regression test
`test_binance_error_translator.py` (every code of the table, plus the configuration codes staying `UNKNOWN`) and `test_an_order_off_the_symbols_filters_is_refused_with_its_named_reason` in `test_futures_trading_client_order_lifecycle_against_fake_server.py` (min price, max price, max quantity through the stricter fake exchange). Red before: 19 failures, `unknown: APIError(code=-4005): ...`; green after. `-4014` cannot reach the exchange through the client, whose own step check refuses it first.

## Verification
Regression tests green (55 passed); `tests/unit/trading`, `tests/integration/infrastructure/binance`, `tests/unit/fake_exchange`, `tests/unit/modules/bots/application` and `tests/unit/architecture` green; `ci-local.ps1 -SkipTests` PASS. Codes read from Binance's USDⓈ-M error-code page on 2026-10-20, not re-verified live.
