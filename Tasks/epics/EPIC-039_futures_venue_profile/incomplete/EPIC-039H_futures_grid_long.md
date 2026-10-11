# EPIC-039H — A Futures Grid runs Long: start, counters, reduce-only exits, stop, reconcile and restart

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10; [DESIGN §5, §8, §9](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🔴 — the first leveraged bot executor; the halt and stop paths decide what stands on the exchange
**Complexity:** L — the executor's variant points, five collaborators, journeys on the fake
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) is extended with the Futures Long journey (a new section, not a new file, unless the owner prefers a new SPEC).
**Design:** [DESIGN §5, §8, §9.1](../DESIGN_2026-10-10_futures_venue_profile.md) · **Decision:** D1, O1, O6, O8, O10
**Depends on:** [039B](EPIC-039B_direction_aware_grid_planner.md), [039D](EPIC-039D_exposure_book_for_positions.md), [039E](EPIC-039E_futures_settings_gate_and_readiness.md), [039F](EPIC-039F_risk_guard_and_liquidation.md), [039G](EPIC-039G_futures_costs_funding_and_pnl.md); owner answers O1, O6, O8, O10.

---

## 1. Context and problem
The Grid executor is an actor with one writer per bot (`grid_executor.py`, 286 lines) that delegates to collaborators: `GridStartSequence`, `GridLadderPlacer`, `GridStopper`/`GridStopSequence`, `GridReconciler`, `GridPriceReaction`, `GridHousekeeping`, `GridRecoveryReader`, `GridResumeSequence`, etc. Almost all of that is exposure-agnostic; four things are Spot-shaped and are the **variant points** of this task.

### Facts verified on `master-warrior` `076d339`
- **Start** (`grid_start_sequence.py:95-231`): earlier runs recorded; the opening **MARKET BUY** in slices ≤ the per-order cap (`D21`, `_buy_opening`, `_count_opening`); the bot has trading re-register its budget so inventory is derived from the exchange; the ladder is laid only when that inventory **covers the SELLs**; SELLs sized net of the opening's base-asset fee (`sells_net_of_opening_fee`). RUNNING on `ladder_ready` only once every other level rests.
- **Stop** (`grid_stop_sequence.py:100-237`): `run(base: BaseHandling, price)`: cancel tagged orders (`_cancel_tagged`), `_sell` the base (retry/rate-limit aware), `_confirm` zero open tagged orders → `stop_confirmed`; `grid_stopper.py` + `grid_stop_retry.py` handle STOPPING retries.
- **Halt** parks the ladder: every halt cancels the bot's tagged orders (the `_park` step, named in `grid_start_sequence.py:15` and called from `grid_task_guard.py:123`; find its definition with `grep -rn "def _park\|_park =" src/modules/bots`) and, today, leaves the base (the owner's log of 2026-10-09: six `cancel … -> done`, base left held).
- **Reconcile** (`grid_reconciler.py`, 362 lines — near the 400-line limit): steps 1–7 in its docstring: claim lease, register budget, read tagged open orders, apply fills first, adopt unknown tagged orders, **check the inventory** (`INVENTORY_MISMATCH`, `HOLDING_BELOW_INVENTORY`), persist and transition. `EPIC-035B`: the same steps 2–6 after a user-stream gap (`GridStreamGap`).
- **Price reaction** (`grid_price_reaction.py`): stop loss / take profit fire on the tick's low/high range (`GridTickExtremes`); the stop runs Stop with `SELL_AT_MARKET`.
- The restart rule: RUNNING/PAUSED → RECOVERING; nothing placed or cancelled at boot; the reconcile waits for the venue's trading switch/session (`bot_restore_service.py`, `SPEC-004`).
- File sizes to respect: >400 lines per file and >15 public methods per class force a split (`architecture-rule.md` §5.4).

## 2. Acceptance criteria
- [ ] The Grid kind's `supported_profiles` becomes `{SPOT, FUTURES_USD_M}`; the venue picker (UI task 039J) is the only user-visible switch; **until 039J a Futures Grid is creatable only through the application layer in tests**, so this PR changes no screen.
- [ ] **Variant points are collaborators, not branches.** Introduce `IOpeningStrategy` (`open(plan) -> OpeningResult`), `IExposureCloser` (`close(handling) -> StopProgress`), the exposure checks of the reconciler (`IExposureCheck`), and the counter-order flags — Spot and Futures implementations each, selected from the venue profile in `GridExecutorFactory`. **No `if futures` inside `GridStartSequence`, `GridStopSequence` or `GridReconciler`.**
  - *Futures opening (LONG):* the opening MARKET BUY of `q·k(P₀)` (the plan's signed opening quantity, 039B), sliced under the per-order cap exactly like Spot; the position is read from `IExposureBook` (derived from tagged fills, checked against `positionRisk`, 039D); **no base-fee netting**.
  - *Ladder:* BUY entries below; SELL counters above as **reduce-only** (`Order.reduce_only=True`, `plan` marks them, 039B/O10); post-only is **not** used (O10).
  - *Close (`CLOSE_AT_MARKET`):* cancel tagged orders, then a reduce-only MARKET close of the position (capped by the position: Binance caps, the fake does), then confirm **flat** (position zero) and zero open tagged orders.
  - *Reconcile:* the inventory checks become the **position checks**: `POSITION_MISMATCH` (derived vs `positionRisk` to within one step) and the foreign-position/unordered-fill rules of 039D/039F; steps 1–5 (lease, budget, tagged orders, fills first, adopt) are unchanged and shared.
- [ ] **Halt on Futures follows O8:** a halt cancels the ladder and, unless an exchange-side stop stands (039L; before it exists: **never**), **closes the position reduce-only**. The Spot halt behaviour (leave the base) is byte-identical (journey unchanged). A test proves a Futures bot halted by `price_feed_stale` on the fake ends **flat with no resting orders**.
- [ ] Stop loss and take profit on Futures use the **mark price** for the trigger: the price tick fed to `GridPriceReaction` is the mark tick for a Futures bot (`bot_price_watch` already opens the stream per `market_type`; the mark-price source is `IMarkPriceReader`, to be fed as a second tick source — design recorded here); a wick test on the fake.
- [ ] `RANGE_EXIT` behaviour per O6 (`hold` default): out of range the bot idles at maximum exposure and publishes the existing `BotRangeChangedEvent`; with `close`, it stops with the close policy.
- [ ] **Restart:** a Futures bot RUNNING at app close loads RECOVERING; at the trading switch the reconcile adopts its tagged orders, applies fills, derives the position, cross-checks `positionRisk`, and returns to RUNNING — or HALTED naming `POSITION_MISMATCH`. Tested with a kill in the middle of the ladder on the fake.
- [ ] **A user-stream gap** (`EPIC-035B`) on Futures runs the same `compare_with_exchange` with the position checks.
- [ ] A Futures bot cannot start with: a foreign position (039D), a settings mismatch (039E), a REFUSED guard verdict (039F). Each is a start refusal with the user-words from its task.
- [ ] **Sibling parity** (`EPIC-037D`'s idea): the same scenario table (fills in order, a partial fill, a rejected counter, a stream gap, a stop loss) runs against the Spot and the Futures LONG executor and the ladder states and PnL agree where they must (Futures differs only by leverage and funding).
- [ ] Spot: the entire `tests/integration/modules/bots/` suite and `tests/unit/modules/bots` pass unchanged.

## 3. Design
Strategy pattern at the four exposure-shaped joints; the actor, the queue, the FSM, the lease, the retry/rate-limit machinery and the persistence are shared and untouched (they are what the Spot soak `EPIC-029H` is proving). LONG first because the Spot oracle proves its planner and its opening is the Spot opening with a different book (O1). A halt is the dangerous path: the Futures closer is the *same* `IExposureCloser` the Stop uses, so one tested close serves Stop, stop loss, take profit and halt.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/contracts/i_opening_strategy.py`, `i_exposure_closer.py`, `i_exposure_check.py` (new) | the seams |
| `bots/application/services/opening_spot.py`, `opening_futures.py`, `closer_spot.py`, `closer_futures.py`, `exposure_check_spot.py`, `exposure_check_futures.py` (new) | adapters (moved code for Spot, byte-for-byte) |
| `grid_start_sequence.py`, `grid_stop_sequence.py`, `grid_reconciler.py`, `grid_executor_factory.py`, `grid_price_reaction.py` | call the collaborators; **file size must stay under 400** (split `grid_reconciler.py` first if needed, in its own commit) |
| `bots/application/services/futures_mark_tick.py` (new) | mark-price ticks for Futures stops |
| `bots/domain/grid/grid_kind.py` | `supported_profiles` |
| `tests/integration/modules/bots/` | Futures journeys on the fake (039C fixture) |

## 5. Testing
Tier: unit (collaborators), integration on the Futures fake. Each shown red first.
- `test_a_futures_long_starts_opens_the_position_and_lays_reduce_only_sells`
- `test_a_futures_bot_halted_by_a_stale_feed_ends_flat_with_no_orders`
- `test_a_stop_loss_on_a_mark_wick_closes_the_position_reduce_only`
- `test_stop_closes_confirms_flat_and_zero_orders`
- `test_a_restart_in_the_middle_of_the_ladder_recovers_orders_and_position`
- `test_a_stream_gap_reconciles_the_position`
- `test_out_of_range_holds_by_default_and_closes_when_asked`
- `test_start_is_refused_for_a_foreign_position_a_settings_mismatch_and_a_refused_verdict`
- `test_spot_and_futures_long_agree_on_the_shared_scenarios` (parity)
- the entire Spot suite, unchanged and green.
Not run yet. **Never against a real exchange**; Futures testnet runs are the owner's (039L).

## Pitfalls
- `grid_reconciler.py` is 362 lines: adding to it breaks the 400-line rule; split first.
- The Spot `_sell` path nets the opening's base fee and waits on balance; the Futures closer must not inherit those assumptions.
- A reduce-only order is *rejected* by Binance when it would not reduce (`-2022`, the fake mirrors it): a ladder out of step with the position produces rejections — they must be classified (`order_outcome.py`: `ORDER_INVALID`) and leave a rung EMPTY, never crash the ladder.
- A halted-then-closed Futures bot has realised a loss: PnL and the alert must say so (`STOP_FAILED` kind in `EPIC-036` covers a close that did not complete).
- Do not hold a position "temporarily" while waiting for the rate limit: the closer's rate-limit wait (`wait_for_rate_limit`) is already modelled for Stop; reuse it, and the position stays under the exchange-side stop meanwhile (039L).

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: ask the owner O1, O6, O8, O10; then read `grid_start_sequence.py`, `grid_stop_sequence.py`, `grid_reconciler.py` end to end and write down, line by line, which statements are exposure-shaped.
