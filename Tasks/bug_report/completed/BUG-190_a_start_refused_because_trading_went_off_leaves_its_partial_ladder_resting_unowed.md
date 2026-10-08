# BUG-190 — A start refused because trading went off leaves its partial ladder resting, and nothing owes its cancel

- **Reported:** 2026-10-08 (the coordinator session's Phase 1 leftovers; recorded as a known residual of `EPIC-035C`)
- **Severity:** 🟡 P2 — the partial ladder of a plan that never completed keeps trading unmanaged after trading is enabled again, until the user presses Resume or Stop. Cancels cannot be made while the session is closed, so nothing is wrongly sent.
- **Status:** ✅ Fixed (2026-10-08)
- **Board:** A start (or confirmed resume) refused because trading went off ended HALTED `switch_off` with part of its ladder resting, and enabling trading never cancelled it. Cause: `fail_with` wrote the plain `SWITCH_OFF` reason, which `GridTaskGuard` skips (D13) and no later step pays. Fix: while STARTING it writes `START_CUT_BY_SWITCH_OFF`, a debt `GridInterruptedStart` pays at the next enable, as `EPIC-035C` does for a restart; a finished ladder still rests (D13).
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → bots (`src/modules/bots/`) → `application/services/grid_order_failure.py`, `grid_interrupted_start.py`
- **Environment:** Linux container; `master-warrior` `be67b47`; unit tier, simulated venue. Not seen on an exchange.

## Reproduction
1. A Start whose submit is refused with `TRADING_SWITCH_OFF` after two opening slices and one ladder order (`test_grid_start_cut_by_switch_off.py::_start_cut_by_the_switch`); or a confirmed resume refused the same way.
2. Trading is enabled again.

Expected: the partial ladder is cancelled at the enable (the cancel was impossible before), as for a start the app's restart cut short. Actual: the bot stays HALTED `switch_off` and the orders rest until Resume or Stop.

## Symptom
HALTED, reason `switch_off`, one tagged order resting, no step owing its cancel.

## Root cause
D13 (`EPIC-029` ADR) lets a switch-off halt leave the ladder resting because the session refuses cancels: `GridTaskGuard._orders_may_rest` skips reason `SWITCH_OFF`. That is sound for a RUNNING bot, whose ladder is a valid grid the owner chose to freeze. For a start it is not: `fail_with` (`grid_order_failure.py`) wrote the same `SWITCH_OFF` for a STARTING bot, whose partial ladder belongs to a plan that never completed and which only Resume (cancel first, then re-plan) or Stop can follow. `EPIC-035C` paid that kind of debt for a restart (`START_INTERRUPTED`, `GridInterruptedStart`) but wrote it on no other path (`EPIC-035C` known residual 1).

D13 stays as it is for RUNNING and PAUSED bots. Deciding against it would also have to cover their whole ladders, which a deliberate switch-off freezes on purpose.

## Fix
`GridReason.START_CUT_BY_SWITCH_OFF` (domain). `fail_with` writes it, with the cancel debt in the detail, for a SWITCH_OFF outcome while STARTING (start and confirmed resume share the path). `GridTaskGuard` does not park under it (a cancel would be refused). `GridInterruptedStart` owes and pays under either reason; only the lead of its sentences differs (`_LEAD`). `BotBootRecovery` pays it at boot for a restored bot too.

## Regression test
`tests/unit/modules/bots/application/services/test_grid_start_cut_by_switch_off.py`: `test_a_start_cut_by_the_switch_writes_the_debt_on_the_bot`, `test_enabling_trading_cancels_the_partial_ladder_of_a_cut_start`, `test_a_cancel_refused_by_the_closed_session_waits_for_the_enable`, `test_a_confirmed_resume_cut_by_the_switch_owes_the_cancel_too` (red before: reason `SWITCH_OFF`, ladder still resting after the enable); D13 is pinned for a finished ladder by `test_a_running_bots_whole_ladder_still_rests_after_the_enable` and `test_a_counter_order_refused_by_the_switch_leaves_a_running_ladder_alone`. `test_grid_executor_start.py` now expects the new reason for the two switch-off starts.

## Verification
Red before on `be67b47`, green after; the bots unit and integration tiers and the commit tier pass. Positive proof the mechanism ran: the enable test sees the book emptied and `START_INTERRUPTED_CLEARED` with "trading went off while this bot was starting".
