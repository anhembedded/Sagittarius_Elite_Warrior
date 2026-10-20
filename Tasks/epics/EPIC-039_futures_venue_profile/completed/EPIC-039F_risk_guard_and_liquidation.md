# EPIC-039F — A Futures plan that can be liquidated inside its own range is refused, and a running bot watches the exchange's liquidation price

**Status:** ✅ Done (2026-10-13) — pull request open
**Source:** the owner, 2026-10-10; [`EPIC-029K`](../../EPIC-029_bots_tab_grid_fast_track/cancelled/EPIC-029K_grid_on_futures.md) §1 ("on Futures the stop loss must sit before the liquidation price by at least one ATR"); [DESIGN §6](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🔴 — the guard decides whether a leveraged bot may start and when it must stop; a wrong estimate is a false assurance
**Complexity:** L — plan verdicts, thresholds, a runtime guard, a state machine, alert kinds
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) gains the Futures verdict words with `039H`.
**Design:** [DESIGN §5.3, §6](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§1, §5](../RESEARCH_2026-10-10_futures_grid.md) · **Decision:** O3, O4, O5
**Branch:** `claude/epic-039f-risk-guard`
**Depends on:** [039E](EPIC-039E_futures_settings_gate_and_readiness.md) (settings, brackets, facts), [039G](EPIC-039G_futures_costs_funding_and_pnl.md) (funding in the estimate's honesty). Alert kinds coordinate with [`EPIC-036B`](../../EPIC-036_alerting_module/completed/EPIC-036B_alert_sources.md).

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
- [x] `FuturesGridThresholds` (a frozen value like `GridThresholds`, editable defaults, no literal in a check): `min_liq_buffer_atr = 1`, `leverage_warn = 10`, `leverage_ceiling = 20`, `funding_adverse_share = 0.25` (with 039G), `liq_warn_distance` and `liq_critical_distance` as fractions of price (defaults chosen with the owner when the task starts and recorded).
- [x] `IRiskGuard.judge_plan(plan, settings, brackets, mark, terms) -> tuple[Verdict, …]` with the verdicts of DESIGN §6: `LIQUIDATION_INSIDE_RANGE` (REFUSED), `STOP_LOSS_NEEDED` (REFUSED when leverage > 1 per O3; WARNING at 1), `STOP_LOSS_AFTER_LIQUIDATION`, `NOTIONAL_ABOVE_BRACKET`, `MARGIN_TOO_SMALL`, `LEVERAGE_HIGH`, `LEVERAGE_ABOVE_CEILING` (REFUSED). Spot's guard answers `()`.
- [x] The liquidation estimate uses the **worst case per direction** (DESIGN §5.3): LONG at the lowest level with position `q·N` and the plan's average entry; SHORT at the highest; **NEUTRAL both**, each judged against the stop loss on its side. The bracket is **looked up for the worst-case notional**, not the first bracket. A property test: raising leverage never moves the estimate away from the range.
- [x] The guard never says "safe"; its OK verdict says "estimated liquidation price X, Y below the stop loss — an estimate" (`is_estimate`), and for Cross margin (not offered in this epic) would say optimistic. The word *estimate* is in the verdict text and in a test.
- [x] `IRiskGuard.watch(snapshot) -> RiskState` where `snapshot` carries the **exchange-reported** liquidation price, mark price, position, margin ratio (if the account read provides it — **to verify**), and a timestamp; `RiskState` is `SAFE | WARN | CRITICAL` with a reason; distance is measured on **mark** price (liquidation is on mark). A stale snapshot is `UNKNOWN`, never `SAFE` (the `ExchangeSnapshot` three-state pattern).
- [x] The executor reacts: `WARN` → one `LIQUIDATION_RISK` event (published on the bus like `BotRangeChangedEvent`, once per transition, re-armed when state returns to SAFE); `CRITICAL` → halt (`GridReason.LIQUIDATION_RISK`) and follow the Futures halt policy of 039H/039L (O8).
- [x] A position change with no tagged fill (`POSITION_CHANGED_UNORDERED` from 039D: a forced close, an ADL) halts with `GridReason.FOREIGN_FILL`; **how Binance marks a forced close is read from the official page first** (RESEARCH §8) and recorded here.
  - **Precondition from 039D (review of PR #485):** `POSITION_CHANGED_UNORDERED` assumes `ORDER_TRADE_UPDATE` reaches the app before the `ACCOUNT_UPDATE` of the same trade, which only the fake has shown. The guard therefore **confirms before it halts**: it re-reads `positionRisk` and the book once more, after the stream has had time to deliver the matching fill, and halts only if the divergence is still there. A `POSITION_MISMATCH` is judged the same way. Unconfirmed, it is logged and left running.
- [x] Alert kinds `LIQUIDATION_RISK`, `MARGIN_LOW`, `SETTINGS_DRIFT`, `FOREIGN_FILL` are proposed in a short section of this task for `EPIC-036B`; whichever of the two tasks lands second adds them once.
- [x] Spot verdicts, order and codes unchanged (the Spot journeys' expected verdict lists are a fixture).

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
Run 2026-10-13: see the evidence list in the implementation notes.

## Pitfalls
- The estimate is for **isolated** margin and one position; under Cross it is optimistic. This epic offers Isolated only (O5): keep it so, and make the guard refuse a Cross symbol setting.
- Liquidation is on **mark**; the bot's stop fires on **last**-price ranges today. A stop that only fires on last can sit "before" liquidation on paper and after it in practice during a wick — 039L moves Futures triggers to mark (`workingType=MARK_PRICE`).
- Do not let the guard *change* a parameter (the user's rule): it refuses or warns, never adjusts leverage or the stop.

## Implementation notes (written when done)

**Reuse survey (asked by the owner).** Three liquidation formulas existed. (1) `trading/contracts/liquidation_estimate.py` - Binance's isolated one-way formula with the bracket's rate and amount - is the **only one the guard uses**. (2) `backtesting/domain/policies/margin_risk_policy.py::liquidation_price` is a float, zero-maintenance simplification (`entry x (1 -/+ 1/leverage)`), the backtest's own; (3) `backtesting/domain/fill_pricing.py` has no liquidation formula (fill prices only). (2) is what `039K` should replace with the trading function. **Changed in the trading contract:** `estimated_liquidation_price` and `LiquidationTerms` are untouched (signature and behaviour); added beside them `BracketedPosition(side, quantity, entry_price, margin)` and `estimated_liquidation_price_in_brackets(position, brackets) -> LiquidationPriceEstimate`, which looks the bracket up for `quantity x entry_price` and calls the old function. `039K` should call that one.

**What shipped**
- Trading: the helper above (`test_liquidation_estimate_in_brackets.py`: the bracket of the notional, not the first; raising leverage never moves the estimate away from the entry).
- Domain: `FuturesGridThresholds` gains `min_liq_buffer_atr`, `leverage_warn`, `leverage_ceiling`, `liq_warn_distance`, `liq_critical_distance`, `liq_rearm_factor`, `risk_snapshot_max_age`, `risk_unknown_halt_after`, `position_recheck_delay` (validated: `0 < critical < warn < 1`); `futures_worst_case.py` (the extreme position per side with its average entry); `futures_grid_checks.py` (the plan verdicts); `futures_risk_classifier.py` (the run-time levels); `PlanRiskInputs`.
- Contracts: `IRiskGuard` (`judge_plan`, `watch`), `RiskSnapshot`/`RiskState`/`RiskLevel` (SAFE, WARN, CRITICAL, **UNKNOWN**), `IRiskSnapshotSource` and `IPositionRecheck` (`i_risk_reads.py`), `BotRiskChangedEvent`; `IBotFacts.on_position_divergence` (its one other implementer, the test double in `test_grid_kind.py`, changed with it).
- Application: `FuturesRiskGuard`, `SpotRiskGuard` (answers `()` and SAFE), `GridRiskWatch`, bound by an optional `GridExecutorDeps.risk_watch` builder and `GridFactParts.risk_watch`; `GridReason.LIQUIDATION_RISK`, `FOREIGN_FILL`, `POSITION_MISMATCH`, `POSITION_UNOBSERVABLE`.

**Decisions taken in the code (reversible).**
1. `judge_plan` takes one `PlanRiskInputs` (params, plan, symbol setting, brackets, mark, thresholds, ATR) instead of the five arguments the sketch lists: `code/quality.md` caps arguments at four.
2. **The exit on a side** is the one that closes that side at a loss: a LONG's is the stop loss (below the range); a SHORT's is the exit above the range, which the parameters call `take_profit`. A Neutral plan is judged on both. `039I` should rename or add a direction-aware stop if the owner wants a SHORT "stop loss" field.
3. `STOP_LOSS_AFTER_LIQUIDATION` (REFUSED) is an exit beyond the estimated liquidation price; closer than `min_liq_buffer_atr` daily ATRs is a separate WARNING code `STOP_LOSS_NEAR_LIQUIDATION`. Cross margin is refused with `CROSS_MARGIN_UNSUPPORTED`.
4. `FOREIGN_POSITION`, `FUNDING_ADVERSE`, `STEP_BELOW_FEES_FUTURES` and the available-margin check are **not repeated**: they exist as `039E`/`039G` rules and constraints. `NOTIONAL_ABOVE_BRACKET` is the largest notional the symbol allows at the *chosen* leverage (a different question from `039E`'s `leverage_above_bracket`); `MARGIN_TOO_SMALL` compares the worst case's initial margin with the capital the bot commits.
5. A snapshot with a position but no liquidation price is UNKNOWN, never SAFE. UNKNOWN publishes an event and logs; **after `risk_unknown_halt_after` (120 s) of being unable to judge** - UNKNOWN, or no reading ever - while the last known position is not flat (no reading at all counts as possibly exposed), the bot halts with `POSITION_UNOBSERVABLE`. Any judgeable reading restarts the clock. This is the owner's rule (below), built after the first push.
7. **Review of PR #486 (first round).** (a) The liquidation estimate is taken at **every step of the ladder** (`ladder_steps`: the position after each fill with its own average entry and margin), not only at the far edge: a position can be liquidated *between* two levels, before the next one fills (LONG 16x, stop 59990: liquidation near 60,172 after the 61,000 BUY, above the 60,000 level). `LIQUIDATION_INSIDE_RANGE` names the first such step; the stop checks read the full position's liquidation price (the exit is reached only after every level filled). (b) A bot with no reading at all is UNKNOWN, announced once, not silently SAFE. (c) the UNKNOWN halt and the notes were the owner's answers, built; (d) commit-lint fixed by rewording the one commit.
6. The watch **confirms before it halts** (the precondition from 039D's review): `on_divergence` waits `position_recheck_delay` (5 s, on the bot's monotonic clock, at the price-watch beat), re-reads, and halts only if the divergence is still there. A re-read that fails is asked again at the next beat; one that shows agreement is logged and the bot runs on.

**Binance facts read (official page, `llms-full.txt`, "Event: Order Update", USDS-M).** A forced close is an `ORDER_TRADE_UPDATE` whose client order id starts with `autoclose-` (liquidation, `X` = NEW); an auto-deleveraging one is `adl_autoclose`; the sample payload's comment lists a third, `settlement_autoclose-` (delisting or delivery). The fake already emits `autoclose-`. The guard does **not** key on the prefix: a position change with no tagged fill is a divergence however it came, and the prefix is only a label for the log. "Event: Margin Call" (`MARGIN_CALL`: cross wallet, positions' mark price and maintenance margin) exists on the same stream and is the likely source for `MARGIN_LOW`; **no reader of it exists**, and neither `positionRisk` nor the account read the app makes carries a margin ratio, so `RiskSnapshot` has no margin-ratio field.

**Alert kinds proposed for `EPIC-036B`** (whichever of the two tasks lands second adds them once; this task edits no alert module): `LIQUIDATION_RISK` (from `BotRiskChangedEvent` with `level` WARN or CRITICAL; SAFE re-arms), `FOREIGN_FILL` (from a halt with `GridReason.FOREIGN_FILL`), `SETTINGS_DRIFT` (halt with `GridReason.SETTINGS_DRIFT`, from 039E), `MARGIN_LOW` (needs a `MARGIN_CALL` reader first; not available today).

**Owner's numbers (answered).** Given by the owner in the coordinator session (`session_01PZn6EWxn6gytSGKwbuRJGg`) on 2026-10-13, about 10:30 UTC, to a question quoting the author's proposal, as the recommended option each time: `liq_warn_distance = 0.05` and `liq_critical_distance = 0.02` of the mark price ("Warn 5%, halt 2%"); and "Accept all" for: a snapshot older than 60 s is UNKNOWN (`risk_snapshot_max_age`); UNKNOWN for more than 120 s while a position exists is a halt reason (`risk_unknown_halt_after`); confirm-before-halt is one re-read after 5 s (`position_recheck_delay`); the SAFE re-arm hysteresis factor is 1.1 (`liq_rearm_factor`). The plan-time numbers stay as O3/O4 decided (`min_liq_buffer_atr` 1, `leverage_warn` 10, `leverage_ceiling` 20, `funding_adverse_share` 0.25). All are `FuturesGridThresholds` defaults.

**Evidence.** `test_futures_grid_checks.py` (17), `test_futures_risk_classifier.py` (10), `test_grid_risk_watch.py` (15, including the timed halt on prolonged UNKNOWN), `test_risk_guards.py` (3), `test_liquidation_estimate_in_brackets.py`, and on the Futures fake `test_a_futures_risk_guard_on_the_fake_exchange.py` (the exchange's own mark and liquidation price walk the guard SAFE -> WARN -> CRITICAL; the forced close reaches the book as `POSITION_CHANGED_UNORDERED`). The unit tier of `tests/unit/modules/bots`, `tests/unit/modules/trading/contracts` and `tests/unit/architecture` is green (4018); ruff and ruff format are clean; the full gate is the PR's run.

**Not done, by design.** No Futures executor exists (`BOT_MARKETS` is Spot until 039H), so nothing feeds `GridRiskWatch` a snapshot or a divergence in a running bot yet: 039H binds `GridExecutorDeps.risk_watch`, the snapshot source (`positionRisk` + mark) and the divergence subscription, and calls `judge_plan` in its Start. What the halt does with the position (close it reduce-only unless an exchange-side stop stands, O8) is 039H/039L's. The Spot verdict lists are untouched (`GRID_CONSTRAINTS` gained no row; `SpotRiskGuard.judge_plan` is `()`).

## Resume
Done in code with the owner's numbers; waits on review. Hand-offs: **039H** - bind `risk_watch`, call `judge_plan` at Start, read the O8 halt policy; **039J** - the liquidation row (`RiskState.reason`) and the verdict words; **039K** - call `estimated_liquidation_price_in_brackets` instead of `margin_risk_policy.liquidation_price`; **EPIC-036B** - the four alert kinds above.
