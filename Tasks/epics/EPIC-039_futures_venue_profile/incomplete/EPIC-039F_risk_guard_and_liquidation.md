# EPIC-039F — A Futures plan that can be liquidated inside its own range is refused, and a running bot watches the exchange's liquidation price

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10; [`EPIC-029K`](../../EPIC-029_bots_tab_grid_fast_track/cancelled/EPIC-029K_grid_on_futures.md) §1 ("on Futures the stop loss must sit before the liquidation price by at least one ATR"); [DESIGN §6](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🔴 — the guard decides whether a leveraged bot may start and when it must stop; a wrong estimate is a false assurance
**Complexity:** L — plan verdicts, thresholds, a runtime guard, a state machine, alert kinds
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) gains the Futures verdict words with `039H`.
**Design:** [DESIGN §5.3, §6](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§1, §5](../RESEARCH_2026-10-10_futures_grid.md) · **Decision:** O3, O4, O5
**Depends on:** [039E](EPIC-039E_futures_settings_gate_and_readiness.md) (settings, brackets, facts), [039G](EPIC-039G_futures_costs_funding_and_pnl.md) (funding in the estimate's honesty). Alert kinds coordinate with [`EPIC-036B`](../../EPIC-036_alerting_module/incomplete/EPIC-036B_alert_sources.md).

---

## 1. Context and problem
Leverage multiplies loss. Pionex's estimate is a **worst case assuming every pending order on the risk side has filled** and liquidation is on **mark price** (RESEARCH §1). The app already has Binance's isolated one-way formula (`liquidation_estimate.py`), the brackets, the mark price and the exchange-reported `LivePosition.liquidation_price`. What is missing is the *policy*: when is a plan refused, and when does a running bot stand down.

### Facts verified on `master-warrior` `076d339`
- `trading/contracts/liquidation_estimate.py`: `LiquidationTerms(side, quantity, entry_price, margin, maintenance_margin_rate, maintenance_amount=0)`; `estimated_liquidation_price()` → `LiquidationPriceEstimate(price | None)` with `is_estimate` always `True`; **optimistic under cross margin; funding not counted**; its docstring: "the bracket is an input … a caller passes the first bracket's figures" until the brackets are read — they now are (`leverage_brackets.py`, via `IOrderEntryTerms`).
- `trading/contracts/live_position.py` `liquidation_price` is read from the exchange and typed so a local estimate cannot be passed where it belongs.
- The Grid's verdict machinery: `domain/grid/grid_constraints.py` (`run_checks`), `grid_checks.py` (`check_*`), `grid_check_inputs.py`, `domain/verdict.py` (`Verdict`, `VerdictSeverity` OK/WARNING/REFUSED), thresholds `domain/grid/grid_thresholds.py` (`GridThresholds`: "each number is advice … editable defaults; nothing here is read from a constant inside a check").
- `check_stop_loss` / `_exit_distance` (`grid_checks.py:286`) judge the stop 3–8 % below the lower limit; `check_range_against_atr` uses `inputs.market.daily_atr`.
- Mark and last: the bot's stop loss and take profit fire on the **tick's range** (`GridTickExtremes`, `BUG-191`) of last-price candles (`grid_price_reaction.py`).
- Alert kinds are `EPIC-036A`'s catalog; this task proposes new members, it does not edit that module.

## 2. Acceptance criteria
- [ ] `FuturesGridThresholds` (a frozen value like `GridThresholds`, editable defaults, no literal in a check): `min_liq_buffer_atr = 1`, `leverage_warn = 10`, `leverage_ceiling = 20`, `funding_adverse_share = 0.25` (with 039G), `liq_warn_distance` and `liq_critical_distance` as fractions of price (defaults chosen with the owner when the task starts and recorded).
- [ ] `IRiskGuard.judge_plan(plan, settings, brackets, mark, terms) -> tuple[Verdict, …]` with the verdicts of DESIGN §6: `LIQUIDATION_INSIDE_RANGE` (REFUSED), `STOP_LOSS_NEEDED` (REFUSED when leverage > 1 per O3; WARNING at 1), `STOP_LOSS_AFTER_LIQUIDATION`, `NOTIONAL_ABOVE_BRACKET`, `MARGIN_TOO_SMALL`, `LEVERAGE_HIGH`, `LEVERAGE_ABOVE_CEILING` (REFUSED). Spot's guard answers `()`.
- [ ] The liquidation estimate uses the **worst case per direction** (DESIGN §5.3): LONG at the lowest level with position `q·N` and the plan's average entry; SHORT at the highest; **NEUTRAL both**, each judged against the stop loss on its side. The bracket is **looked up for the worst-case notional**, not the first bracket. A property test: raising leverage never moves the estimate away from the range.
- [ ] The guard never says "safe"; its OK verdict says "estimated liquidation price X, Y below the stop loss — an estimate" (`is_estimate`), and for Cross margin (not offered in this epic) would say optimistic. The word *estimate* is in the verdict text and in a test.
- [ ] `IRiskGuard.watch(snapshot) -> RiskState` where `snapshot` carries the **exchange-reported** liquidation price, mark price, position, margin ratio (if the account read provides it — **to verify**), and a timestamp; `RiskState` is `SAFE | WARN | CRITICAL` with a reason; distance is measured on **mark** price (liquidation is on mark). A stale snapshot is `UNKNOWN`, never `SAFE` (the `ExchangeSnapshot` three-state pattern).
- [ ] The executor reacts: `WARN` → one `LIQUIDATION_RISK` event (published on the bus like `BotRangeChangedEvent`, once per transition, re-armed when state returns to SAFE); `CRITICAL` → halt (`GridReason.LIQUIDATION_RISK`) and follow the Futures halt policy of 039H/039L (O8).
- [ ] A position change with no tagged fill (`POSITION_CHANGED_UNORDERED` from 039D: a forced close, an ADL) halts with `GridReason.FOREIGN_FILL`; **how Binance marks a forced close is read from the official page first** (RESEARCH §8) and recorded here.
- [ ] Alert kinds `LIQUIDATION_RISK`, `MARGIN_LOW`, `SETTINGS_DRIFT`, `FOREIGN_FILL` are proposed in a short section of this task for `EPIC-036B`; whichever of the two tasks lands second adds them once.
- [ ] Spot verdicts, order and codes unchanged (the Spot journeys' expected verdict lists are a fixture).

## 3. Design
A guard *port* with two methods (plan time, run time), Spot a no-op adapter (Liskov: every profile answers; open/closed: a new risk is a new check in a list). Thresholds are *advice values the user may override* (the repo's rule: crossing one is a WARNING with the measured value beside it; REFUSED only where the plan is meaningless — here, when the bot can be liquidated before its ladder is used). The runtime guard reads what the exchange **reports**; the plan-time guard computes an **estimate** and says so (D6 of the domain-truth rule: never present an estimate as a fact).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/contracts/i_risk_guard.py`, `risk_state.py` (new) | port and values |
| `bots/application/services/risk_guard_futures.py`, `risk_guard_spot.py` (new) | adapters; the Futures one calls `trading/contracts` (`estimated_liquidation_price`, brackets, mark) only |
| `bots/domain/grid/futures_grid_thresholds.py`, `futures_grid_checks.py` (new) | thresholds and the plan verdicts (pure domain) |
| `bots/application/services/grid_executor.py` (+ a `GridRiskWatch` collaborator, new) | feed snapshots, react to states |
| `bots/domain/grid/grid_runtime.py` | `GridReason.LIQUIDATION_RISK`, `FOREIGN_FILL` |
| `bots/contracts/events/bot_risk_changed_event.py` (new) | the event the alert module will read |

## 5. Testing
Tier: unit (pure checks and states), integration on the Futures fake (039C: forced liquidation, a mark price moving toward liquidation).
- `test_a_long_whose_liquidation_is_inside_the_range_is_refused` · `test_a_neutral_plan_is_judged_on_both_sides`
- `test_the_bracket_for_the_worst_case_notional_is_used_not_the_first`
- `test_a_stop_loss_closer_than_one_atr_to_liquidation_warns` · `test_no_stop_loss_above_leverage_one_is_refused`
- `test_the_ok_verdict_says_estimate`
- `test_watch_reports_unknown_when_the_snapshot_is_stale`
- `test_a_critical_state_halts_and_a_warn_publishes_once_per_transition`
- `test_a_fill_the_bot_did_not_order_halts_with_foreign_fill`
- `test_spot_verdicts_are_unchanged`
Not run yet.

## Pitfalls
- The estimate is for **isolated** margin and one position; under Cross it is optimistic. This epic offers Isolated only (O5): keep it so, and make the guard refuse a Cross symbol setting.
- Liquidation is on **mark**; the bot's stop fires on **last**-price ranges today. A stop that only fires on last can sit "before" liquidation on paper and after it in practice during a wick — 039L moves Futures triggers to mark (`workingType=MARK_PRICE`).
- Do not let the guard *change* a parameter (the user's rule): it refuses or warns, never adjusts leverage or the stop.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: ask the owner O3 and O4 (their recommendations are in the decision record) and record the answers; then write the first red test (`LIQUIDATION_INSIDE_RANGE`).
