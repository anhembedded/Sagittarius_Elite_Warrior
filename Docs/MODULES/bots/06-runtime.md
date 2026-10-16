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

[`diagrams/06-protective-stop.puml`](diagrams/06-protective-stop.puml) — *how does a Futures Grid keep
an exchange-side stop under its position, and what does a restart do with it?* Designed by `EPIC-039L`
C1, built by C2 to C4; nothing below runs yet. The choices and what the documentation did not say are in
[`DECISION_2026-10-16`](../../../Tasks/epics/EPIC-039_futures_venue_profile/DECISION_2026-10-16_futures_protective_stop_minimum.md).

**Place.** At the first fill that makes the account position non-zero (the opening fill, or for a kind that opens flat the first ladder fill) and, for the opening fill, before the ladder is declared ready, the executor saves a record
`INTENDED` (the stop's `clientAlgoId` and trigger price) in the bot's runtime, sends a `STOP_MARKET`
conditional order with `closePosition=true` and `workingType=MARK_PRICE` through `trading`, and saves
`STANDING` on the answer. A take profit, when the plan has one, is a second order of the same kind
(`TAKE_PROFIT_MARKET`) with the same life. A bot with no stop-loss price places none and is
*unprotected*. A lost answer is resolved by reading the order by its `clientAlgoId`; an id that does not
exist is sent again with the same id: the id is unique among *open* orders, and a resend follows only a not-found read, so it cannot make a second open order.

**Exit.** Every exit (Stop, stop loss, take profit, a halt that closes) runs the same close, and the stop
is cancelled as one more step **after** the bot's own derived position is zero and the exchange's position
of the symbol reads zero, a remainder below one market step, or the quantity the foreign-position rule
already names. Any other reading, a close that failed or a read that failed leaves the stop standing.
A stop that is kept (a halt that left the position, a Stop with *keep*, an unconfirmed close) stays under
the bot's record and the symbol stays claimed; a custody check, run at every boot, before a start or
resume on the symbol and on each position or algo event, cancels it once the bot's exposure is closed.
A stop is told from a ladder order by one seam: the gateway's ladder read returns ladder orders only and
a separate read returns the stops.

**Restart.** The reconcile reads the symbol's position and the bot's protective orders (told from
ladder orders by type and `closePosition`, not by their id) and applies one table: adopt a matching
stop; replace a different one (the new stop stands before the old is cancelled); place one where a
position has none and close the position if it cannot stand; cancel an orphan only after a second read
confirms flat; a stop that triggered while the app was down returns the bot `STOPPED`, flat, with the
reason `protective_stop_triggered`. A stop that disappears while a position stands (an `EXPIRED`
from the exchange, a manual cancel) is placed again once, then the position is closed.

**Halt.** Whether a halt closes or leaves the position is decided at the moment of the halt by reading
the exchange: a position stays only under a stop that reads `NEW` and matches the record
(`PositionExposureCloser.closes_on_halt` in `bots/application/services/positions/closer_futures.py`
becomes a question about that moment, C3). The desk's Emergency Stop runs three steps (C3): it cancels the
regular orders, closes the positions, then cancels the conditional orders of each symbol confirmed flat,
so a close that fails leaves the stop.

