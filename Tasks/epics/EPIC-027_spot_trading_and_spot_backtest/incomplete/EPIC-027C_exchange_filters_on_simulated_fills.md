# EPIC-027C — A simulated fill obeys the exchange's step size, minimum notional and tick size

**Status:** 🔵 Backlog
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
- [ ] Entry quantity is floored to the symbol's step size for the backtest's market.
- [ ] An entry below the minimum notional is not filled. It is counted as rejected with a reason, and
      the run continues.
- [ ] Price rounding uses the symbol's real tick size when metadata is available. When metadata is
      missing, the run states which default it used.
- [ ] Whether filters were applied, and their values, are recorded in the backtest result and report.
- [ ] A regression test shows a run whose unrounded quantity would violate LOT_SIZE.

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
- Unit: step floor, minimum-notional rejection, tick rounding; float-to-Decimal edge values.
- Business acceptance: a Spot BTCUSDT run with 0.00001 step size produces no quantity finer than the step.
- Not run yet.
