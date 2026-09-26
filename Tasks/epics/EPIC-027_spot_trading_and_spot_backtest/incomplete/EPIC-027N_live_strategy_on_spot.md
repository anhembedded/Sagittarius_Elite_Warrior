# EPIC-027N — An armed strategy trades Spot long-only, sized from the right balance, at 1×

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot"* ("I want to trade spot").
**Risk:** 🟡 — the automatic path places orders without a human click.
**Complexity:** M — an arming gate, sizing for BUY and SELL, a fixed leverage.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027M](EPIC-027M_spot_session_enable_and_emergency_stop.md). ADR O2 and O4 answered.

---

## 1. Context and problem
- `ArmedStrategyConfig.leverage` ranges from 1 to 125 (`contracts/armed_strategy_config.py:34-39,72`).
  Leverage is a sizing multiplier only; nothing calls `futures_change_leverage` (`manual_order_card.py:4-7`).
- `LiveTradingCoordinator` sizes as `status.usdt_balance × sizing% × leverage`
  (`src/modules/strategy/application/services/live_trading_coordinator.py:118-161`).
- `signal_action_to_order_intent.py:40-43` maps SHORT → SELL (not reducing) and COVER → BUY (reducing).
  On Spot, the first would try to sell an asset the account does not hold.
- Two shipped strategies emit SHORT: `ema_trend_pullback` and `volume_spike_flow`.

## 2. Acceptance criteria
- [ ] On a Spot venue, leverage is fixed at 1. The control is hidden, and a config value other than 1
      is refused, not silently clamped.
- [ ] Arming follows the user's answer to ADR O2. If "refuse" (recommended): arming a strategy that
      declares it can SHORT is refused with a reason naming the strategy. This needs the declared
      capability below.
- [ ] Strategies declare the directions they can emit (a seam; long-only strategies declare LONG only).
      A guard test checks that every registered strategy declares it.
- [ ] BUY size = quote (USDT) balance × sizing %. SELL size = the holding the app bought, floored to
      the lot step.
- [ ] A non-USDT-quoted symbol on Spot is refused at arming (ADR D9), unless O4 is answered otherwise.

## 3. Design
- The capability is declared by the strategy, not inferred by scanning its code (`architecture-rule.md`
  §7.3: a decision in a type, not in prose). Seam now: a `supported_directions` attribute on the base
  strategy with a default. Variant later: mixed-direction strategies on Spot, if O2 changes.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/strategy/domain/strategies/base_strategy.py` | `supported_directions` |
| `src/modules/strategy/application/services/live_trading_coordinator.py` | Spot sizing |
| `src/modules/trading/ui/strategy_arming_coordinator.py` | the arming gate and its message |
| `src/modules/trading/contracts/armed_strategy_config.py` | leverage fixed by market |

## 5. Testing
- Unit: sizing both sides; the arming refusal; the guard over all registered strategies.
- Integration: arm a long-only strategy on the fake Spot venue; a signal produces a correctly sized order.
- Not run yet.
