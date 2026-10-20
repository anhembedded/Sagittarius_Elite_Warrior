# BUG-236 — A Futures order refused for its tick, step or price band is reported as an unknown rejection

- **Reported:** 2026-10-20 (found by the stricter fake exchange of EPIC-037E, PR 617 round 1)
- **Severity:** 🟢 P3 — the Grid checks tick, step and band before sending, so a live order rarely reaches the exchange off-filter; when one does (a desk order, a stale `ExchangeTerms`), the user is told "rejected" with no reason to act on
- **Status:** Open
- **Board:** A Futures order the exchange refuses with `-4014` (tick), `-4023` (step), `-4005` (maximum quantity), `-4013`/`-4002` (price band) maps to `UNKNOWN`, so the desk and the bots show no filter reason.
- **Context:** Place a manual order (`Docs/SPEC/SPEC-005_place_a_manual_order.md`) → Module `src/modules/trading/` → `adapters/binance/`
- **Environment:** Unknown (found by reading code against Binance's USDⓈ-M error-code page, fetched 2026-10-20); app at `01d188a`.

## Reproduction
Not yet reproduced against a live exchange. On the fake exchange of PR 617 (it answers the page's codes): send a Futures `LIMIT` order at `63000.05` on `BTCUSDT` (tick `0.10`) through `FuturesTradingClient.place_order`; expected `OrderRejectionReason.PRICE_FILTER`, actual `UNKNOWN`.

## Symptom
`_UNAMBIGUOUS_CODE_TO_REASON` in `src/modules/trading/adapters/binance/binance_error_translator.py` maps `-4164`, `-1111` and `-4003` for Futures, and `-1013` by message text (Spot's shape). The page lists `-4014` "Price not increased by tick size.", `-4023` "Qty not increased by step size.", `-4005` "Quantity greater than max quantity.", `-4013` "Price less than min price.", `-4002` "Price greater than max price."; none is mapped, and on Futures `-1013` is `INVALID_MESSAGE`, not a filter failure.

## Root cause
Not yet established beyond the missing entries above; the module's own note says the mapping "is written from Binance's documented Futures API error codes, not re-verified".

## Fix
Pending.

## Regression test
Pending.

## Verification
Not run.

## Suggested next steps
Add the five codes to the translator (`PRICE_FILTER` for `-4014`/`-4013`/`-4002`, `LOT_SIZE` for `-4023`/`-4005`) with a test per code; then check which screen text each reason produces.
