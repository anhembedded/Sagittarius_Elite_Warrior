# EPIC-035G — A failed store write still parks the ladder

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M2 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — memory says ERROR while the disk disagrees and the ladder stays live
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035C

---

## 1. Context and problem
**Claim (audit M2), verified ✅ on `be67b47`, with one correction to the citation.** `BotRunState.transition` and `update` change memory first and then call `_save` (`bot_run_state.py`, the whole file is 120 lines: the cited `:200-220` does not exist; the mechanism is `transition`/`update` → `_save`). `GridTaskGuard.run` catches a task's exception and calls `fault_with` inside the `except` block; `fault_with` saves again, the second `OSError` leaves `run`, and the `_park` call below it never runs. Reproduced before the change: with the store failing, a counter-order fault ended with the traceback through `grid_task_guard.py` `run` and the ladder still resting.

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [x] A store write failure (disk full, permissions) never skips parking: `BotRunState._save` keeps an `OSError` as `storage_failure` instead of raising it, so the fault handler and the park both run. Evidence: `test_a_failed_save_does_not_skip_parking`, red before, green after.
- [x] A distinct storage-failure fact is raised and shown; it does not masquerade as the original fault: a parked bot's reason keeps the fault that happened and its detail gains `its state could not be saved (OSError: …)` once; the ERROR log line carries `[bot-store-failed]`. Evidence: `test_a_storage_failure_is_named_beside_the_fault_not_instead_of_it`. Shown where: the bots screen's state line renders `reason_detail`, but it renders what the store holds, so the note reaches the screen with the next successful write; until then it is the log line.
- [x] On the next successful write the true state is persisted: every write is the whole record. Evidence: `test_the_next_successful_write_persists_the_true_state` (the file said RUNNING while memory said ERROR; the next write made it ERROR).

## 3. Design
Same family as `EPIC-035C`'s H4: parking is a safety effect and must not depend on persistence succeeding.

Chosen: convert at the one writer, not at each caller (`fix-bug-rule.md` §1). `BotRunState` is the only place a running bot saves, so catching `OSError` there covers the fault handler, the park's per-order updates and every later write. Only `OSError` is converted: a `TypeError` from encoding is a defect and still raises. The rejected alternative, parking *before* recording the fault, fixes the one call site and leaves `cancel_tagged`'s own `state.update` per cancelled order to raise half-way through the park.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/bot_run_state.py` | as the criteria require |
| `src/modules/bots/application/services/grid_task_guard.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Unit tier, in `tests/unit/modules/bots/application/services/test_grid_storage_failure.py`, against the real executor through the real factory and a store that fails on demand (`FakeBotStore.fail_saves`, verified in `test_bot_store_contract.py`):
- `test_a_failed_save_does_not_skip_parking` — red before: `OSError` left `GridTaskGuard.run`, the book kept its orders.
- `test_a_storage_failure_is_named_beside_the_fault_not_instead_of_it` — red before, same cause.
- `test_the_next_successful_write_persists_the_true_state` — red before, same cause.

Green after: the three, the whole `tests/unit/modules/bots` (1314 tests) and `tests/unit/architecture`; the commit tier PASS.

## Implementation notes
- `bot_run_state.py`: `_save` converts `OSError` to `storage_failure` (+ `[bot-store-failed]` ERROR, `[bot-store-recovered]` WARNING on the next success); `GridTaskGuard` appends the note once to a parked bot's detail.
- **Amended by owner decision D6 (2026-10-08, [decision file](../DECISION_2026-10-08_spot_grid_audit_owner_decisions.md)).** This task first shipped "a bot that is not parked keeps trading on memory" as an accepted price, locked by `test_a_running_bot_on_a_failing_disk_goes_on_and_the_next_write_catches_up`. The owner overrode it: after 3 consecutive failed saves a RUNNING bot goes to PAUSED with `STORAGE_FAILURE` (orders rest, nothing new placed, counter orders held); Resume works once a save succeeds and is refused while the store still fails; a successful save resets the count. The lock test was **replaced on purpose**, not weakened, by `test_grid_storage_pause.py` (four required cases plus the reset and the held-ladder cases). Mechanism: `BotRunState.failed_saves` / `save_works()`, `GridStorageWatch` (called by `GridTaskGuard` after each task, and by `GridExecutor._run_resume` before a resume from PAUSED). SPEC-014 §6 and its behaviour table are updated.
- **D6 visibility rider (owner, same day): nothing fails silently.** `BotRunState._save` logs every failed save on `App.Bots.GridExecutor` (the tree the bot's log tab and Output pane show through `BotLogFeed`): WARNING `state save failed (1/3) … retrying`, `(2/3)`, ERROR from the third; the pause is an ERROR and its reason detail tells the user to check the disk and press Resume; a save that works after failures logs INFO `state save recovered after N failure(s)`. Evidence: `test_each_failed_save_is_a_line_the_user_can_read`, `test_the_pause_notice_is_the_bots_reason_on_screen`, `test_a_refused_resume_is_a_line_too`. Limits stated plainly: the state line reads the file, so the pause notice reaches it only once a write lands (the log tab is live meanwhile); no new UI event was added because the log feed already is the live path. **Follow-up:** the Discord alert on the pause waits for `EPIC-035K` (not on master).

## Resume
Done. Nothing owed.
