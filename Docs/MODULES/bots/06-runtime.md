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
refuses a closed venue, an unconfirmed Mainnet start and an unready bot (among the readiness items: a
bot of the **same venue** that is not at rest, `.../lifecycle/other_active_bot.py` → `other_active_bot`,
ADR 029 D20 as `EPIC-029J1a` made it per venue; a bot on another venue does not count, and a file the store
refused counts on every venue), then asks the runner to start (`.../bot_runner.py` → `BotRunner.start`). The runner works **on the caller's thread**: it
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
Spot, sells what was bought above the session's baseline). On Futures the order is the safety
(`.../emergency_stop/futures_stop_steps.py` → `cancel_regular_orders`, `close_all_futures_positions`,
`cancel_conditional_orders_of_flat_symbols`): the regular orders first, so the ladder cannot refill; then
the close; then the conditional orders of each symbol a fresh read shows flat. A close that fails leaves
the protective stop standing over the position and the result names the symbol (decision D11, the owner's
O1). The router hands the switch to every bot on
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
`order_session_refusal`, `order_session_refusal_words`), with exactly four callers: Start, a Resume
from `HALTED` or `RECOVERING`, the headless `run --resume-recovering`, and the operator's `bot stop` on a running host (`EPIC-038J`, below)
(`.../grid_start_preconditions.py` → `GridStartPreconditions.check`,
`GridStartPreconditions.open_session_for_resume`; `.../resume_recovering_for_host/handler.py` →
`ResumeRecoveringForHostCommandHandler._open`; `src/modules/bots/application/use_cases/stop_bot_for_operator/handler.py` → `StopBotForOperatorCommandHandler.execute`). The headless `run --resume-halted` (`EPIC-042E`) is the
Resume caller's own: it dispatches the screen's `ResumeBotCommand`, so it opens the session through the
same Resume path, and its `ConfirmBotResumeCommand` once the bot holds the proposal
(`.../resume_halted_for_host/handler.py` → `ResumeHaltedForHostCommandHandler`); it dispatches every Resume first, then asks
again every `PROPOSAL_POLL_S` against one shared `PROPOSAL_WAIT_S` deadline, never confirms blind, and
withdraws (`IBotRunner.withdraw_resume_proposal`) a proposal that did not come in time, so none is left
held to block the automatic recovery. Nothing automatic opens it: a
late order must not undo an Emergency Stop.

A running `run` host takes three more requests from a person's second shell (`EPIC-038J`): `bot stop`,
`bot pause` and `bot resume` arrive as `StopBotForHostCommand`, `PauseBotForHostCommand` and
`ResumeBotForHostCommand` (`src/modules/bots/application/use_cases/pause_bot_for_host/handler.py` → `PauseBotForHostCommandHandler`;
`src/modules/bots/application/use_cases/resume_bot_for_host/handler.py` → `ResumeBotForHostCommandHandler`), each dispatching the screen's own
command, so the lifecycle table, the read-only rule and the real-money question apply unchanged. `bot stop` arrives as `StopBotForOperatorCommand` (`src/modules/bots/application/use_cases/stop_bot_for_operator/handler.py` → `StopBotForOperatorCommandHandler`): after the lifecycle table allows the stop, it opens the venue's order session when it is closed (`order_session_refusal`, a mainnet venue only with the typed venue), then dispatches `StopBotForHostCommand`. The shutdown policy's `StopBotForHostCommand` still opens nothing, and the screen's Stop is unchanged. The resume covers PAUSED and RECOVERING; a
HALTED or AWAITING_RECOVERY bot is refused with words, because its resume proposes a ladder a person confirms.
The transport is the `operations` module's (`Docs/MODULES/README.md` has no `operations` folder yet): the host's `HostedControlPoller` (`src/modules/operations/adapters/hosted_control_poller.py` → `HostedControlPoller`) runs on the Engine scheduler's thread, so these three commands are dispatched from that thread, as the stop policy's worker dispatches Stop; each is queued on the bot's own executor, which is the bot's one writer. At shutdown the Engine stops the scheduler first and the hosted services after, and the poller's `stop()` waits for a poll already running and then refuses further ones, so no command is dispatched into a closing application.

## Built: the exchange-side protective stop (Futures)

[`diagrams/06-protective-stop.puml`](diagrams/06-protective-stop.puml) — *how does a Futures Grid keep
an exchange-side stop under its position, and what does a restart do with it?* Built by `EPIC-039L`
C2; the halt policy that relies on the stop is C3 and is Planned below. The choices, and what
Binance's pages did not say, are in
[`DECISION_2026-10-16`](../../../Tasks/epics/EPIC-039_futures_venue_profile/DECISION_2026-10-16_futures_protective_stop_minimum.md).

**Place.** The start asks its protection right after the opening and before the ladder
(`bots/application/kinds/grid/start/grid_start_sequence.py` → `GridStartSequence.run`;
`bots/contracts/i_exposure_protection.py` → `IExposureProtection`). Futures' is
`bots/application/kinds/grid/protection/protection_futures.py` → `ProtectiveStopService`. For each
stop the plan asks for, it saves a record `INTENDED` with the stop's `clientAlgoId` and trigger price
in the runtime (`protective_stop_book.py` → `ProtectiveStopBook.intend`), then sends a `STOP_MARKET`
with `closePosition=true` and `workingType=MARK_PRICE` through trading, as a protective order the
owner's pacing checks do not refuse, and saves `STANDING` on the answer (`ProtectiveStopBook.send`).
A LONG grid's stop is a SELL at its stop-loss price, a SHORT grid's a BUY; a NEUTRAL grid's other side
is its take profit, placed only for the side that covers the position until the owner has recorded
check T3 (`protective_stop_plan.py` → `NEUTRAL_BOTH_SIDES_VERIFIED`). A plan with no stop loss places
none and is *unprotected*, said in a warning. A stop that cannot stand halts the bot, which closes its
position (it is never left bare); an opening that left the account flat has nothing to protect yet,
and the first beat that finds a position places it. A send with no answer leaves the record
`INTENDED`: the next look finds the order among the open ones, or sends it again under the same id
(unique among *open* orders, so a resend cannot make a second open order).

**Keep.** On the price watch's beat (`bots/application/kinds/grid/grid_facts.py` →
`GridFacts.on_price_age_check`, `GridFacts._supervise_protection`) the service compares its records
with the open protective orders and the position: a record that is on no open list is placed again
when a position stands; with the account flat the order is read by its client id (no cache), and
`TRIGGERED` — it ran, the verdict the bot stops on with `GridReason.PROTECTIVE_STOP_TRIGGERED` —
is told from the exchange ending it without a fill (the record is dropped, the bot runs on); an
answer that cannot be read counts as ran. An untracked stop of the right side and trigger is adopted;
a stop standing over a flat symbol is cancelled after a second read, because it could open a
position; a recorded stop that no longer covers the position (a NEUTRAL grid whose position changed
sign, while check T3 is unrecorded) goes once the covering one stands. A beat costs about two or three
REST reads per Futures bot: the position, the open protective orders and, only when a stop has
vanished with the account flat, the one order. The fill of a stop reaches the bot under its id when the
stream has linked it, and then runs the same look at once.

**Exit.** Every exit (Stop, stop loss, take profit, a halt that closes) runs the same close, and the
stop goes as one more step after it: `ProtectedCloser` calls the stop's `release` only when the
inner closer answers `None` — the bot's own position is closed, or what remains is below one market
step or not the bot's (`bots/application/kinds/grid/protection/protected_closer.py` →
`ProtectedCloser.close`). A close that failed or is unfinished is returned untouched and the stop
stands; a stop that could not be cancelled keeps the stop sequence waiting on the exchange, so the bot
is never reported stopped with a stop standing. A stop is told from a ladder order by one seam: the
gateway's ladder read returns ladder orders only and a separate read returns the stops
(`bots/application/services/orders/bot_account_reads.py` → `BotAccountReads.ladder_orders`,
`BotAccountReads.protective_orders`).

**Restart.** `GridFacts.reconcile_recovering` looks at the stops twice
(`bots/application/kinds/grid/grid_facts.py` → `GridFacts.reconcile_recovering`). Before the
reconcile it only reads: a stop that ran while the app was closed has left the account flat, which the
reconcile would call a position mismatch, so the bot stops there with the reason
`protective_stop_triggered`. After the reconcile has registered the budget (trading takes a tagged
order only under one) a missing stop is placed, before anything held is laid; a standing one is
adopted from the open list. The bot is never bare at any step.

## Built: a transient halt recovers by itself

[`diagrams/06-halt-recovery.puml`](diagrams/06-halt-recovery.puml) — *what happens to a Spot Grid whose
price feed goes quiet and comes back?* Built by `EPIC-042C`; the state and its rows are in
[`state-machines.md`](state-machines.md), the choices in [the decision](../../../Tasks/epics/EPIC-042_halt_auto_recovery/DECISION_2026-10-17_halt_auto_recovery.md).

**The halt.** `GridPriceReaction.check_age` (`bots/application/kinds/grid/watch/grid_price_reaction.py` →
`GridPriceReaction.check_age`) halts a bot in `PRICE_STALENESS_HALTS` that heard no tick for
`PRICE_STALE_AFTER_SECONDS`, and `GridStreamGap.halt` does the same for a stream down too long. Both
call `halt_with` (`bots/application/kinds/grid/grid_order_failure.py` → `halt_with`), which now asks
`BotRunState.halt` (`bots/application/services/lifecycle/bot_run_state.py` → `BotRunState.halt`) for the
event. The halt-recovery director (`.../services/lifecycle/halt_recovery_director.py` →
`HaltRecoveryDirector.decide`) answers `halt_transient` when the bot is `RUNNING` or `STARTING`, the
bot's effective policy (`bots/contracts/venue_profile.py` → `recovery_policy_of`: the common, the Grid's
and the venue's layers merged) has a rule for the reason, and the bot's ledger holds fewer attempts than
the rule allows in its window; otherwise `halt`, and when the budget is what made it plain the reason
says "the 3 automatic recoveries allowed in 24 h are used up". A `PAUSED` or `RECOVERING` bot halts
plainly, and a Futures venue has no rule. The ladder comes off on entering the state
(`.../kinds/grid/grid_task_guard.py` → `GridTaskGuard`). When that cancel fails the bot lands in plain
`HALTED` instead (`GridTaskGuard._halt_unparked`): the wait presumes a ladder off the exchange, and
`BOT_HALTED` then says the orders may still rest.

**The wait.** The bot keeps its price stream and keeps watching its stop loss and take profit
(`GridPriceReaction`), so a tick that reaches either runs Stop as it does in `HALTED`. On every beat of
the price watch (`bots/application/services/watches/bot_price_watch.py` → `CHECK_EVERY_SECONDS`) the
Grid posts `GridHaltRecovery.check` on its worker (`.../kinds/grid/recovery/grid_halt_recovery.py` →
`GridHaltRecovery.check`). It asks the probe (`.../kinds/grid/watch/grid_halt_probe.py` →
`GridHaltProbe.is_clear`) whether each cause of the bot's effective policy is clear (every one, not only the one it halted on:
a feed that returns while the stream is still down waits): for the feed, a tick heard since the bot began to
wait and younger than `RECOVERY_TICK_MAX_AGE_SECONDS` (`bots/domain/grid/price_freshness.py`), read from
the last tick and never from `GridPriceAge.stale_detail`; for the stream, the venue's stream reporting
CONNECTED (`.../services/watches/user_stream_status.py` → `UserStreamStatus`). A clear sample starts the
*clear since* mark and a not-clear one resets it, so the dwell is continuous to the beat.

**The attempt.** When the cause has been clear for the dwell the run: (1) saves the attempt in the
bot's ledger before anything is asked of the exchange (`BotRunState.record_recovery_attempt`); (2) reads a
fresh price and, if it is beyond the stop loss or take profit, runs Stop and ends there, laying no
ladder; (3) runs the person's own Resume, `GridResumeSequence.propose` (budget registered from exchange
evidence, every tagged order cancelled, a ladder sized from the price now and the inventory held) and
`GridResumeSequence.confirm` with `condition_cleared`, which re-reads the price and lays the ladder;
(4) publishes `BotAutoRecoveredEvent` (`bots/contracts/events/bot_auto_recovered_event.py`), which
`alerting` carries to the owner from `EPIC-042D`; a wait that lasts `stalled_after` publishes
`BotRecoveryStalledEvent` once, which `alerting` already carries as `BOT_RECOVERY_STALLED`. An attempt that meets a new cause (a moved price, a
symbol that does not trade, a rate limit, a rejected key) ends in `HALTED` through `halt_with`; one that
changes nothing (the budget registration refused, the price unreadable) leaves the bot waiting with the
attempt spent, and with the budget spent it goes to `HALTED` with `budget_exhausted`. The run does
nothing while a person's resume proposal is held, and a person's Resume, a Stop or an Emergency Stop
moves the bot out and the next beat forgets the wait. The cancel in step (3) is also the retry of an
entry park that failed during the outage: no ladder is laid over orders that may still rest.

**The long wait.** The wait has no limit. After the rule's `stalled_after` the run publishes
`BotRecoveryStalledEvent` once (`bots/contracts/events/bot_recovery_stalled_event.py`), which `alerting`
turns into an alert in `EPIC-042D`, and goes on waiting. A restart is not a recovery: the order session is
closed after one, so the bot is `HALTED` with its ledger, and the owner resumes it from the GUI or with
`run --resume-halted` (`EPIC-042E`).

## Built: what a halt that cannot close says (EPIC-039L C3)

A switch-off, a rejected key or a rate limit halts a Futures bot without a cancel or a close, so its
position stays open. The halt's words now say whether the protective stop stands, read from the exchange
at that moment (`bots/application/kinds/grid/grid_parking.py` → `GridParking.left_open_words`; the question is
`bots/contracts/i_exposure_protection.py` → `IExposureProtection.describe_stop`; the words are
`bots/application/kinds/grid/protection/stop_words.py` → `stop_words`): "its protective stop stands on the
exchange", "is not on the exchange" (the record says one stands and the exchange does not list it),
"no protective stop stands over it", or "could not be read", never "none" for an unread list.

## Built: the mainnet lock removed (EPIC-039L C4-lite)

**The mainnet gate (C4-lite), built.** Futures mainnet is open to bots since the owner's O2
(2026-10-17): `CLOSED_VENUES` is gone and every path asks only the real-money confirmation
(`TradingVenue.is_mainnet`). No port, no state file, no setting. The 14-day soak and checks T1–T5 are an
optional runbook (`Docs/OPERATIONS/futures_testnet_soak.md`), not enforced by code; the owner manages the
risk.

## Planned: EPIC-039L, a halt that leaves the position (D10, D13)

**Halt that leaves the position (D10) and custody (D13), deferred.** Whether a halt closes or leaves the
position would be decided at the moment of the halt by reading the exchange: a position stays only under
a stop that reads standing and matches the record (`PositionExposureCloser.closes_on_halt` in
`bots/application/services/positions/closer_futures.py` becomes a question about that moment). That also
needs the custody of decision D13: a stop kept under a stopped or halted bot keeps the symbol claimed,
and a check at boot cancels it once the exposure is closed. Today a Futures position is never kept
(`keep_on_stop_closed_reason`), so no path leaves a stop standing under a stopped bot, and a halt that
can close does close (O8). Not built in C3: leaving real-money positions is the larger risk and the owner
has not asked for it.
