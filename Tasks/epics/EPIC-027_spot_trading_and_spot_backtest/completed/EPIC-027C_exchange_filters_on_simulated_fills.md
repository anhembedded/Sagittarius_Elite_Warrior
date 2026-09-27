# EPIC-027C — A simulated fill obeys the exchange's step size, minimum notional and tick size

**Status:** ✅ Done (2026-09-27)
**Source:** found while measuring the Spot gap, 2026-09-26. This is part of the user's *"back test theo spot"* request.
**Risk:** 🟡 — changes the numbers of every backtest, Futures included; must be explicit and reported.
**Complexity:** M — metadata lookup per market, rounding in one place, a rejection counter.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027A](EPIC-027A_market_aware_kline_storage_and_download.md), which provides market-keyed metadata.

---

## 1. Context and problem
- Backtest quantities are unrounded floats. Nothing in `src/modules/backtesting/domain` or
  `application` reads LOT_SIZE, the step size or the minimum notional.
- `BrokerSimulationConfig.tick_size` is a hard-coded default of 0.01, not the symbol's real tick.
- Filters today are only a UI hint: `ui/coordinators/strategy_config_coordinator.py:230-265` warns
  when `capital / last_close` is too small.
- Spot exchange filters are already parsed for backtesting from `GET /api/v3/exchangeInfo`
  (`market_data/adapters/binance/market_metadata_parser.py:21-42`). Futures filters come from a
  different endpoint.
- The live path already has an exchange-agnostic Decimal rounding policy
  (`trading/domain/policies/order_quantity_rounding_policy.py:87-130`).

## 2. Acceptance criteria
- [x] Entry quantity is floored to the symbol's step size for the backtest's market.
- [x] An entry below the minimum notional is not filled. It is counted as rejected with a reason, and
      the run continues.
- [x] Price rounding uses the symbol's real tick size when metadata is available. When metadata is
      missing, the run states which default it used.
- [x] Whether filters were applied, and their values, are recorded in the backtest result and report.
      The result carries them (`BacktestResult.exchange_filters`, `rejected_entries`); the report
      schema writing them is `EPIC-027E`, whose own criteria already name the filter provenance.
- [x] A regression test shows a run whose unrounded quantity would violate LOT_SIZE.

## 3. Design
- One rounding place: `FillPricing.entry_capital` (`domain/fill_pricing.py:199-237`). It reuses the
  rounding rules of the live policy, so backtest and live cannot disagree on the same symbol. The
  rules are moved to a shared domain helper if the module boundary requires it.
- Metadata is keyed by (market, symbol), from `EPIC-027A`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/backtesting/domain/fill_pricing.py` | floor to step, reject below minimum notional, tick from metadata |
| `src/modules/backtesting/contracts/broker_simulation_config.py` | carry the symbol filters instead of a fixed `tick_size` default |
| `src/modules/backtesting/application/run_static_backtest/handler.py` | resolve filters for (market, symbol) before the run |

## 5. Testing
- **Unit, new:**
  - `contracts/test_exchange_filters.py`: impossible filter values are refused.
  - `domain/policies/test_exchange_filter_policy.py`: step floor, including the float edge values
    `0.1 + 0.2` and `0.3`; never rounding up; the minimum-quantity and minimum-notional boundaries
    at and around each edge; a no-op without filters.
  - `domain/test_paper_exchange_exchange_filters.py`:
    - A Spot BTCUSDT entry is floored to the step, and the remainder stays cash.
    - Fees are paid on the floored order, and cash is conserved.
    - A leveraged Futures entry is floored and its margin scaled.
    - Entries below the minimum notional are rejected and counted, and the run continues.
    - Slippage moves by the symbol's real tick.
    - Without filters, the quantity is unrounded exactly as before.
  - `application/test_exchange_filters_backtest.py` (business acceptance, a real static run):
    - No quantity is finer than the 0.00001 step. The unrounded 0.0300003… BTC would violate
      LOT_SIZE.
    - The result records the filters.
    - Rejected entries are counted.
  - `ui/coordinators/test_execution_coordinator.py`: the run applies the filters of its own
    (market, symbol), or none without metadata.
- **market_data, per market:**
  - The client test proves Futures filters come from `/fapi/v1/exchangeInfo`, through the shared
    parser.
  - The metadata-provider contract suite now includes "a symbol known on one market is unknown on
    another".
- **Golden:** unchanged numbers. The run carries no filters (`exchange_filters: null`), so the diff
  only adds keys.
- **Suites:** 5612 unit passed. 168 integration passed, 4 skipped. 32 sanity passed. Architecture 445 passed. mypy clean
  (`src` + `scripts`). `ruff check` and `ruff format --check` are clean on the whole tree.

## Implementation notes (written when done)
- **One rounding place, the live path's arithmetic.** `ExchangeFilterPolicy`
  (`domain/policies/exchange_filter_policy.py`) wraps `trading`'s published
  `OrderQuantityRoundingPolicy`:
  - Quantities are floored with `Decimal(repr(x))`. `repr`, not the exact binary expansion, so
    `0.3` does not floor one step short.
  - The notional is compared in `Decimal`.
  - `FillPricing.entry_capital()` returns an `EntryCapital`, which carries a rejection reason. The
    earlier three-zeros answer meant "unfundable" and "refused by the exchange" alike.
  - The floored order pays the fee of the smaller order (`FeeCalculatorPolicy.entry_fee_for_quantity`,
    the inverse of the sizing formula). Its margin shrinks in proportion, so what the floor did not
    buy stays in cash.
- **Rejections are counted where the entry is decided.** `PositionLifecyclePolicy` counts them,
  `PaperExchange.rejected_entries` exposes them, and both handlers put them on the result.
- **Tick size.** `BrokerSimulationConfig.price_tick_size` uses the symbol's tick when filters are
  known, otherwise the `tick_size` default. Slippage is the only price the engine offsets by ticks.
  Stop-loss and take-profit prices are **not** rounded to the tick; that is a deliberate scope
  limit, left as an extension case in the policy's docstring.
- **Where the filters come from.** The Backtest screen's pre-run sync already warms the metadata
  cache (`BUG-127`). `ExecutionCoordinator` reads that cache for the run's (market, symbol) and
  copies the values into the command's `BrokerSimulationConfig.exchange_filters`, so the run and
  its result carry the exact rule they used.
  - No metadata means `None`: nothing is floored, nothing is refused, and the result and the
    limitations text say so.
  - A headless caller (the golden run, tests) passes `None` the same way.
- **Metadata per market.** `ISymbolMetadataProvider`, `ISymbolMarketMetadataCache` and
  `IExchangeClient.get_symbol_metadata()` take a `MarketType`. USD-M Futures filters come from
  `/fapi/v1/exchangeInfo`: the same parser reads Futures' `MIN_NOTIONAL.notional`. Spot's filters
  can no longer stand in for Futures'.
- Delivered together with `EPIC-027D`, in one pull request, as the user asked.
