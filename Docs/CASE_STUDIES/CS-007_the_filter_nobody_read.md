# CS-007 — The filter nobody read

`BUG-146`: a Grid on BTCUSDT at about 85 000 had a BUY level at 2 222. It passed every check. Its Start faulted on the first order with `-1013 Filter failure: PERCENT_PRICE_BY_SIDE`, and the bot went from STARTING to ERROR. The gate was green. Binance published the filter in `exchangeInfo`, and the Spot parser skipped it without a word.

## Why nothing caught it

| Net | Why it was silent | Still open? |
| :--- | :--- | :--- |
| The Grid checks (`grid_checks.py`) | They judge every exchange rule `ExchangeTerms` carries. This rule was never in it. | no: `LEVEL_OUTSIDE_PRICE_BAND` |
| The pre-network refusals in `ExecuteOrderCommandHandler` (`BUG-090`) | They refuse what `OrderPreview` can judge. The preview had no band to judge. | no: `OUTSIDE_PRICE_BAND`, for every order with a price and a last price |
| `spot_metadata_parser.py`'s strict parsing | It is strict about the filters it reads. A filter it does not read was ignored with no log and no list, so the decision was never visible. | no: `UNREAD_SPOT_FILTERS` and the WARNING |

## The fix
- `tests/unit/modules/trading/adapters/binance/spot/test_spot_metadata_parser.py::test_every_spot_filter_is_read_or_declared_unread` requires every filter Binance documents to be either read or named in `UNREAD_SPOT_FILTERS` with a reason.
- At runtime, a filter in neither group is logged once per catalog load as `[exchange-filters]` WARNING.
- The band is read into `SymbolOrderMetadata.price_band`. It is judged in `OrderPreview.price_band_check` (`price_band_policy.py`) and in the Grid plan.

## Where else this is still open
- `futures_metadata_parser.py` does not read Futures' `PERCENT_PRICE`. Bots run on Spot only, and a Futures desk order outside that band is still refused by the exchange.
- An order sent without a `last_price` skips the band check, for example the Grid's later reaction orders. Those sit next to a level that just filled, so they are well inside the band.
