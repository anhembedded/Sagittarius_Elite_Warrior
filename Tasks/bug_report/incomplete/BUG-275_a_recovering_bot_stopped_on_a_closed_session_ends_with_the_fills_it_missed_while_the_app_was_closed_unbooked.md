# BUG-275 — A RECOVERING bot that reaches STOPPING without a reconcile ends its run with the fills it missed while the app was closed unbooked

- **Reported:** 2026-10-27 (round 3 of the independent review of PR #742, session `session_01TcvhNHdtrDX93usRggjNsB`; the author traced the same gap)
- **Severity:** 🟡 P2 — no order is placed wrongly and the close still covers the exchange-derived position, but the stopped run's `realised_total` and earnings can be wrong (the probe of `BUG-274` read +363.25 USDT for a run that lost 14.83)
- **Status:** Open
- **Board:** A RECOVERING bot stopped while the order session is closed (the loss cap's or the shutdown policy's Stop, or a declined real-money question) moves to STOPPING without the reconcile that books the fills which landed while the app was closed; neither a later Stop nor the switch-on books them, so the run's record is short. Not yet reproduced; the main path was fixed in `BUG-274`.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (restart and recovery; Stop) → `src/modules/bots/` → `application/kinds/grid/` (`grid_executor.py`, `grid_facts.py`, `stop/`, `recovery/grid_reconciler.py`)
- **Environment:** Master at the head of PR #742 (`b589130`). Reproduction not run.

## Reproduction
Not yet reproduced; this is a code trace (`grid_executor.py` → `GridExecutor._run_stop`, `grid_facts.py` → `GridFacts.book_missed_fills`, `GridFacts._apply_switch`, STOPPING branch, at `b589130`).
1. A bot is RECOVERING after a restart with the venue's order session closed, and a ladder order filled while the app was closed.
2. A Stop that carries no person's answer arrives (`LossCapStopper`, the shutdown policy), or the person declines the real-money question. `book_missed_fills` runs, but the reconcile's budget registration is refused (session closed), so it books nothing; the stop moves the bot to STOPPING.
3. The bot is STOPPING. The person presses Stop (the new wait text says to), or any action opens the session. `_run_stop` finds the state STOPPING, not RECOVERING, and `after_switch_on` never reconciles.
Expected: the stopped run's record includes the fill. Actual (from the trace): the close is measured against a cost that lacks it and books its proceeds as profit.

## Symptom
The `BUG-274` probe on the person's-Stop path, before `book_missed_fills`: `realised_total` +363.25 where the reconcile-first path reads −14.83 (0.006 bought while down, price below every entry).

## Root cause
Not yet established beyond the trace above. The only record that a bot came from RECOVERING is `BotLifecycle.recovering_from` (`src/modules/bots/domain/bot.py`), and it is cleared on any transition out of RECOVERING, so STOPPING cannot tell that the booking is still owed.

## Suggested next steps
Choose one trigger that every entry into the stop shares (`_run_stop`, `after_switch_on`, a retry): (a) book in `GridStopSequence` once the budget registration succeeds, when the exchange-derived inventory differs from the runtime's; (b) keep a marker on the runtime that survives the move to STOPPING. (a) adds one comparison to every stop and uses `GridReconciler.compare_with_exchange`, which is idempotent through `AppliedFills`; (b) adds a persisted field. Write the journey first: automated `StopBotCommand` on the closed session, then the screen's Stop, then `realised_total < 0` (red).
