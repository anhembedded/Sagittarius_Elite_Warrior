Status: Current

# `bots` — 6. Runtime

*What happens, step by step, on the journeys that matter?* Each journey has its own picture, drawn by
hand; the steps below cite the code that runs them. The states named are the lifecycle's
([`state-machines.md`](state-machines.md)). Design: ADR 029 §3.3 and §3.4, design 038 §5, design 039
§9 ([`09-decisions.md`](09-decisions.md)).

## Built: Start

[`diagrams/06-start.puml`](diagrams/06-start.puml) — *what happens, in order, when the owner starts a
Grid bot, and on which thread?*

The use case (`bots/application/use_cases/start_bot/handler.py` → `StartBotCommandHandler.execute`)
refuses a closed venue, an unconfirmed Mainnet start and an unready bot, then asks the runner to
start (`.../bot_runner.py` → `BotRunner.start`). The runner works **on the caller's thread**: it
retires the earlier run's worker, so no task of that run can save over the new one, applies `start`
(`STARTING`, not yet saved), and asks the Grid's preconditions (`.../grid_start_preconditions.py` →
`GridStartPreconditions.check`) to re-read the parameters, claim the symbol, open the order session
(`.../order_session_opening.py` → `order_session_refusal`) and register the owner budget. A refusal
goes back to the caller with nothing saved and nothing queued. Only once they pass does the runner
save the bot `STARTING` and queue `start` on a fresh worker. On the worker the executor plans and
places the ladder (`.../grid_executor.py` → `GridExecutor._run_start`; `.../grid_start_sequence.py` →
`GridStartSequence.run`), and `ladder_ready` moves the bot to `RUNNING`. The order-session opening and
the budget registration are calls to `trading` the caller waits on.

## Built: a fill

[`diagrams/06-fill.puml`](diagrams/06-fill.puml) — *what happens when one of a bot's orders fills?*

The router (`.../bot_event_router.py` → `BotEventRouter.on_fill`) gives the fill to `GridFacts`,
which ignores one already counted and books the rest on the bot's worker (`.../grid_facts.py` →
`GridFacts.on_fill`, `GridFacts._apply_fill`). A filled level lays its counter order one level away
and returns to `EMPTY` (`settled`, the level machine in [`state-machines.md`](state-machines.md)), and
the bot's run state saves the new runtime.

## Built: Stop

[`diagrams/06-stop.puml`](diagrams/06-stop.puml) — *what does the owner's Stop do, and when is a bot
really STOPPED?*

The use case (`.../stop_bot/handler.py` → `StopBotCommandHandler.execute`) goes through
`GridStopper` (`.../grid_stopper.py` → `GridStopper.run`), which moves the bot to `STOPPING`, to
`GridStopSequence` (`.../grid_stop_sequence.py` → `GridStopSequence.run`): it registers the budget
again, cancels every order carrying the bot's tag, keeps or closes the exposure (the owner's choice;
a stop loss or take profit forces *close*), and reads the open orders again. Only zero tagged orders
raise `stop_confirmed`; anything else leaves the bot `STOPPING`, saying why, never reported stopped
early. The automatic retries wait on `STOP_RETRY_DELAYS` ([`10-quality.md`](10-quality.md)); when
they are used up the bot publishes `BotStopGaveUpEvent` (`.../grid_stop_retry.py` →
`GridStopRetry._exhausted`), which `alerting` carries to the owner.

## Built: Emergency Stop

[`diagrams/06-emergency-stop.puml`](diagrams/06-emergency-stop.puml) — *what does an Emergency Stop on
the trading desk do to a running bot?*

The stop is `trading`'s (`src/modules/trading/application/session/emergency_stop/handler.py` →
`EmergencyStopCommandHandler`): it disables trading on the venue, publishes
`TradingSwitchChangedEvent` with the cause `EMERGENCY_STOP` before any order is read (ADR 029 D7, so a
bot learns of it before its cancels reach it), cancels every open order and closes every position (on
Spot, sells what was bought above the session's baseline). The router hands the switch to every bot on
the venue (`.../bot_event_router.py` → `BotEventRouter.on_switch`), and a bot that is `STARTING`,
`RUNNING` or `PAUSED` goes `switch_off` → `HALTED`, its reason naming the Emergency Stop
(`.../grid_facts.py` → `GridFacts._apply_switch`). A `STOPPING` bot waits in `STOPPING` and runs its
stop again when trading is enabled (`GridStopper.after_switch_on`). An order a bot sends while the
session is closed is refused, and the bot halts rather than faults (`.../bot_order_gateway.py` →
`BotOrderGateway`).

## Built: restart

[`diagrams/06-restart.puml`](diagrams/06-restart.puml) — *what happens to a running bot when the app
restarts?*

`BotRestoreService` (`.../bot_restore_service.py` → `BotRestoreService.restore_all`) applies
`app_restart` to every saved bot: `RUNNING` and `PAUSED` become `RECOVERING`, `STARTING` becomes
`HALTED`, and nothing is placed. `BotBootRecovery` (`.../bot_boot_recovery.py` →
`BotBootRecovery.run`) has every `RECOVERING` bot report what the exchange holds, read only, and pays
the cancels a cut-short start left owing. The full reconcile (`.../grid_reconciler.py` →
`GridReconciler.run`) runs only once the venue's order session is open: until then nothing listens to
the exchange and the Orders panel shows the ladder as saved, with a note saying so.

The reconcile brings each saved order's quantity level with the exchange's **before** it applies any
missed fill (`recovery/grid_order_quantities.py` → `adopt_exchange_quantities`; `BUG-205`): from the
open-order list, or from history for an order that is gone. A smaller quantity is adopted and logged
`[order-quantity]`; a larger one halts the bot (`order_quantity_mismatch`). A new order is saved at the
quantity the exchange accepted, never the one asked for.

## Built: Resume from `RECOVERING`

[`diagrams/06-resume-recovering.puml`](diagrams/06-resume-recovering.puml) — *how does the owner's
Resume bring a `RECOVERING` bot back, or halt it?*

`BUG-204`, the desktop's way out: the use case (`.../resume_bot/handler.py` →
`ResumeBotCommandHandler`) asks for the real-money
answer on a mainnet venue, `BotRunner.resume` (`.../bot_runner.py` → `BotRunner.resume`) opens the
session (`.../grid_start_preconditions.py` → `GridStartPreconditions.open_session_for_resume`) or
refuses in the session's words, and the executor reconciles (`.../grid_executor.py` →
`GridExecutor._run_resume`; `.../grid_facts.py` → `GridFacts.reconcile_recovering`): a fill the bot
missed is booked once from the order history, its counter order laid, an order missing from the book
ended, and the bot returns to its prior state, or halts on a mismatch. The prior state is data on the
screen's side: `Bot.lifecycle.recovering_from` travels on `BotSnapshot.recovering_from`, so the state
line of a `RECOVERING` bot says where the reconcile returns it (`bot_facts.py`, `BUG-206`). A bot the
owner had paused returns to `PAUSED` with the reason `restored_paused` (`GridReconciler.run`), which
the state line shows until the next Resume clears it, so the second press is explained on screen and
not only in the `[recovering-resume]` log line.

A deliberate action that trades opens the order session in one place (`.../order_session_opening.py` →
`order_session_refusal`, `order_session_refusal_words`), with exactly three callers: Start, a Resume
from `HALTED` or `RECOVERING`, and the headless `run --resume-recovering`
(`.../grid_start_preconditions.py` → `GridStartPreconditions.check`,
`GridStartPreconditions.open_session_for_resume`; `.../resume_recovering_for_host/handler.py` →
`ResumeRecoveringForHostCommandHandler._open`). Nothing automatic opens it: a late order must not undo
an Emergency Stop.

## Planned: EPIC-039L, the exchange-side protective stop

The journey in which a Futures Grid places a protective stop on the exchange after its opening fill,
cancels it only once the position is flat, and adopts or replaces it on a restart is designed by
[`EPIC-039L`](../../../Tasks/epics/EPIC-039_futures_venue_profile/incomplete/EPIC-039L_protective_stop_mainnet_gate_and_soak.md)
and written here by that task. Nothing in this folder designs it yet; the task's acceptance criteria
and [design 039 §8](../../../Tasks/epics/EPIC-039_futures_venue_profile/DESIGN_2026-10-10_futures_venue_profile.md)
are the current source.
