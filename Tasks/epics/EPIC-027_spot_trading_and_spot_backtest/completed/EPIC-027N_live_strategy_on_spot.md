# EPIC-027N — An armed strategy trades Spot long-only, sized from the right balance, at 1×

**Status:** ✅ Done (2026-09-28)
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
- [x] On a Spot venue, leverage is fixed at 1. The control's hiding is `EPIC-027O`'s own AC3; this task
      owns the refusal — a config value other than 1 is refused (`SPOT_LEVERAGE_NOT_SUPPORTED`), never
      silently clamped.
- [x] Arming follows the user's answer to ADR O2 ("refuse"): arming a strategy that declares it can
      SHORT is refused (`SPOT_SHORT_NOT_SUPPORTED`) with a reason naming the strategy.
- [x] Strategies declare the directions they can emit (`BaseStrategy.supported_directions`, long-only
      strategies declare `{BUY, SELL}` by default). A guard test checks every registered strategy's own
      source against its declaration.
- [x] BUY size = quote (USDT) balance × sizing %. SELL size = the holding the app bought, floored to
      the lot step, never below the session's Spot baseline.
- [x] A non-USDT-quoted symbol on Spot is refused at arming (`SPOT_QUOTE_ASSET_NOT_SUPPORTED`, ADR D9/O4).

## 3. Design
- **The capability is declared by the strategy, not inferred by scanning its code** (`architecture-rule.md`
  §7.3: a decision in a type, not in prose). `BaseStrategy` gets a `ClassVar[frozenset[SignalAction]]
  supported_directions`, defaulting to `{BUY, SELL}` (long-only) — every strategy that never calls
  `self.short()`/`self.cover()` needs zero changes. `EmaTrendPullbackStrategy` and `VolumeSpikeFlowStrategy`
  are the only two that override it to add `SHORT, COVER`. A class attribute, not an instance one: the
  refusal at arm time (AC2) must answer from the registered *class*, before an instance is ever built —
  `StrategyRegistry.available()` already hands out classes, never instances, for exactly this kind of
  pre-construction question.
- **Where the refusal actually lives — corrected from this file's original file table.** The table below
  named `strategy_arming_coordinator.py` (UI) and `armed_strategy_config.py` (a `Deliberately unvalidated`
  dataclass per its own docstring) as the gate. Both are wrong for the same reason `i_trading_session.py`'s
  own docstring already records about a near-identical past mistake: *"a UI class enforcing a trading
  safety rule is backwards"* (`architecture-rule.md` §3). The one place that already asks "may this be
  armed at all" is `ArmStrategyCommandHandler.execute()` (`strategy/application/use_cases/arm_strategy/`) —
  every one of AC1/AC2/AC5's refusals is a new ordered check there, right after `STRATEGY_NOT_FOUND`,
  returning a new named `ArmStrategyBlockReason` member each: `SPOT_LEVERAGE_NOT_SUPPORTED` (AC1, checked
  against `ArmedStrategyConfig.DEFAULT_LEVERAGE`, i.e. `1.0` — reusing the existing constant rather than a
  new magic number), `SPOT_SHORT_NOT_SUPPORTED` (AC2), `SPOT_QUOTE_ASSET_NOT_SUPPORTED` (AC5, `symbol`
  must end with the same `"USDT"` quote-asset literal `emergency_stop/handler.py`/`spot_account_reader.py`
  already carry — a fourth copy of a pre-existing repeated literal, not a new one, per the PR #286
  reviewer's own non-blocking note on the third). AC1's other half — *hiding* the leverage control — is
  `EPIC-027O`'s own AC3 ("Leverage controls are hidden on Spot"), already listed there; this task only
  owns the refusal a hidden-but-bypassable control (a saved config, a race with venue switching) must
  still catch.
- **How the handler learns the venue, without a new cross-module edge.** `ArmStrategyCommandHandler`
  already depends on `trading`'s own `ITradingSession` (the seam PR 2.1f built for the symbol lease).
  `TradingSessionSnapshot` is deliberately minimal — its own docstring records exactly three "measured"
  facts and nothing else — but this task is a real fourth (and fifth) consumer, so it grows two fields:
  `market_type: MarketType | None` — `None` mirroring `TradingVenue.market_type`'s own optionality
  (`TradingVenue.DISABLED` trades no market at all) rather than inventing a Futures/Spot stand-in for
  "disabled" (`code/errors.md` #6); every consumer only ever asks "is this Spot?", which a `None` answers
  correctly the same as any other non-`SPOT` value — and `spot_baseline_holdings: Mapping[str, Decimal] |
  None` (the same optional three-state fact `EPIC-027M` already established: `None` = unknown/never
  enabled this session, `{}` = enabled while flat, non-empty = a real per-asset baseline). The alternative
  — injecting `TradingVenue`
  straight from `support/binance_gateway/contracts/` the way `trading`'s own handlers do — was rejected:
  `strategy` has never imported anything from `support/binance_gateway` (`grep` across `src/modules/strategy`
  confirms zero hits), and every fact it has ever needed from `trading` crosses through `ITradingSession`/
  `contracts/` already, so extending the existing seam is the smaller, more consistent change over opening
  a new one. `TradingSessionService` (the port's only implementation) gains a `trading_venue: TradingVenue`
  constructor dependency (already bound unconditionally — zero composition-root changes, same pattern
  `EPIC-027M` used three times over) and reads the baseline straight off the `TradingSessionState` it
  already holds (`self._session_state.spot_baseline_holdings()` — no `read_all()` tuple change needed).
- **SELL sizing reuses Emergency Stop's own safety mechanism instead of inventing a second one.** AC4's
  "SELL size = the holding the app bought, floored to the lot step" is exactly `EPIC-027M`'s
  `sellable_spot_quantity(current_total, baseline_quantity, step_size)` — a strategy's own SELL signal
  must never sell the pre-existing baseline either, for the identical reason Emergency Stop must not.
  Inventing a second, parallel "how much may Spot sell" rule would be the shared-formula-diverges trap
  `pitfalls/source.md` #2 already names. The function itself moves from
  `trading/domain/policies/spot_holdings_close_policy.py` to `trading/contracts/spot_holdings_close_policy.py`
  — `strategy` cannot import across the `trading.domain` boundary (`architecture-rule.md` §3: a module
  crosses only through another module's `contracts/`), and `OrderQuantityRoundingPolicy` already sits in
  `trading/contracts/` for this exact reason (a pure policy function/class that a second module legitimately
  needs). `EmergencyStopCommandHandler`'s own import updates in the same commit; its behaviour is
  byte-for-byte unchanged, only its import path moves.
- **`LiveTradingCoordinator`'s two sizing paths.** BUY keeps the existing `calculate_live_order_quantity()`
  path unchanged on every venue (Spot's `usdt_balance` is already the Spot quote balance, `EPIC-027H`) —
  fixing `leverage=1` at arm time (AC1) is already enough for a correct BUY size, no new branch needed. SELL
  branches only on `market_type is MarketType.SPOT`: it re-fetches current holdings via the already-injected
  `ITradingAccountReader` (never trusting a stale value, the same discipline `EPIC-027M` established), reads
  the baseline off a newly-injected `ITradingSession` (auto-wired, already bound), and refuses (publishing
  `LiveOrderBlockedEvent`, never silently) when no baseline was ever recorded — the identical "unknown
  baseline, sell nothing" rule `EPIC-027M` applies to Emergency Stop, now applied to the strategy's own exit
  signal too. Futures SELL/SHORT/COVER keep the pre-existing `calculate_live_order_quantity()` path
  unchanged; `SHORT`/`COVER` can never reach a Spot-armed coordinator at all once AC2's arming refusal is in
  place, so no Spot branch is needed for them.
- **The guard test proves the declaration, not just its existence** (AC3). Every strategy `BaseStrategy`
  registers is source-scanned (`inspect.getsource`) for a literal `self.short(`/`self.cover(` call; finding
  one without the matching member in that class's own `supported_directions` fails the guard — a strategy
  cannot silently gain SHORT capability without updating the declaration a live Spot arming depends on.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/strategy/domain/strategies/base_strategy.py` | `supported_directions: ClassVar[frozenset[SignalAction]]`, default `{BUY, SELL}` |
| `src/modules/strategy/domain/strategies/ema_trend_pullback_strategy.py`, `volume_spike_flow_strategy.py` | override to add `SHORT, COVER` |
| `src/modules/strategy/application/services/live_strategy_session.py` | `declared_directions(key)` accessor, mirrors `available_strategy_keys` |
| `src/modules/strategy/application/use_cases/arm_strategy/handler.py` | the three Spot refusals |
| `src/modules/strategy/contracts/arm_strategy_result.py` | three new `ArmStrategyBlockReason` members |
| `src/modules/trading/contracts/strategy_arm_result.py` | the identical three members on trading's own mirrored `ArmStrategyBlockReason` (`live_strategy_config_translation.py` already translates by `.value`, unchanged) |
| `src/modules/trading/ui/arm_block_messages.py` | new — `ARM_BLOCK_MESSAGES`/`DISARM_BLOCKED_MESSAGE` moved here, plus copy for the three new reasons; extracted because `strategy_arming_coordinator.py` was already over `architecture-rule.md` §5.4's shrink-only 424-line baseline with no room to grow (`test_god_files_only_shrink.py`); `baseline_god_files.json`'s entry for it is removed now that it measures under 400 |
| `src/modules/trading/ui/strategy_arming_coordinator.py` | imports the messages instead of declaring them |
| `src/modules/trading/contracts/i_trading_session.py` | `TradingSessionSnapshot` gains `market_type`, `spot_baseline_holdings` |
| `src/modules/trading/application/session/trading_session_service.py` | reads and populates both new fields |
| `src/modules/trading/domain/policies/spot_holdings_close_policy.py` → `src/modules/trading/contracts/spot_holdings_close_policy.py` | moved, unchanged, so `strategy` may import it |
| `src/modules/trading/application/session/emergency_stop/handler.py` | import path only, no behaviour change |
| `src/modules/trading/composition/port_bindings.py` | `_build_trading_session` resolves `TradingVenue` too |
| `src/modules/strategy/application/services/live_strategy_factory.py`, `composition/state_bindings.py` | thread `ITradingSession` through to `LiveTradingCoordinator` |
| `src/modules/strategy/application/services/live_trading_coordinator.py` | `ITradingSession` dependency; Spot SELL sizing branch |
| ~~`src/modules/trading/contracts/armed_strategy_config.py`~~ | scope correction — no change; leverage stays "deliberately unvalidated" by design |
| `Docs/SPEC/` | out of scope, same reason `EPIC-027M` deferred `SPEC-007` — no live-trading SPEC exists yet to extend |

## 5. Testing
- Unit: `BaseStrategy.supported_directions` default and the two overrides (`test_base_strategy.py`,
  `test_ema_trend_pullback_strategy.py`, `test_volume_spike_flow_strategy.py`); the guard over all six
  registered strategies' own source (`test_supported_directions_guard.py`, mutation-verified by hand —
  removing `SHORT` from `EmaTrendPullbackStrategy` while its `decide()` still calls `self.short()` turns
  it red for the right reason, then restored); the three new Spot arming refusals plus their two positive
  boundaries (1x/long-only arms fine) and a Futures-arming-is-unaffected case, exercised against real
  `LiveStrategySession`/`StrategyRegistry`/strategy classes so `declared_directions()` is proven through
  real use, not a second isolated test (`test_arm_strategy.py`); Spot SELL sizing — surplus, exactly-at-
  baseline (sells nothing), no baseline recorded (refuses, publishes a blocked event), a lot-step dust
  remainder, and that BUY keeps its own unchanged path (`test_live_trading_coordinator.py`).
- Integration: not added — every acceptance criterion is fully covered at the unit tier against the real
  domain objects (`EmaTrendPullbackStrategy`/`EmaCrossoverStrategy`, `LiveStrategySession`,
  `sellable_spot_quantity`), with only the network-facing collaborators (`ITradingAccountReader`,
  `IOrderSubmission`) faked/mocked; a fake-exchange journey would duplicate `EPIC-027K`'s own Spot
  order-path coverage without adding a new observable fact (the same call `EPIC-027M` made).
- Regression: `tests/unit` 5842 passed; `tests/integration` 184 passed, 4 pre-existing skips, 0 failed;
  `tests/unit/architecture` 459 passed. `ruff check`/`ruff format --check` clean across `src tests tools
  scripts`. `mypy` (run from the parent directory, the invocation GitHub Actions and the independent
  reviewer both use) unchanged at the pre-existing 584-error baseline, verified by exact diff before and
  after — an earlier same-repo invocation from inside the repo root falsely reported 2722/2737 errors
  from a namespace-package resolution artifact of that invocation directory, not a real regression.
- Full local gate (`ci-local.ps1 -Full`): not run locally, per `ci-rule.md` §1 (user decision
  2026-09-18) — GitHub Actions' `-Full` check run on the PR is the full-gate authority, cited once green.
