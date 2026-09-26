# EPIC-027B — A backtest can run as Spot: long-only, 1×, never liquidated, shorts counted not taken

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-26: *"back test theo spot"* ("backtest on spot").
**Risk:** 🟡 — the fill path is shared with every Futures backtest; the default must stay byte-for-byte.
**Complexity:** M — one config field, one gate at `fill()`, one counter in the result.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027A](EPIC-027A_market_aware_kline_storage_and_download.md). The engine change is independent, but a Spot run must read Spot candles.

---

## 1. Context and problem
- `PaperExchange.fill()` dispatches BUY→open LONG, SELL→close LONG, SHORT→open SHORT and COVER→close
  SHORT (`src/modules/backtesting/domain/paper_exchange.py:216-231`). Nothing can turn SHORT off.
- A 1× LONG is already valued and settled with spot arithmetic and has no liquidation price
  (`domain/policies/margin_risk_policy.py:103,160,182`). A SHORT always has a liquidation price, even
  at 1×.
- `BrokerSimulationConfig` has no market field (`contracts/broker_simulation_config.py:20-69`).
- Strategies that emit SHORT today are `ema_trend_pullback_strategy.py:233-241` and
  `volume_spike_flow_strategy.py:254,294`.

## 2. Acceptance criteria
- [ ] `BrokerSimulationConfig.market_type` defaults to `FUTURES_USD_M`. Every existing backtest test
      passes unchanged, and one golden run is compared byte-for-byte.
- [ ] With `SPOT`, validation refuses `long_leverage` or `short_leverage` other than 1.0, with a named
      error.
- [ ] With `SPOT`, SHORT and COVER signals open and close nothing. The result reports how many were
      ignored, and the log records each one at DEBUG with a summary at INFO.
- [ ] With `SPOT`, no trade can end with `ExitReason.LIQUIDATION`. A test drives a price crash through
      a long-only run and gets a stop or a loss, never a liquidation.
- [ ] The tick backtest (`run_historical_tick_backtest`) honors the same gate.

## 3. Design
- The gate sits at the one place a signal becomes a position (`PaperExchange.fill()` or the lifecycle
  policy's open path), not in each strategy. Strategies stay market-agnostic. The exchange refuses
  what the market cannot do, the way a real Spot exchange would.
- The ignored count is a result fact. It rides on `BacktestResult` next to the trades, so the report
  and the UI can show it without re-deriving it (ADR D4).
- No new valuation formula. Spot reuses the existing 1× LONG branch (ADR D3).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/backtesting/contracts/broker_simulation_config.py` | `market_type` field with a default, and spot validation |
| `src/modules/backtesting/domain/paper_exchange.py` | refuse SHORT/COVER when `SPOT` and count them |
| `src/modules/backtesting/contracts/` (result) | `ignored_short_signals: int = 0` |
| `src/modules/backtesting/application/run_historical_tick_backtest/handler.py` | same config and gate |

## 5. Testing
- Unit (`tests/unit/modules/backtesting/`): config validation; the gate with a SHORT-emitting fake
  signal stream; no liquidation in spot.
- Regression: a golden Futures run before and after, compared field by field.
- Mutation: remove the gate and the spot test must go red.
- Not run yet.
