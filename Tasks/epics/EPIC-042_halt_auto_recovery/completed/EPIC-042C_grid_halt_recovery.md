# EPIC-042C — A Spot Grid halted by a quiet feed resumes through its Resume path when the feed has been healthy for 120 s

**Status:** ✅ Done (2026-10-17; pull request open)
**Source:** the owner, 2026-10-17, through the coordinating session (decision record [D1, D4, D5, D10, D11, D12](../DECISION_2026-10-17_halt_auto_recovery.md))
**Risk:** 🔴 — real money: it lays a ladder with no person present; the three-per-24 h budget and the exits re-check are the guards
**Complexity:** L — the director, the recovery run, the Grid's rule and probe, the wiring of the halt, the exits re-check
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042B](EPIC-042B_awaiting_recovery_state_and_ledger.md); rebases onto `EPIC-039L` C3 / C4-lite if they land first

---

## 1. Context and problem
`GridPriceReaction.check_age` halts the bot with `halt_with`; nothing brings it back. The mechanism of [the decision](../DECISION_2026-10-17_halt_auto_recovery.md) must act on the bot's worker, through `GridResumeSequence`, and never against a crossed exit.

## 2. Acceptance criteria
- [x] A Spot Grid halted for `price_feed_stale` or `user_stream_down` in `RUNNING` enters `AWAITING_RECOVERY`; in `PAUSED` it enters `HALTED` (D8); on a Futures venue it enters `HALTED` (D5). The shared probes are the price watch's and the user-stream watch's (`bots/application/services/watches/`), not Grid code.
- [x] After the probe has said *clear* for 120 s without a gap, the attempt is saved, the exits are re-checked on the fresh price, `propose` and `confirm` run, and the bot is `RUNNING` with a fresh ladder.
- [x] **The ladder is off the exchange on entering the state**: done in `042B` for a hand-driven transition (`GridTaskGuard._PARKED`); here the real halt does it, with a test that drives `price_feed_stale` from RUNNING and asserts zero tagged orders rest.
- [x] A gap inside the dwell restarts the dwell. The probe is a tick heard since the halt and younger than `RECOVERY_TICK_MAX_AGE_SECONDS` (15 s), read from the last tick, never from `GridPriceAge.stale_detail`; a feed silent since the halt never clears (test), and a feed of two ticks a minute never clears (test).
- [x] An Emergency Stop in the state ends the wait (`GridFacts._apply_switch`, done in `042B`); the recovery run does nothing with trading off.
- [x] A person's Resume in the state ends the wait and is not counted; the automatic run does not start while a person's proposal is held; the refusal table of the decision's §2.1 holds, row by row.
- [x] If the park on entering the state fails (the cancel is refused during the outage, "its orders may still rest"), the bot retries it before an attempt, or the attempt's `propose` cancels every tagged order first; a test refuses the entry cancel and asserts no ladder is laid over resting orders.
- [x] A fill missed while `user_stream_down` is reconciled: the Resume path books it from exchange evidence before laying (test on the fake exchange).
- [x] A stop loss or take profit crossed during the wait, or on the fresh price at the attempt, ends the bot as Stop with *sell base* forced, and no ladder is laid (a test per exit and per direction the Spot Grid runs).
- [x] The fourth halt inside 24 h is `HALTED` with a reason that says the three recoveries are used up; the ledger survives a restart (the bot file is reloaded in the test).
- [x] A bot still waiting after `stalled_after` publishes `BotRecoveryStalledEvent` once per wait and goes on waiting (and still recovers if the feed returns later); a refused attempt spends budget (D10).
- [x] A rate limit met by the attempt lands in `HALTED` with `RATE_LIMITED` and `GridRateLimitPause` resumes it as today (`_HALTED_BY_A_LIMIT` includes the new state).
- [x] A person's Stop, Emergency Stop and Resume in the state do what the table says.
- [x] Positive proof in the run log: `[bot-transition]` lines and a new `[bot-halt-recovery]` line per entry, attempt and outcome (`logging-rule.md` §9: seen through the real logging configuration).
- [x] Spot behaviour that is not a transient halt is byte-for-byte unchanged.

## 3. Design
Decision §2.1 (the recovery run) and §2.2. `HaltRecoveryDirector` and `BotRunState.halt` in `application/services/lifecycle/`; the run is a method called from the price watch's beat; `GridResumeSequence.confirm` takes the event to apply (`resume` by default, `condition_cleared` here), not a flag; the Spot Grid's rule is declared in the kind, its probe over `GridPriceAge`.

## 3a. Reuse
Used `GridResumeSequence.propose/confirm`, `GridPriceAge`, `IMonotonicClock`, `GridStopper.run`, `crossed_exit`. Not used: `IBotRetryScheduler` (the beat already runs; a second timer would race the first).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.../services/lifecycle/halt_recovery_director.py` (new), `bot_run_state.py` | the decision and the ledger write |
| `.../kinds/grid/watch/grid_price_reaction.py`, `grid_price_age.py` | route the halt, probe, `_WATCHES_EXITS` |
| `.../kinds/grid/recovery/grid_halt_recovery.py` (new), `grid_resume_sequence.py` | the run; `confirm(proposal, event)` |
| `.../services/watches/bot_price_watch.py`, `user_stream_watch.py` | the two probes (common reasons, shared by every kind) |
| Module docs | Planned → Built |

## 5. Testing
Unit: director per state, ledger across the window, probe continuity. Integration (`tests/integration/modules/bots/`, fake exchange): the incident end to end, the exit crossing, budget across a restart, the Futures refusal. Mutation checks per `testing-rule.md`.

## 6. Docs touched
`06-runtime.md`, `05-building-blocks.md`, `10-quality.md`, `07-deployment.md` (the thread: the run is on the bot's worker), the diagram.

## Implementation notes (written when done)
- **Built as designed:** `HaltRecoveryDirector` (`BotRunState.halt` asks it; `halt_with` calls `halt`), `GridHaltRecovery` (the run, on the worker, at the price watch's beat), `GridHaltProbe` and the two contracts `IHaltConditionProbe` and `IUserStreamStatus` (with `UserStreamStatus` kept by `UserStreamWatch` and bound in `executor_bindings`), `GridPriceAge.heard_since`, `RECOVERY_TICK_MAX_AGE_SECONDS` (15 s, in the generated timing table), `recovery_policy_of` (the one place a bot's policy is resolved; the generated table calls it too), `GridResumeSequence.confirm(proposal, event)`, `BotAutoRecoveredEvent` and `BotRecoveryStalledEvent` (published; their alerts are `042D`).
- **Behaviour change, deliberate:** a RUNNING or STARTING Spot Grid halted by a quiet feed or a down stream now enters `AWAITING_RECOVERY` instead of `HALTED`. Eighteen older tests encoded the old state; each was read and updated, with the reason in its docstring (price age, user-stream watch, price-watch checks, exposure seams, and four integration journeys). A PAUSED or RECOVERING bot and every Futures venue still halt plainly.
- **The review's carried criteria:** a refused entry cancel leaves resting orders, and the attempt's `propose` cancels every tagged order first (a failed cancel stops the attempt, test `test_the_entry_park_that_failed_does_not_let_a_ladder_be_laid_over_resting_orders`); the probe reads the last tick and never `stale_detail`; a feed silent since the halt and a feed of two ticks a minute never clear.
- **Refusal table:** a moved price, a symbol that does not trade, a rate limit and a rejected key land `HALTED` through `halt_with` (each is a new cause); a refused budget registration changes nothing, spends the attempt, and with the budget spent ends `HALTED` through `budget_exhausted`.
- **Positive proof in the log:** the composed-app journey asserts the `[bot-halt-recovery]` lines for the entry (`is transient`), the attempt (`recovery attempt 1 of 3`) and the outcome (`recovered from price_feed_stale`), emitted through the real `App.Bots.GridExecutor` logger.
- **Mutation checks, each red then restored:** the exit re-check, the dwell reset, the saved attempt, the held-proposal guard, the stalled event, the budget boundary and the director's allowed states.
- **Not covered:** the alerts (`042D`); `run --resume-halted` (`042E`); a stream flap shorter than the 5 s beat is not seen by the dwell. The review of `042B` noted the generator names the Grid's layer constant, not each registered kind.
