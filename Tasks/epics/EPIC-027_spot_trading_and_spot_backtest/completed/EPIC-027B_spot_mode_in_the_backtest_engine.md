# EPIC-027B — A backtest can run as Spot: long-only, 1×, never liquidated, shorts counted not taken

**Status:** ✅ Done (2026-09-27)
**Source:** the user, 2026-09-26: *"back test theo spot"* ("backtest on spot").
**Risk:** 🟡 — the fill path is shared with every Futures backtest; the default must stay byte-for-byte.
**Complexity:** M — one config field, one gate at `fill()`, one counter in the result.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027A](EPIC-027A_market_aware_kline_storage_and_download.md) (done). The engine change is independent, but a Spot run must read Spot candles.

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
- [x] `BrokerSimulationConfig.market_type` defaults to `FUTURES_USD_M`. Every existing backtest test
      passes unchanged, and one golden run is compared byte-for-byte.
- [x] With `SPOT`, validation refuses `long_leverage` or `short_leverage` other than 1.0, with a named
      error.
- [x] With `SPOT`, SHORT and COVER signals open and close nothing. The result reports how many were
      ignored, and the log records each one at DEBUG with a summary at INFO.
- [x] With `SPOT`, no trade can end with `ExitReason.LIQUIDATION`. A test drives a price crash through
      a long-only run and gets a stop or a loss, never a liquidation.
- [x] The tick backtest (`run_historical_tick_backtest`) honors the same gate.

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
| `src/modules/backtesting/domain/paper_exchange.py` | refuse SHORT/COVER when `SPOT` and count them (asks the new policy below) |
| `src/modules/backtesting/domain/policies/market_signal_gate_policy.py` | new — which actions a market can execute, the refusal count and its logs |
| `src/modules/backtesting/contracts/` (result) | `ignored_short_signals: int = 0` |
| `src/modules/backtesting/application/run_historical_tick_backtest/handler.py` | same config and gate |
| `src/modules/backtesting/application/run_static_backtest/handler.py` | passes the count to the result; comment on the Spot candle pin |
| `tests/integration/golden/backtest_golden_master.json` | regenerated: three `"ignored_short_signals": 0` keys added, nothing else changed |

## 5. Testing
- **Unit, new** (`tests/unit/modules/backtesting/`):
  - `contracts/test_broker_simulation_config_market_type.py` — the default is `FUTURES_USD_M`; `SPOT`
    refuses any leverage other than 1.0 (boundary values 0.5, 1.0001, 2.0 on either side); COIN-M is
    refused as unsupported (ADR D1).
  - `domain/test_paper_exchange_spot_market.py` — SHORT and COVER open and close nothing and are
    counted; a SHORT never closes an open long (ADR D4); the long side still trades; USD-M still
    shorts; a crash through a long-only Spot run ends in `STOP_LOSS` or an `END_OF_BACKTEST` loss,
    never `LIQUIDATION`; DEBUG per ignored signal, one INFO summary.
  - `domain/policies/test_market_signal_gate_policy.py` — the policy's action table and counter.
  - `application/test_spot_market_backtest.py` — both handlers, through the real engine and the
    verified `FakeMarketDataRepository`: a SHORT-emitting strategy trades only its long side and
    reports 3 ignored signals; the same strategy on USD-M still shorts; a static Spot crash stops out
    and never liquidates.
- **Mutation:** making `MarketSignalGatePolicy.admits()` return `True` turned 8 tests red; deleting
  either handler's `ignored_short_signals=` line turned that handler's Spot test red. All restored.
- **Golden:** `tests/integration/golden/` failed first on exactly three added keys
  (`$.ignored_short_signals`, and the same key on both out-of-sample halves). The file was regenerated;
  its diff is three `+ "ignored_short_signals": 0` lines and no deletions, so every pre-existing field
  of the Futures run is byte-for-byte unchanged.
- **Log proof** (`logging-rule.md` §9): one Spot static run through the app's real `StdLogger`
  (`DictConfig`, DEBUG, file handler) wrote `Market: spot` on the exchange's init line, three
  `[spot-gate] SHORT|COVER ignored at …` DEBUG lines, and `[spot-gate] 3 short-side signal(s) ignored in
  this simulation: spot is long-only` at INFO.
- **Suites:** Unit 5550 passed. integration 166 passed (4 pre-existing skips). Architecture 445 passed. mypy clean (`src` + `scripts`,
  703 files). `ruff check` and `ruff format --check` clean on the whole tree (`src tests tools scripts`).

## Implementation notes (written when done)
- **The gate is a policy, not four lines in `fill()`.** Inline, `paper_exchange.py` reached 399 lines,
  one under the 400-line ceiling (`architecture-rule.md` §5.4). `MarketSignalGatePolicy`
  (`domain/policies/market_signal_gate_policy.py`) holds the market → refused-actions table, the count,
  and both log lines; `PaperExchange` asks `admits()`, then `record_refusal()`, and calls
  `log_run_summary()` from `force_close()`. The file is now 387 lines. A market that restricts another
  action is one table entry.
- **COVER is counted too.** The criterion says "SHORT and COVER signals open and close nothing. The
  result reports how many were ignored", so both count. In Spot no short can be open, so a COVER is
  as unexecutable as a SHORT.
- **COIN-M is refused at construction.** ADR D1 keeps it unsupported. Letting it through would simulate
  COIN-M with USD-M arithmetic without saying so.
- **Candles stay pinned to Spot.** Both handlers still read Spot shards whatever `market_type` says.
  Following the `FUTURES_USD_M` default now would send every existing run to Futures shards nobody has
  downloaded. The read follows the market once the user can choose one; that row is now in
  `EPIC-027D`'s change table.
- **One INFO summary per simulation pass.** A static run with enough data makes three passes (the full
  range and BOT-080's two out-of-sample halves), so it logs three summaries. The result carries the
  full-range count. Each out-of-sample result carries its own.
- **The report does not carry the count yet.** The serializer writes neither `market_type` nor
  `ignored_short_signals`, and a loaded report reads them back as the defaults. That is `EPIC-027E`.
- Delivery: branch `claude/wizardly-cerf-fc5b5x`. GitHub Actions' `ci-local.ps1 -Full` check run is the
  pre-merge full-gate authority (`ci-rule.md` §1). Merge to `master-warrior` needs an independent
  reviewer session (`ONBOARDING.md` §7).
