# EPIC-035C — No unmanaged orders and no stuck states

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, findings H4, H5 and H6 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 1 approved the same day (D1).
**Risk:** 🔴 — each case leaves real orders resting under a bot that does not manage them, or a bot that cannot be stopped
**Complexity:** L — a guard rule, an FSM edge with a retry timer, a boot-time read-only reconcile and a user-visible report, and a restart cleanup
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), extended by this task
**Depends on:** None

---

## 1. Context and problem
**H4 — a refused confirm-resume leaves a partial ladder resting. Verified ✅ on `3bbe243`.**
- `src/modules/bots/application/services/grid_task_guard.py:54-73`: `GridTaskGuard.run` records `before = state.state` ahead of the task and parks (`cancel_tagged`) only when `_stopped_placing_since(before)` is true, which requires `before not in _PARKED`.
- `confirm_resume` runs `GridResumeSequence.confirm` (`src/modules/bots/application/services/grid_resume_sequence.py:111-114`): `transition(RESUME)` (HALTED → STARTING) and `place_ladder`. A refusal part-way goes STARTING → HALTED (`bot_lifecycle_fsm_matrix.py:101`, `START_REFUSED`). The guard sees `before = HALTED`, `after = HALTED`, so it does not park and the already-placed part of the ladder keeps resting.

**H5 — a bot can stick in STOPPING. Verified ✅, with one refinement.**
- `src/modules/bots/domain/bot_lifecycle_fsm_matrix.py:134-138`: STOPPING has `STOP_CONFIRMED`, `SWITCH_OFF`, `FAULT`, `HALT`, `APP_RESTART` and **no `STOP` edge**. So `can(STOP)` is false in STOPPING and the screen's Stop action, which maps to `BotLifecycleEvent.STOP` (`src/modules/bots/ui/bots_screen/bot_action_rules.py:41`), is not offered.
- **Refinement of the audit:** the executor already tolerates a second stop. `GridExecutor._run_stop` (`grid_executor.py:244-252`) takes the `elif state.state is not _S.STOPPING` branch and re-runs `_stop.run(...)`, and `_apply_switch` re-runs it on switch-on (`:324-327`). What is missing is the **edge** (so the user can ask) and an **automatic bounded retry** (so nobody has to): today the only retry trigger is a trading-session closed→open event.

**H6 — after a restart the ladder trades unattended, and a restart in STARTING leaves orders. Verified ✅ on both halves.**
- A restored RUNNING or PAUSED bot becomes RECOVERING (`Bot.restored`, `src/modules/bots/domain/bot.py:140-142`, `APP_RESTART`). The reconciler runs for RECOVERING only from `GridExecutor._apply_switch` when trading is switched on (`grid_executor.py:315-323`). Until the session opens, resting orders fill with no counter orders.
- A bot restored from STARTING goes to HALTED (`bot_lifecycle_fsm_matrix.py:105`). Nothing on that path calls `cancel_tagged` (its callers are `grid_stop_sequence.py:80,93`, `grid_resume_sequence.py:88` and the guard, `grid_task_guard.py:77`), so tagged orders from the interrupted start remain on the book. **Note on the audit's citation:** the audit cites `grid_executor.py:315-327` for this half; that range is the switch-on handler, which confirms the RECOVERING half. The STARTING half is the matrix edge plus the absence of any cancel on restore, as above.

## 2. Acceptance criteria
- [x] **H4:** whenever a placing task (start, resume-confirm, a fill's counter order, a re-place) ends with the bot in HALTED or ERROR **and orders may rest**, the guard parks the ladder, regardless of the state it began in. A confirm-resume refused part-way ends with no tagged order resting, and the report names what was cancelled (existing `CancelReport`).
- [x] The park is not repeated forever: a HALTED bot that is already parked (no tagged orders) does not re-cancel on every task; the rule is "parks when the task placed or may have placed", not "parks on every task in HALTED".
- [x] **H5:** STOPPING gains a `(STOPPING, STOP)` edge (self-loop, a retry) in the FSM matrix, and the Stop action is available in STOPPING. The executor retries a stop that waited on a refused cancel automatically, on a bounded schedule (named interval and maximum), without needing a session event; each attempt's reason and the remaining open order count are visible on the bot (the stop sequence already names them).
- [x] After the retries are exhausted the bot stays STOPPING with a named reason that tells the user the next action, and the failure is a user-visible alert once `EPIC-035K` exists (until then, a log record at ERROR with the bot id).
- [x] **H6, boot reconcile:** at app boot, once the credentials resolve and without waiting for the trading switch or a session open, every restored RUNNING / PAUSED bot runs a **read-only reconcile**: it reads the exchange's open orders and the order history by client order id and reports to the user, in the Bots mode, what it found (resting, filled while closed, missing). Read-only means it places and cancels nothing on its own; placing missing counter orders still waits for the session (existing behaviour), now with the user told, and with the interplay with `EPIC-035B`'s gap reconcile defined (they share the missed-fill read).
- [x] **H6, STARTING at restart:** a bot restored from STARTING cancels its tagged orders (the interrupted start's partial ladder) when its symbol lease is reclaimed or the credentials resolve, whichever first, and ends HALTED with the cancel report as its detail. If the cancel is refused, the bot says so and does not claim a clean halt.
- [x] Every one of the three cases has a regression test that is **red on `3bbe243`'s behaviour** (§5).

## 3. Design
- **H4 — mechanism, not call site.** The defect is that "parked" is inferred from a *transition*, not from the *fact* "orders may rest under a bot that no longer manages them". Move the decision into one predicate on the guard: after any task, if `state in _PARKED` and the task was one that could place (a flag on the task or on the executor's runtime, set by `place_ladder` and the counter/re-place paths, cleared by a clean park), park. The `SWITCH_OFF` exemption stays (trading off means the session cannot cancel). This closes the whole family (resume-confirm, the same shape in start-from-HALTED), not only the reported call site (`fix-bug-rule.md` §1–§2). A scan for other paths that end HALTED→HALTED is part of the task and its result is recorded.
- **H5 — retry by edge and timer.** Add the self-loop edge so `can(STOP)` holds in STOPPING (one table, one change); add an executor-owned retry task on a bounded backoff using the injected clock (the same timer service as `EPIC-035A` / `035B`). The edge makes the manual retry honest; the timer makes it unnecessary in the common case. Do not weaken the invariant "never STOPPED early": STOPPED still requires zero open tagged orders (`grid_stop_sequence.py`).
- **H6 — boot reconcile in two parts.** (1) *Read-only report:* a reconciler mode that returns a `RecoveryReport` (per-bot: resting, filled-while-closed, missing, foreign) and does no write; the bots presenter shows it on the bot (a visible line with the reason and the count, not a log line only, per the HLD's "every reason shown"). It runs when credentials resolve, independent of the trading switch, because a read needs no order session. (2) *STARTING cleanup:* on restore, a bot whose pre-restart state was STARTING gets a one-shot "cancel tagged" through the existing `GridHousekeeping.cancel_tagged`, under the guard.
- **Layering:** the guard, executor and reconciler stay in `application/services`; the FSM edge in `domain`; the report is a contracts value object shown by the UI through the existing presenter seam. No UI code calls the reconciler.
- **Related, not duplicated:** `EPIC-035B` reconciles after a *reconnect*; this task reconciles at *boot* and reports. Both reuse one missed-fill read. `EPIC-035G` (a failed store write skips parking) is the same family at a different seam and depends on this task's predicate.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/grid_task_guard.py` | Park on "ended parked-state after a placing task", not on a state change |
| `src/modules/bots/application/services/grid_resume_sequence.py`, `grid_start_sequence` (as named in the tree) | Mark the placing tasks |
| `src/modules/bots/domain/bot_lifecycle_fsm_matrix.py` | `(STOPPING, STOP): STOPPING` |
| `src/modules/bots/ui/bots_screen/bot_action_rules.py` | Stop is offered in STOPPING (follows the matrix) |
| `src/modules/bots/application/services/grid_executor.py`, `grid_stop_sequence.py` | Bounded automatic stop retry; reason and remaining orders visible |
| `src/modules/bots/application/services/grid_reconciler.py`, `bot_restore_service.py` (as named in the tree) | Read-only boot reconcile and `RecoveryReport`; STARTING cleanup |
| `src/modules/bots/ui/bots_screen/` | Show the recovery report and the STOPPING reason |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | The journeys "refused resume", "a stuck stop", "restart" |
| `tests/unit/modules/bots/**`, `tests/integration/modules/**` | The tests named in §5 |

## 5. Testing
| Criterion | Test | Tier | Expected |
| :--- | :--- | :--- | :--- |
| H4 | `tests/unit/modules/bots/application/services/test_grid_task_guard.py` (new) `::test_a_confirm_resume_refused_part_way_parks_the_partial_ladder` — **red before:** HALTED→HALTED does not park, the placed orders stay | Unit, with the real guard and a gateway that refuses the Nth order | No tagged order remains; the report names the cancelled ones |
| H4, no loop | `test_a_parked_bot_is_not_cancelled_again_by_every_task` | Unit | `cancel_tagged` called once |
| H4, family | `test_every_task_that_places_is_parked_when_it_ends_halted_or_error` (parametrised over start, resume-confirm, counter order, re-place) | Unit | Parked in all |
| H5, edge | `tests/unit/modules/bots/domain/test_bot_lifecycle_fsm_matrix.py::test_stop_is_declared_in_stopping` — **red before:** no edge | Unit | `can(STOP)` true |
| H5, retry | `test_a_stop_that_waited_on_a_refused_cancel_retries_without_a_session_event` — **red before:** nothing retries | Unit with a fake clock and a gateway that refuses twice then accepts | STOPPED after the third attempt; reason and remaining count shown between |
| H5, safety | `test_stopped_still_requires_zero_open_tagged_orders` | Unit | Never STOPPED early |
| H5, exhausted | `test_exhausted_retries_leave_the_bot_stopping_with_a_named_reason` | Unit | Reason set, ERROR log record |
| H6, boot | `test_a_restored_running_bot_reports_what_the_exchange_holds_before_the_session_opens` — **red before:** nothing runs until the switch | Unit and integration | A `RecoveryReport` with the three counts; nothing placed or cancelled |
| H6, report shown | `tests/unit/modules/bots/ui/test_recovery_report_is_visible.py` | Unit | The line is in the bot's facts |
| H6, STARTING | `test_a_bot_restored_from_starting_cancels_its_tagged_orders` — **red before:** HALTED with orders resting | Unit and integration with the fake Binance server | No tagged order; the detail has the cancel report; a refused cancel is said, not hidden |
| Architecture | `pytest tests/unit/architecture -q` | Guards | Green |

Each "red before" test was shown red at `3bbe243`'s behaviour first; see the implementation notes.

## Implementation notes (written when done)

**Evidence.** Red at `546b8a3` (the code before any change), then green:
- H4: `test_a_confirm_resume_refused_part_way_parks_the_partial_ladder` and `test_every_task_that_places_is_parked_when_it_ends_halted_or_error[resume-confirm]` failed with 2 placed orders still on the book; the other three family members (start, counter order, re-place) already parked and stay as regression coverage.
- H5: `test_stop_is_declared_in_stopping`, `test_the_matrix_declares_exactly_the_adr_table` and `test_exactly_the_legal_actions_are_live[STOPPING]` failed (no edge, Stop not offered); the retry tests failed at collection (no scheduler existed to retry with).
- H6: the restart-then-enable scenario written against the old API failed with the whole ladder still resting (`book.open` non-empty under a HALTED bot); the boot-report and cleanup tests failed at collection (no boot step existed).
- Wiring: `test_boot_has_a_restored_bot_report_what_the_exchange_holds` and `test_boot_has_a_bot_whose_start_was_cut_short_pay_its_cancel` both fail with the `BotBootRecovery` line removed from `BotsModule.boot()` (measured).

**H4 — the mechanism.** `GridTaskGuard` now parks when the bot **fell into** HALTED/ERROR during the task, *or* the task **sent orders** and ended there (other than a switch-off). "Sent orders" is `BotOrderGateway.submissions`, which counts every request including one that raised (it may have reached the exchange). This is stateless: no flag to set on each placing path, so a new placing path is covered without being remembered. A parked bot whose task sent nothing is left alone (a test counts the open-order reads). *Scan for other HALTED→HALTED paths:* the only one is `confirm_resume` (HALTED → STARTING → HALTED); `propose` cancels but places nothing; fills and ends in HALTED are held or dropped, never placed; a stop's `halt_with(EXIT_SLICE_FAILED)` starts in STOPPING, already covered.

**H5 — edge and timer.** `(STOPPING, STOP): STOPPING`, so the screen offers Stop in STOPPING. Retry policy is `STOP_RETRY_DELAYS` (10 s, 30 s, 60 s, 2 min, 5 min) in `grid_stop_retry.py`, driven through a new port `IBotRetryScheduler` (real: `TimerBotRetryScheduler`; verified fake: `FakeBotRetryScheduler`, both under one contract suite). This task could not wait for the timer service `035A`/`035B` are building, so it brings the smallest seam of its own: **when they land, their timer should replace this adapter behind the same port, not sit beside it**. `GridStopSequence.run` now returns a `StopProgress` so the retry knows whether it waits on the exchange (retried), on the order session (not retried — the switch-on event does it) or ended. A stop asked again starts a fresh round and a retry scheduled by an earlier round does nothing; in STOPPING the reason the stop began with is kept. Exhaustion is an ERROR log record with the bot id plus the reason "the automatic retries are used up; press Stop to try again"; the alert channel is `EPIC-035K`'s. `GridExecutor` was at its 400-line ceiling after the change, so the stop command moved to `grid_stopper.py`.

**H6 — report and cleanup.** The boot report is stored as the bot's reason (`GridReason.RECOVERY_READ`) so it reaches the screen through the existing `bot_progress` → `bot_facts` line, with no new UI code; the full reconcile replaces it on `reconcile_ok`. Read failures (history unavailable, any exception) become an "unreadable" report, never a fault. A bot restored from STARTING is saved with `START_INTERRUPTED` on its own record, so a second crash cannot lose the debt; `BotBootRecovery` pays it at boot and the switch-on pays it again until done (`START_INTERRUPTED_CLEARED`).

**Deviations from the task text, for the owner.**
1. *"Once the credentials resolve."* There is no credentials-resolved event in the tree. The boot step runs on each bot's own worker and reports what it could read; a failed read is said on the bot. The order session is closed at boot and the exchange refuses cancels then, so the STARTING cleanup normally *waits* ("N tagged order(s) still rest and are cancelled when trading is enabled") and is paid at the switch-on — which is also when the lease is reclaimed, so the "whichever first" of the task collapses to the switch-on in practice. The user is told in both cases.
2. *Shared missed-fill read with `035B`.* `GridRecoveryReader` counts what `GridReconciler._apply_missed_fills` books; the two reads were left separate to avoid editing the reconciler's read while `035B` works in that area. Merge point: one read both call.
3. *`RecoveryReport` is a domain value*, not a contracts type, because the UI reads only its sentence through the existing progress seam.
4. A malformed bot config (found by the module wiring test) could have stopped boot when its executor was built; `BotBootRecovery` isolates each bot and logs.

**Verification.** Commit tier (`ci-local.ps1 -SkipTests`) PASS; `tests/unit/architecture` green; `tests/unit/modules/bots` and `tests/integration/modules/bots` green. The `-Full` gate is GitHub Actions' (see the pull request).
