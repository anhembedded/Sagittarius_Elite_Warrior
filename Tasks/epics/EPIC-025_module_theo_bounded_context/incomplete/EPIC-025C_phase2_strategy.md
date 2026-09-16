# EPIC-025C — Phase 2: `modules/strategy` (the Core domain)

- **Status:** 🟡 Started 2026-09-16 — **PR 2.1a done** (the unblocking measurement and the one
  split it produced). The move itself, PR 2.1b, is next; §3 below is the cut, measured rather
  than estimated.
- **Repository:** Elite
- **Blocked by:** B · **Blocks:** D
- **Read first:** HLD §3.4; ADR D1 (`strategy` is the Core domain, separated from `trading` — the
  cost of keeping them merged was `BUG-112`).

## 1. What to do

1. `modules/strategy/`: `domain/strategies`, `services/live_strategy_*`, the
   `use_cases/trading/{arm, disarm}_strategy` handlers (moved out of trading),
   `StrategyArmingCoordinator` (392 lines, from `ui/common`), `signal_feed`.
2. `contracts/`: `IStrategyCatalog`, `IStrategyEngineFactory` (for `backtesting` in Phase 3), the
   DTOs `StrategyDescriptor` and `ArmedStrategySnapshot` (carrying `symbol`), the existing
   `SignalGeneratedEvent` (name unchanged) and the new `StrategyArmedEvent` / `StrategyDisarmedEvent`
   (carrying `symbol`).
3. `strategy` **consumes** `trading.contracts.IOrderSubmission` — never the reverse (Customer /
   Supplier: `trading` is the supplier). The symbol lease **adds to** the existing rules: `strategy`
   calls `ITradingSession.claim_symbol` on arm and `release_symbol` on disarm; `arm_strategy` still
   reads the session's enabled state. **Seam for two strategies on two symbols (ADR §7 item 15):**
   `LiveStrategySession` is keyed by symbol internally even while only one entry exists, so the
   second entry later is a local change. **ADR D17:** `position_sizing_bridge` and `MarginRiskPolicy` move here behind
   `strategy/contracts/ISizingPolicy`; `LiveTradingCoordinator` puts the computed quantity on the
   `OrderIntent`; the boundary-allowlist entry for `trading → backtesting` is removed in this phase. Signal overlays on
   the chart go through `IChartHost` (HLD §4).
4. Contributed widgets: the strategy card (one implementation shared by Trading and Dev Board), the
   last-signal card, the parameters dialog.

## 2. Done when

- The guard confirms that `modules/trading` imports **nothing** from `modules/strategy`, not even
  its `contracts/`.
- Arm / disarm / tick → automatic order runs on Testnet exactly as before (confirmed by the user).

---

## 3. The cut, measured 2026-09-16 before any code moved

`ls`-and-`grep` are not a measurement; these numbers come from walking the AST of every file in
`src/` and `scripts/`. **26 files / 2782 lines** would move under §1's list, with **13 consumer
files** naming them.

### 3.1 What the moving code reaches for that is not moving

| Dependency | Sites | What it means |
| :--- | ---: | :--- |
| `support.indicators.*`, `core.vo`, `core.contracts`, `modules.trading.contracts.*`, `support.ui_kit.*` | 44 | already permitted — nothing to unblock |
| `domain.value_objects.{signal_action,signal,live_strategy_config}` | 16 | strategy's own vocabulary; moves to `strategy/contracts` (HLD §02 line 89, §3.4) |
| `domain.events.signal_generated_event` | 2 | the same; the name stays (§1 item 2) |
| `application.services.live_trading_coordinator` | 2 | **not trading's, on measurement** — see §3.3 |
| `config.config_keys` | 1 | the legacy config keys module; Phase 5's |
| `presentation.ui.{common.strategy_display,components.strategy_params}` | 2 | strategy's UI; §1 item 4 |

### 3.2 Who reaches into it

13 files: `binance_bot_module.py` (10 imports — the strangler module still wires every strategy),
both big Presenters (4 each), the two backtest handlers, `trade_once_cmd`, `market_tick_event_handler`,
`backtest_presenter`, two `strategy_overlay` components, `strategy_params/bot_params_form.py`, and
two `scripts/` probes. Each becomes a counted `legacy → modules.strategy` allowlist entry when the
move lands and retires when its consumer moves onto a port — the shape `0.4a → 0.5` and
`1.3a → 1.3b` already ran twice, and the reason the allowlist header calls such a jump *"not a
regression"*. It is a different thing from the growth
[`DECISION_2026-09-16`](../DECISION_2026-09-16_the_duplication_criterion_waits.md) refused: there the
11 entries had **no** port to repay them before Phase 4, here every entry has a named repayment.

### 3.3 The finding: `trading` would have depended on `strategy`, and §2's done-when forbids it

`modules/trading/domain/policies/signal_action_to_order_intent.py` imports `SignalAction`. Move
`SignalAction` into `strategy/contracts` and that import becomes `trading → strategy` — which §2's
first done-when refuses outright, *"not even its contracts"*, and which ADR D1 separated the two
contexts to prevent.

Measured before deciding, and the file turned out to hold two unrelated things:

- `OrderIntent`, the `(side, reduce_only)` pair — **trading's own** vocabulary. Two producers
  (`order_intent_for()`, `manual_order_intent_for()`), and both consumers are *outside* the module,
  so by HLD §2.4's admission rule it already crosses the boundary.
- `order_intent_for()`, the `SignalAction → OrderIntent` table — **strategy's**, exactly what HLD
  §02 means by *"strategy only (plus trading through the bridge)"*. Its callers are
  `presentation/cli/trade_once_cmd.py` and `application/services/live_trading_coordinator.py`;
  **nothing inside `modules/trading` calls it.**

So `LiveTradingCoordinator` is strategy's too — it is the thing that turns a signal into an order,
and Customer/Supplier puts the translation on the customer's side — which also answers §3.1's
`live_trading_coordinator` row: it moves *in* rather than being reached for.

**PR 2.1a** therefore published `OrderIntent` as `modules/trading/contracts/order_intent.py` and
left the bridge where it is, ready to leave with its callers. Zero allowlist change, no behaviour
change, and it retired the naming compromise `order_request.py` and `Docs/SDD/05` both recorded:
`OrderRequest` was named around a collision with an `OrderIntent` in `domain/policies/`, and now
there is exactly one `OrderIntent` in the module, in `contracts/`, where HLD §3.4 always listed it.

### 3.4 The remaining pull requests

| PR | What | Allowlist |
| :--- | :--- | :--- |
| ~~2.1a~~ ✅ | `OrderIntent` published; the signal bridge identified as strategy's and isolated | unchanged (36) |
| **2.1b** | `modules/strategy/` arrives: `domain/strategies` (9), the six strategy services, `arm`/`disarm`, `LiveTradingCoordinator`, and `contracts/` for `Signal`, `SignalAction`, `LiveStrategyConfig`, `SignalGeneratedEvent` and the bridge | grows — one entry per consumer in §3.2, each named with the PR that retires it |
| 2.1c | `IStrategyCatalog` published; `strategy_registry`'s consumers move onto it | shrinks |
| 2.1d | `ISizingPolicy` (ADR D17): `position_sizing_bridge` and `MarginRiskPolicy` move in; the `trading → backtesting` entry retires | shrinks |
| 2.1e | the UI: `strategy_arming_coordinator`, `signal_feed`, `strategy_display`, `strategy_params`, `strategy_overlay` → `modules/strategy/ui/`, with the strategy card contributed to both surfaces (§1 item 4) | shrinks |
| 2.1f | `ITradingSession.claim_symbol`/`release_symbol` — the lease `IOrderSubmission` shipped without, whose first consumer is `arm_strategy` (`Docs/SDD/05` §3) | unchanged |

`2.1e` is also where §3.1's `strategy_params` row is answered: HLD §3.5 assigns that package to
`support/indicators`, the rule table cannot satisfy it (`bot_params_form.py` needs `BaseStrategy`),
and a form rendering *a strategy's* parameters is `modules/strategy/ui`. That was recorded as open
for the user in `EPIC-025E`; Phase 2 existing is what makes it answerable, and the HLD row is fixed
in that pull request rather than left to disagree with the code.
