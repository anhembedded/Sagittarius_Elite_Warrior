# EPIC-042F — The grid rate-limit auto-resume runs on the halt-recovery mechanism

**Status:** ✅ Done (2026-10-20; pull request open)
**Source:** the owner, 2026-10-17, through the coordinating session (decision record [D6](../DECISION_2026-10-17_halt_auto_recovery.md)); the owner pre-approved the coordinating session's recommendations on 2026-10-20 and asked for each judgement call to be recorded as an agent decision they may veto
**Risk:** 🟡 — changes the state and the alerts a Spot owner sees during every rate-limit pause; no change to order sizing, stop or close logic
**Complexity:** M — one reason, one probe whose clear is the pause's end, the retired counter and timer
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042C](../completed/EPIC-042C_grid_halt_recovery.md)

---

## 1. Context and problem
`GridRateLimitPause` resumed a rate-limited Grid when the exchange's named pause ended: a timer on the retry scheduler, `MAX_AUTO_RESUMES` (five, consecutive, in memory, reset at `RUNNING`), a bot sitting in `HALTED`. It was a second recovery mechanism with its own counter, its own state and no exit check on a fresh price (the gap [D12](../DECISION_2026-10-17_halt_auto_recovery.md) accepted for it). The owner asked for the answer and a record ([D6](../DECISION_2026-10-17_halt_auto_recovery.md)), then for the work.

## 2. Acceptance criteria
- [x] **Decided first (the owner's pre-approved recommendation, 2026-10-20):** a rate-limited bot waits in `AWAITING_RECOVERY`; the timer is not kept as a `HALTED` special case. State and alerts change as the decision record says (agent decision A1 below).
- [x] `RATE_LIMITED` has a rule in the Grid's kind layer whose *clear* is the pause's end: the probe reads the pause the bot met (`GridRateLimitPause.holds`, read by `GridHaltProbe`). The consecutive counter, the timer, `MAX_AUTO_RESUMES`, `resume_delay` and `[bot-rate-limit-resume]` / `[bot-rate-limit-exhausted]` are deleted, not left beside it; the rolling budget of the bot's ledger applies.
- [x] A pause longer than `MAX_AUTO_RESUME_WAIT` still stays `HALTED` for a person, saying "resume by hand" (`pause_with`, `too_long_to_wait_words`).
- [x] A bot halted `RATE_LIMITED` resumes by itself at the pause's end, **every bot of the venue** on the same beat; a bot that only reads keeps its ladder; the other venue is unaffected ([runbook §8](../../../../Docs/OPERATIONS/headless_runbook.md) paragraph, unchanged in meaning, reworded for the new state).
- [x] Alerts as the decision record says: entering the wait is silent, a recovery tells the owner (`BOT_AUTO_RECOVERED`, reason `rate_limited`), a wait of 15 min tells it once (`BOT_RECOVERY_STALLED`, now truthful about a ladder that rests), the spent budget or a long ban lands `HALTED` and `BOT_HALTED` carries the words.
- [x] The exit re-check of D12 now covers this path: a stop loss or take profit crossed during the pause ends the bot as a Stop and no ladder is laid (the gap `042C`'s refusal table accepted for a limit met by an attempt is closed).
- [x] Futures keeps resuming from a pause as before ([`BUG-216`](../../../bug_report/completed/BUG-216_a_fill_burst_spends_the_request_weight_budget_and_the_exchanges_pause_halts_the_bot_as_a_switch_off.md)): its venue layer still clears every lower layer and now lists the pause alone (agent decision A2).
- [x] No change to order sizing, stop or close logic. The existing rate-limit tests are the oracle: the journeys are the same, only the state they assert changed (`HALTED` → `AWAITING_RECOVERY`) and the timer assertions became beats; none was weakened or deleted.
- [x] Positive proof in the log: the composed-app journey asserts the `[bot-halt-recovery]` lines `rate_limited is transient`, `recovery attempt 1 of 3`, `recovered from rate_limited`, through the real `App.Bots.GridExecutor` logger; `[bot-rate-limit-wait]` says the pause is waited for.

## 3. Design
Decision §2.1 and §2.3, and the row of the reason classification that said *Exchange pause: Yes, Grid kind layer, in `EPIC-042F`*. Three moving parts:

1. **The reason and its rule** (`bots/domain/halt_recovery_policy.py` → `RATE_LIMITED`, `PAUSE_RULE`; `bots/domain/grid/grid_kind.py` → `GRID_RECOVERY_LAYER`): the default budget (three per rolling 24 h per bot, counted with every other reason), the default stalled alert (15 min), and a dwell of `AUTO_RESUME_MARGIN` (2 s), the margin the retired timer added to the pause.
2. **The halt reaches the mechanism through one function** (`bots/application/kinds/grid/grid_order_failure.py` → `pause_with`), from both doors the retired class had: an order the venue's gate refused (`fail_with`) and a read or cancel that raised (`GridRateLimitPause.halt`). A bot that places or waits to goes to `AWAITING_RECOVERY` (the director's `halt_transient`), keeping its ladder (`GridTaskGuard._NOT_PARKED` still holds `RATE_LIMITED`: no cancel into a pause); a pause over `MAX_AUTO_RESUME_WAIT` is a plain halt (`BotRunState.halt(..., plain_because=...)`); a bot already waiting keeps its reason and rule.
3. **The probe** (`bots/application/kinds/grid/watch/grid_halt_probe.py` → `GridHaltProbe`, `GridRateLimitPause.holds`): `rate_limited` is *clear* when the pause the bot met has ended on its monotonic clock, and clear when it met none. `GridRateLimitPause.after_task` records when the pause ends (the gateway's noted pause, as before), and says so in the reason's detail. The run then does what `042C` built: every cause clear for the dwell, a saved attempt, a fresh price and the exit check, `propose`, `confirm` with `condition_cleared`.

## 3a. Reuse
`HaltRecoveryDirector`, `BotRunState.halt`, `GridHaltRecovery`, `GridHaltProbe`, `RecoveryLayer`/`RuleChange`, `GridResumeSequence`, `BotAutoRecoveredEvent`, `BotRecoveryStalledEvent`, `AUTO_RESUME_MARGIN` and `MAX_AUTO_RESUME_WAIT` (kept: the stop's retry and the long-pause limit use them). Not used: `IBotRetryScheduler` for the resume (the stop still uses it); the recovery run's beat replaces the timer.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/domain/halt_recovery_policy.py` | `RATE_LIMITED`, `PAUSE_DWELL`, `PAUSE_RULE` |
| `bots/domain/grid/rate_limit_pause.py` | `MAX_AUTO_RESUMES` and `resume_delay` removed; `too_long_to_wait_words`; `AUTO_RESUME_MARGIN` is `PAUSE_DWELL` |
| `bots/domain/grid/grid_kind.py`, `bots/contracts/venue_profile.py` | the Grid's layer declares the pause; Futures lists it after clearing the lower layers |
| `bots/application/kinds/grid/watch/grid_rate_limit_pause.py` | rewritten: no timer, no counter; `holds`, `halt`, `after_task` |
| `.../grid/watch/grid_halt_probe.py`, `.../grid/grid_executor.py` | the probe knows `rate_limited` and reads the pause; wiring |
| `.../grid/grid_order_failure.py`, `bots/application/services/lifecycle/bot_run_state.py` | `pause_with`; `halt(..., plain_because=)` |
| `.../grid/recovery/grid_halt_recovery.py` | a spent budget ends a wait even when the attempt raised; a reason with no rule keeps its detail |
| `alerting/application/sources/bot_alert_source.py` | the stalled alert does not claim a ladder off the exchange for a pause |
| `scripts/render_bots_design_tables.py`, `src/support/log_view/template_catalogue.json` | generated: the timing row, the policy table, the log catalogue |
| Module docs, vocabulary, `SPEC-014`, the runbook | Planned → Built |

## 5. Testing
Unit: the journeys of `test_grid_executor_rate_limit.py` (the oracle: halt for the pause, resume at its end, a stop that waits the pause out, the bounded recoveries, the long ban), the consequences in `test_grid_rate_limit_recovery.py` (exits re-checked, a feed's dwell not shortened, a Paused bot left to a person, the one budget), the probe, the policy and the declarations. Integration (composed app over the fake exchange): the Spot journey end to end, the Futures pause (`BUG-216`) and the neighbours test. Mutation checks, each red then restored: `holds` always false, the probe ignoring the pause, a bot already waiting losing its reason, the long-pause words, the budget re-check, Futures not clearing the lower layers.

## 6. Docs touched
`05-building-blocks.md`, `06-runtime.md` ("The exchange's pause"), `state-machines.md`, `10-quality.md` (generated tables and the sentence above them), `09-decisions.md`, bots `README.md`; `Docs/VOCABULARY/README.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/OPERATIONS/headless_runbook.md`, `Docs/LEARNING/001_layered_policy_and_lifecycle_state.md`.

## Agent decisions (the owner may veto; each reverts in one place)
- **A1 — a rate-limited bot waits in `AWAITING_RECOVERY`** (the pre-approved recommendation). A Spot owner no longer gets `BOT_HALTED` on every pause; they get `BOT_AUTO_RECOVERED` when it is over and `BOT_RECOVERY_STALLED` after 15 min. Veto: keep the timer for this reason only, which brings the second mechanism back.
- **A2 — Futures lists the pause.** Futures still clears every lower layer (D5); it now adds `rate_limited` alone, because a Futures bot has always resumed from a pause (`BUG-216`) and the rest of D5 says nothing about it. The lock "a Futures venue resolves no rule" became "a Futures venue resolves the pause and nothing a kind adds". Veto: delete the one `changes` entry, and a Futures bot stays `HALTED` through a pause.
- **A3 — the budget is the common one: three per rolling 24 h per bot, counted with every other reason.** The retired counter allowed five *consecutive* failed resumes and reset at `RUNNING`, so it never bounded a pause that kept recovering. The owner's rule is three a day per bot ([D1](../DECISION_2026-10-17_halt_auto_recovery.md)); a bot whose pause meets a fourth recovery in a day halts for a person. Veto: `max_attempts=5` in `PAUSE_RULE`, one number.
- **A4 — the dwell is the margin (2 s), the stalled alert the default (15 min).** The old resume ran at the pause plus 2 s; the run's beat is 5 s, so a bot attempts up to two beats after the pause ends. Veto: a larger or smaller dwell in `PAUSE_RULE`.
- **A5 — what the mechanism never recovers is left to a person and says so (D8 applied):** a `PAUSED` or `RECOVERING` bot that meets a limit is `HALTED` (the old timer resumed a Paused bot, undoing the owner's Pause), and so is a `HALTED` bot whose Resume met a limit (the person is told to resume again once the pause ends; the old timer finished the resume by itself). The latter is the one narrowing a person may notice, on the GUI and on `run --resume-halted`: it does not reach a bot that waits in `AWAITING_RECOVERY`, whose Resume and recovery attempt that meet a limit simply go on waiting. Veto: add a `HALTED` + `halt_transient` row to the lifecycle table.
- **A6 — a limit met by a bot already waiting for another reason keeps that reason and rule.** The pause joins the causes the run samples; it does not replace the reason, because the rule follows the reason and a 2 s dwell would shorten a quiet feed's 120 s.
- **A7 — the pause's end lives in memory.** A restart ends the wait in `HALTED` (D9), the pause is long over by then, and nothing is stored that would have to be migrated.

## Implementation notes (written when done)
- **Built as designed.** `RATE_LIMITED` is a reason of the Grid's layer; `GridRateLimitPause` keeps one fact (when the pause ends); the probe says *clear* when it has; the run, the budget, the exit check and the alerts are `042C`'s and `042D`'s, unchanged but for two small fixes below.
- **Two fixes the migration forced in `GridHaltRecovery.check`.** A limit raised inside an attempt (a read of the fresh price) never reached `_after`, and with the bot now still waiting that would have let the attempts run past the budget: `check` ends a wait whose budget is spent before it samples, with the same words. And a reason with no rule (a storage failure replaced the reason during the attempt) kept losing its detail when it halted: it now keeps it and appends the sentence.
- **Tests that changed state, with the reason in each docstring:** `test_grid_executor_rate_limit.py` (the oracle, `HALTED` → `AWAITING_RECOVERY`, the retry scheduler → the price watch's beats, `MAX_AUTO_RESUMES` → the common budget), `test_grid_storage_pause.py` (the storage gate meets the recovery attempt, not the timer), `test_grid_executor_awaiting_recovery.py` and `test_grid_halt_recovery_refusals_and_budget.py` (a limit met in the wait keeps the bot waiting, no longer `HALTED`), the Futures `BUG-216` journey and the neighbours journey (`AWAITING_RECOVERY`, no resume timer), and the layer, policy and `bot show` tests (the Grid's pause row; Futures lists it).
- **Mutation checks:** six, each red then restored (see §5).
- **Verified:** `ci-local.ps1 -SkipTests` (the commit tier) and the touched and neighbouring unit and integration tests pass locally; the full gate is GitHub Actions' `ci-local.ps1 -Full` run on the pull request's head, read from its job logs (recorded on the pull request).
- **Not covered:** the owner's Testnet run (no real exchange pause is provoked on demand; the fake exchange's 429 with `Retry-After` is the proof); a pause longer than the 15 min stalled alert is told once and the bot goes on waiting.
