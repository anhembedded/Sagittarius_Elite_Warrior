# EPIC-026L — A daily-loss and drawdown circuit breaker trips Emergency Stop by itself and stays tripped across a restart

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 5; ADR D9; the user (2026-09-20):
*"hãy cho lô trình để có thể giao dịch thật"*.
**Risk:** 🔴 — it closes positions without a human; a wrong PnL sum trips it on a winning day or
never trips it on a losing one.
**Complexity:** M — one policy, one subscriber, one journaled state, one refusal in enable.
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-004` §5 (a new enable refusal) and `SPEC-007` §1 (a second trigger).
**Depends on:** [`EPIC-026G`](EPIC-026G_trade_journal.md) (realised PnL per day; breaker state)

---

## 1. Context and problem

The four limits (`trading_limit_policy.py:30-80`) are counts, a notional and an interval; none
reads profit or loss. `EquitySampledEvent` and `EquityCurveRecorder` already carry the account's
equity per `ACCOUNT_UPDATE` (`EPIC-021M`), but only to draw a chart. A strategy that is wrong all
day is stopped by a human noticing. The breaker is the one control every risk reference puts
first, and the one this app lacks entirely.

## 2. Acceptance criteria

- [ ] `CircuitBreakerPolicy.evaluate(day_realised_pnl, session_peak_equity, current_equity,
      limits) -> BreakerDecision` with two thresholds from config: `trading.max_daily_loss_usdt`
      and `trading.max_drawdown_percent` (peak-to-trough on the session's equity samples).
- [ ] A subscriber to `OrderFilledEvent` and `EquitySampledEvent` evaluates after each; a trip
      dispatches `EmergencyStopCommand` (the existing one — no second close path), journals
      `breaker_state = TRIPPED(day, reason, values)`, and publishes `CircuitBreakerTrippedEvent`.
- [ ] While tripped, `EnableTradingCommand` refuses with a new reason `BREAKER_TRIPPED` until the
      UTC day rolls over; the state is read from the journal, so a restart does not reset it.
- [ ] The Trading screen shows the breaker's two live values against their limits at all times
      (the same "every refusal names itself" rule as `SPEC-004` §4).
- [ ] A protective-stop placement failure (`EPIC-026K`) trips it with its own reason.
- [ ] A drill: `main.py breaker-drill` sets the daily-loss limit to a value already exceeded on
      Testnet and proves the whole chain runs (`fix-bug-rule.md` §3's positive proof), logged
      under `App.CircuitBreaker`.

## 3. Design

Pure policy in `trading/domain/policies/`; the subscriber in `trading/application/session/`
beside the enable/disable/stop handlers, because the breaker is session policy. Daily PnL comes
from the journal's fills (realised), drawdown from the equity samples the recorder already has;
neither is recomputed from the exchange on every tick. The breaker never re-enables anything: the
day roll-over only removes the refusal, and the operator enables by hand (`SPEC-004`'s "off is
the safe end state").

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/trading/domain/policies/circuit_breaker_policy.py` | Pure policy |
| `src/modules/trading/application/session/circuit_breaker/{subscriber,drill}.py` | Evaluate on events; dispatch stop; drill command |
| `src/modules/trading/contracts/events/circuit_breaker_tripped_event.py` | New; `EventRegistry` row |
| `src/modules/trading/contracts/enable_trading_result.py` | `BREAKER_TRIPPED` |
| `src/modules/trading/application/session/enable_trading/handler.py` | Read breaker state first |
| `src/modules/trading/ui/trading/trading_view.py`, `trading_view_model.py` | Two values vs limits |
| `src/config/config_keys.py`, `app_config.json` | Two limits |
| `tests/unit/modules/trading/domain/policies/test_circuit_breaker_policy.py` | Boundaries, both thresholds |
| `tests/unit/modules/trading/application/session/test_circuit_breaker.py` | Trip → stop dispatched → journaled; enable refuses; day roll-over |
| `Docs/SPEC/SPEC-004_….md`, `SPEC-007_….md` | Rows |
| `Docs/VOCABULARY/README.md` | Row: **Circuit breaker** |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Thresholds | policy unit test | unit | exactly at, one cent over, drawdown from a moving peak |
| Chain | subscriber unit test with a fake dispatcher | unit | one `EmergencyStopCommand`, one journal row, one event |
| Survives restart | enable handler unit test with a `TRIPPED` journal | unit | refuses; passes after roll-over |
| Drill on Testnet | `breaker-drill` | human | three Emergency Stop lines, journal row, log lines under `App.CircuitBreaker` — pasted here |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
