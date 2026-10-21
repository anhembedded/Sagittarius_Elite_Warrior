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
refuses a closed venue, an unconfirmed Mainnet start and an unready bot (among the readiness items: another
active bot on the **same venue and symbol**, a venue already running its cap of bots, and a bot of the venue
still `RECOVERING`, all three from `.../lifecycle/other_active_bot.py` → `other_active_bot`, `venue_is_full`,
`venue_recovering`, `occupancy_of`; ADR 029 D20 as `EPIC-029J1a` made it per venue and `EPIC-029J1b` per symbol
with the cap `.../domain/venue_bot_cap.py` → `MAX_ACTIVE_BOTS_PER_VENUE`; a bot on another venue does not
count, and a file the store refused counts on every venue and symbol), then asks the runner to start (`.../bot_runner.py` → `BotRunner.start`). The runner works **on the caller's thread**: it
retires the earlier run's worker, so no task of that run can save over the new one, applies `start`
(`STARTING`, not yet saved), and asks the Grid's preconditions (`.../grid_start_preconditions.py` →
`GridStartPreconditions.check`) to re-read the parameters, claim the symbol, open the order session
(`.../order_session_opening.py` → `order_session_refusal`) and register the owner budget. A refusal
goes back to the caller with nothing saved and nothing queued. Only once they pass does the runner
save the bot `STARTING` and queue `start` on a fresh worker. On the worker the executor plans and
places the ladder (`.../grid_executor.py` → `GridExecutor._run_start`; `.../grid_start_sequence.py` →
`GridStartSequence.run`), and `ladder_ready` moves the bot to `RUNNING`. The order-session opening and
the budget registration are calls to `trading` the caller waits on.

## Built: several bots on one venue

*Which resources do the bots of one venue share, and what stops them using them all?* (`EPIC-029J1b`;
the measurements are in the task file's §5a.)

- **Per bot:** its executor and worker thread, its price stream, its owner budget and books, its
  lease on its symbol. A tick reaches the executors of its own symbol only: `BotEventRouter.on_tick`
  filters by symbol and venue before anything is queued (about 50 µs a tick, the same at 1, 5 and 20
  bots). A fill is routed by the client order id's tag, a funding charge by symbol.
- **Per venue:** the request-weight gate (`ExchangeCallPolicy` / `RateLimitGate`, one per
  `VenueSessions`), the order session (and so the Emergency Stop, which halts every bot of the venue
  through `BotExecutors.on_venue`), the user-data stream, and since `EPIC-029J1b` the order pacer:
  `VenueOrderPacers` hands every bot of a venue the same `MonotonicOrderPacer`, which reserves a turn
  under a lock, so the venue's orders keep the budget's spacing and stay inside its rate (`OrderPacing`,
  read off the budget by `grid_pacing`; `BUG-238`) whichever bot sends them. A turn is the later of the
  spacing after the previous turn and the window after the turn `max_orders` places back, so a ladder
  longer than the 60 orders a minute is laid at that rate instead of being refused `owner_budget_rate`
  at its 61st order. The pacer keeps its window `STAMP_JITTER` (2 s) longer than trading's, because
  trading stamps an order a moment after the turn. Only the orders that build a ladder or open a position take a turn (`BotOrderGateway._submit_paced`); protective stops and exits do not, so none waits behind a neighbour's ladder.
  **Limits:** (1) The figures are one owner's (a budget's rate and spacing) applied to the whole venue,
  so two bots of a venue share 60 orders a minute where trading allows each 60, and a second bot's
  opening can wait behind its neighbour's ladder; this is the conservative side, accepted for now.
  (2) A wait for the window blocks the bot's worker for at most one window: a Stop asked meanwhile is
  heard only after the wait, and the order that waited is still sent (`GridStartSequence._place` asks
  `stop_asked` before the wait, not after), then the stop cancels it with the rest of the ladder.
  (3) Exits (`market_sell`, `market_reduce_only`) take no turn: they are sent as a close, which trading
  judges by the inventory or the exposure and not by the spacing or the rate that pace placements
  (`BUG-241`; a Spot exit answers to the inventory check only), and it still counts in the window.
  (4) A start whose stamps still land inside one window (a skew beyond `STAMP_JITTER`) meets the
  refusal as a `start_refused`; the margin exists to prevent it, and the integration test fails without it.
- **The account's positions, read once a beat for the venue** (`BOT-184`). `positionRisk` without a symbol
  is one request for the whole account (weight 5), and an idle Futures bot read it twice a beat (its
  risk watch and its protective-stop check): 120 weight a minute for one bot, 2,405 for twenty.
  `SharedPositionReads.of(venue)` hands every bot of a venue the same `VenuePositionReads`
  (`bots/application/services/risk/`), one lock around one read: the first bot of a beat reads, the rest
  of that sweep take its reading, which is served for at most half a beat (`SHARED_READING_MAX_AGE_SECONDS`)
  and dropped by every order or cancel this app sends on the venue (`BotOrderGateway`, before the call and after it; a read in flight is not kept, by a generation each read carries) and by every fill a bot hears (`GridFacts.on_fill`); `invalidate()` never waits for a read (two locks). Only the
  idle watches ask it (`PositionRiskSnapshots`, and `BotAccountReads.watched_position` for
  `ProtectiveStopService.supervise`); a confirmation (a close, a divergence recheck, a start, a coverage
  read) calls `BotAccountReads.position` and reads the account itself. A failed read is raised and not
  kept. Measured on the fake exchange (`test_many_bots_on_one_venue_cost_on_the_fake_exchange.py`): an
  idle minute reads the positions 60 weight whether there are 1, 5 or 20 bots (it was 120, 600, 2,405),
  and the idle bot costs 115, 67 and 58 weight a minute at 1, 5 and 20 (it was 175 at each). A stop that left the open list is judged on the account's own read (`ProtectiveStopService._explain_absence`), never on the beat's, so a stop that ran just after a beat's read is told as triggered.
- **The symbol's mark price, read once a beat for the bot's two watches** (`BOT-221`). The exit watch
  (`GridMarkExit`) and the risk watch (`PositionRiskSnapshots`) of one bot each read the symbol's
  `premiumIndex` every beat: two requests (weight 1 each). `SharedMarkReads.of(venue, symbol)` hands
  both the same `BoundedAgeReading` (`bots/application/services/risk/`, the mechanism `VenuePositionReads`
  also stands on), reached through `BotAccountReads.shared_mark` by `ExchangeMarkSource`. It is
  served for at most half a beat, dropped by every order or cancel the bot sends and every fill it
  hears (`BotAccountReads.account_changed`, the same call that drops the positions), and a failed
  read is raised and not kept. Two bots never hold one symbol of a venue (`other_active_bot`), so
  today the sharers are the two watches of one bot, not several bots: an idle bot costs 103, 55 and 46
  weight at 1, 5 and 20 (it was 115, 67, 58). **Not shared on purpose:** the open orders and open algo
  orders (`BotAccountReads.protective_orders`, one read a beat, no second reader on the symbol, so
  sharing saves nothing and would sit between the bot and the question whether its stop still stands);
  and every confirmation. **Limit:** what an idle bot still costs is symbol-scoped and linear in the
  bots; the next lever is `premiumIndex` without a symbol (weight 10 for every symbol, worth it only
  above about ten bots on a venue, past today's cap).
- **A rate limit one bot meets** closes the venue's gate for every caller. A neighbour that needs an
  order halts `RATE_LIMITED` at that order and waits for the pause in `AWAITING_RECOVERY`; a neighbour
  that only reads says so and keeps its ladder (`GridRateLimitPause`, `GridRiskWatch`). Every waiting
  bot of the venue attempts on the same beat of the price watch once the pause is over and the
  `AUTO_RESUME_MARGIN` has passed (see "The exchange's pause" below).
- **What caps it:** `other_active_bot` (one bot per venue and symbol), `venue_is_full` (at most
  `MAX_ACTIVE_BOTS_PER_VENUE`), `venue_recovering` (no Start while a bot of the venue waits to
  recover: its orders and budget are reconciled only by its own Resume, so nothing new starts beside that
  unverified exposure; a Start's session opening resumes no other bot, `BOT-183`, `BOT-197`, `BOT-201`).

## Built: a fill

[`diagrams/06-fill.puml`](diagrams/06-fill.puml) — *what happens when one of a bot's orders fills?*

The router (`.../bot_event_router.py` → `BotEventRouter.on_fill`) gives the fill to `GridFacts`,
which ignores one already counted and books the rest on the bot's worker (`.../grid_facts.py` →
`GridFacts.on_fill`, `GridFacts._apply_fill`). A filled level lays its counter order one level away
and returns to `EMPTY` (`settled`, the level machine in [`state-machines.md`](state-machines.md)), and
the bot's run state saves the new runtime. Once it is saved, one `BotOrderFilledEvent` is published for
each order the fact filled whole (`bots/domain/grid/grid_reactions.py` → `Reaction.filled`;
`bots/application/kinds/grid/grid_fill_announcer.py` → `GridFillAnnouncer.announce`; BOT-189): a partial fill and a trade already counted publish nothing, and
the `alerting` module words the rest.

**The exit's result (`BOT-190`).** An exit's market slices are sent inside the stop, which then confirms
STOPPED; each slice fills later, as a fact on the bot's queue, and is booked by `_apply_fill` with
`book_exit_fill`. So the run's result is final only after the last of them. Right after it books an exit
slice's fill, `GridFacts` asks (`bots/application/kinds/grid/grid_exit_report.py` → `GridExitReport.after_exit_fill`)
whether what the run still holds is dust, as the stop treats it (`bots/domain/grid/exit_dust.py` →
`is_exit_dust`: under one market step; on Spot also worth less than the minimum notional). If it is, it
publishes one `BotExitClosedEvent` with the run id, the stop's reason and the books' figures, fee
included; the slices sent are counted (`OffLadderOrders.exits_sent`), so the last slice's further trades
publish nothing. It is a notification after the booking: it orders, cancels, sizes and confirms nothing,
and `GridStopSequence` is unchanged. Spot's base sale and the Futures reduce-only close are both exit
slices, so one path covers both. Nothing is published before a stop has begun (`runtime.reason` is unset): the exchange-side protective stop is registered as an exit slice, and its fill is booked while the bot is still RUNNING, so the call comes after `_supervise_protection` and waits for the stop to give the exit its reason. An exit that sold nothing (a base kept as dust) books no fill and
publishes nothing, and a restart in the middle of an exit forgets the slices it sent, so that exit is not
told.

The stream hands over fills in the order it chooses, not always the order the exchange made them
(`BUG-225`). A counter order whose level the ledger still shows occupied is therefore not yet a
duplicate: `GridBlockedCounter` (`.../grid_blocked_counter.py` → `GridBlockedCounter.on_fill`) reads
the order in the way once from the exchange (`BotAccountReads.order_status`, uncached). If it is
filled, the fill that owes the counter is parked and replayed right after that order's own fill is
applied; if it is cancelled or expired with nothing executed, the level is freed and the counter
retried; if it is still open, or the read fails, the `DUPLICATE_LEVEL_ORDER` halt stands. A parked
fill is in memory only: a restart or a stream gap reconciles from history in the exchange's order
(`BUG-214`).

## Built: Stop

[`diagrams/06-stop.puml`](diagrams/06-stop.puml) — *what does the owner's Stop do, and when is a bot
really STOPPED?*

The use case (`.../stop_bot/handler.py` → `StopBotCommandHandler.execute`) goes through
`GridStopper` (`.../grid_stopper.py` → `GridStopper.run`), which moves the bot to `STOPPING`, to
`GridStopSequence` (`.../grid_stop_sequence.py` → `GridStopSequence.run`): it registers the budget
again, cancels every order carrying the bot's tag, keeps or closes the exposure (the owner's choice;
a stop loss or take profit forces *close*), and reads the open orders again. Only zero tagged orders
raise `stop_confirmed`; anything else leaves the bot `STOPPING`, saying why, never reported stopped
early. The close is sent as a close purpose (`.../bot_order_gateway.py` →
`BotOrderGateway.market_reduce_only`), so `trading`'s owner budget does not count it among the bot's
open orders: the stop's own cancelled orders, which the exchange's open-orders list may still show
when the budget is registered again, never refuse it. A cancel that finds no such order (`-2011`) is
`OrderOutcomeKind.GONE` (`.../order_outcome.py` → `OrderOutcomeKind`, `is_order_gone`, `classify_cancel`; `trading` answers the refusal as a value, `src/modules/trading/contracts/cancel_order_result.py` → `CancelOrderResult`, so the command dispatcher does not log it as a failed command, `BUG-226`), which the
ladder's housekeeping counts as cancelled (`.../grid_housekeeping.py` →
`GridHousekeeping._ended_meanwhile`), not a fault. The automatic retries wait on `STOP_RETRY_DELAYS` ([`10-quality.md`](10-quality.md)); when
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

## Built: the account-level loss cap

*What happens when the day's loss across the host's bots reaches the owner's figure?* (`EPIC-026L`,
decision N3.) The parts are in [`05-building-blocks.md`](05-building-blocks.md).

1. **Sample.** Every `SAMPLE_EVERY_SECONDS` the bots ticker calls `AccountLossCap.sample`
   (`bots/application/services/loss_cap/account_loss_cap.py` → `AccountLossCap.sample`). The sampler
   reads the status report and turns each bot into a `BotObservation`: its run's result
   (`RunEarnings.total_pnl`, realised plus unrealised at the price the bot last saved, at most
   `MARK_PRICE_SAVE_SECONDS` old) or *unknown*.
2. **Add up.** `LossCapLedger.observe` keeps, per bot, the result when the ledger first saw the run
   (its baseline) and the latest; a new run banks the old run's day; a deleted bot keeps what it
   lost. The day is the sum, from 00:00 UTC; at midnight the ledger starts again.
3. **Decide.** `loss_reached` (the loss is at or beyond the figure) or `unjudged_too_long` (a bot that
   may hold risk has had no result for `UNJUDGED_TRIP_AFTER`, the bots could not be read, or a bot
   file is refused). No figure set: nothing is judged.
4. **Trip, in this order.** The trip is written to `loss_cap.json` first; then
   `LossCapStopper.stop_all` dispatches `StopBotCommand` for every bot not at rest (the Bots tab's own
   Stop; a position venue closes at market, the only form it accepts, any other keeps its base);
   then `AccountLossCapTrippedEvent` is published and `alerting` sends the CRITICAL alert. A record that
   cannot be written is logged at ERROR and the trip holds in memory: the stops and the alert still go.
5. **Stay down.** `BotRunner.start` and `resume` refuse with `BotRefusal.LOSS_CAP_TRIPPED` while the
   record holds a trip; every later sample stops a bot that got going by a path that does not ask the
   runner (a halt recovery, for one) and asks again for a stop that was refused. A restart reads the
   record and stays tripped; so does a day roll-over; so does an unset figure.
6. **Acknowledge.** The owner runs `main.py bot loss-cap-ack`; the running host's command directory
   carries it to `AcknowledgeLossCapForHostCommandHandler`, which asks `AccountLossCap.acknowledge`. It is
   refused while today's loss is still at or above the figure (clearing the trip would only trip it again:
   the owner raises `bots.account_loss_cap` and restarts, or waits for 00:00 UTC), and when the cap is not
   tripped. Otherwise the trip clears and **the day's count goes on** from 00:00 UTC, so a further loss to
   the figure trips it again; no bot is started: the owner starts each one.

**What the figure is not.** It is the sum of the bots' own accounts at the prices they last saved,
not the exchange's equity: it sees what a bot has recorded, within about
`SAMPLE_EVERY_SECONDS + MARK_PRICE_SAVE_SECONDS` of the market, and between the trip and the last bot
reaching `STOPPED` the market goes on. A Spot bot keeps its base, so its loss can still move after
the trip; the alert says so. These limits are the price of a cap that depends on no bot's own logic
and adds no close path.

## Built: restart

[`diagrams/06-restart.puml`](diagrams/06-restart.puml) — *what happens to a running bot when the app
restarts?*

`BotRestoreService` (`.../bot_restore_service.py` → `BotRestoreService.restore_all`) applies
`app_restart` to every saved bot: `RUNNING` and `PAUSED` become `RECOVERING`, `STARTING` becomes
`HALTED`, and nothing is placed. A tripped account-level loss cap is read back from its record and still holds every start and resume
(`bots/composition/loss_cap_bindings.py` → `bind_loss_cap`); a record this build cannot read starts the
cap tripped (`LossCapTripReason.RECORD_UNREADABLE`). `BotBootRecovery` (`.../bot_boot_recovery.py` →
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

The opening is announced as opened *for* the bot that asked (`BOT-183`, ADR 038 O2: a host never resumes a bot by itself). `order_session_refusal` passes the bot id to `ITradingSession.ensure_ready` (`src/modules/trading/contracts/i_trading_session.py` → `ITradingSession.ensure_ready`), which carries it on `TradingSwitchChangedEvent.opened_for` (`src/modules/trading/application/session/session_readiness.py` → `SessionReadiness.ensure_ready`). `BotEventRouter.on_switch` hands it to every bot of the venue, and `GridFacts._apply_switch` reconciles a `RECOVERING` bot only when `opened_for` names that bot or is `None` (no opener known); any other `RECOVERING` bot logs `[recovering-waits]` and stays as it was. A person's action that belongs to no bot, a manual order (`ExecuteOrderCommandHandler`) or arming a strategy (`ArmStrategyCommandHandler`), passes the typed `OpenedByPerson.PERSON` (`src/modules/trading/contracts/session_opener.py` → `OpenedByPerson`, `SessionOpener`), which wakes no `RECOVERING` bot either (`BOT-197`, the owner's decision of 2026-10-20). The headless `run --resume-recovering` no longer relies on the event: it sends each `RECOVERING` bot its own `ResumeBotCommand` (`.../resume_recovering_for_host/handler.py` → `ResumeRecoveringForHostCommandHandler`), so it resumes them also when an earlier Resume already opened the session, which publishes no event. A `STOPPING` bot and the cancel a cut-short start owes act on any opening, as before: each finishes what its owner already asked for.

A deliberate action that trades opens the order session in one place (`.../order_session_opening.py` →
`order_session_refusal`, `order_session_refusal_words`), with exactly three callers: Start, a Resume
from `HALTED` or `RECOVERING`, and the operator's `bot stop` on a running host (`EPIC-038J`, below)
(`.../grid_start_preconditions.py` → `GridStartPreconditions.check`,
`GridStartPreconditions.open_session_for_resume`; `src/modules/bots/application/use_cases/stop_bot_for_operator/handler.py` → `StopBotForOperatorCommandHandler.execute`). The headless `run --resume-recovering` is the Resume caller's own too: it sends each `RECOVERING` bot the screen's `ResumeBotCommand` (`.../resume_recovering_for_host/handler.py` → `ResumeRecoveringForHostCommandHandler._resume`). The headless `run --resume-halted` (`EPIC-042E`) is the
Resume caller's own: it dispatches the screen's `ResumeBotCommand`, so it opens the session through the
same Resume path, and its `ConfirmBotResumeCommand` once the bot holds the proposal
(`.../resume_halted_for_host/handler.py` → `ResumeHaltedForHostCommandHandler`); it dispatches every Resume first, then asks
again every `PROPOSAL_POLL_S` against one shared `PROPOSAL_WAIT_S` deadline, never confirms blind, and
withdraws (`IBotRunner.withdraw_resume_proposal`) a proposal that did not come in time, so none is left
held to block the automatic recovery. Nothing automatic opens it: a
late order must not undo an Emergency Stop.

A running `run` host takes five more requests from a person's second shell (`EPIC-038J`, `EPIC-038K`, `EPIC-038L`): `bot stop`,
`bot pause`, `bot resume`, `bot start` and `bot edit` arrive as `StopBotForOperatorCommand`, `PauseBotForHostCommand`,
`ResumeBotForHostCommand`, `StartBotForHostCommand` and `EditBotForHostCommand` (`src/modules/bots/application/use_cases/pause_bot_for_host/handler.py` → `PauseBotForHostCommandHandler`;
`src/modules/bots/application/use_cases/resume_bot_for_host/handler.py` → `ResumeBotForHostCommandHandler`), each dispatching the screen's own
command, so the lifecycle table, the read-only rule and the real-money question apply unchanged. `bot stop` arrives as `StopBotForOperatorCommand` (`src/modules/bots/application/use_cases/stop_bot_for_operator/handler.py` → `StopBotForOperatorCommandHandler`): after the lifecycle table allows the stop, a position venue is refused (`EXPOSURE_MUST_CLOSE`, in words that name `--close-position`) unless the operator typed the flag (`StopBotForOperatorCommand.close_position`, carried by the command file's optional `close_position` key, `BUG-224`); then it opens the venue's order session when it is closed (`order_session_refusal`, a mainnet venue only with the typed venue), then dispatches `StopBotForHostCommand` with `ExposureHandling.CLOSE_AT_MARKET` for the flag and `KEEP` without it, which the host handler passes unchanged to the screen's `StopBotCommand`. So a Futures bot can only be stopped from the command line with the explicit close, and a Spot bot keeps its base unless the flag sells it. The shutdown policy's `StopBotForHostCommand` still opens nothing; `--on-stop stop-bots` keeps (so it leaves a Futures bot, which refuses KEEP), while the default policy closes a Futures bot whose stop does not cover it (next section), and the screen's Stop is unchanged. The resume covers PAUSED and RECOVERING; a
HALTED or AWAITING_RECOVERY bot is refused with words, because its resume proposes a ladder a person confirms.
`bot start` is the very `StartBotForHostCommand` that `run --start-planned` dispatches (`src/modules/bots/application/use_cases/start_bot_for_host/handler.py` → `StartBotForHostCommandHandler.execute`), which dispatches the screen's `StartBotCommand`: so the readiness check refuses in words for the symbol's holder, a full venue and a venue with a RECOVERING bot (`other_active_bot.py` → `occupancy_of`). The handler adds two answers for both callers: a HALTED or AWAITING_RECOVERY bot is refused with the way back (`run --resume-halted`, the Bots tab) before the lifecycle table is asked, and the refusal that asks for the typed mainnet venue names the venue's RECOVERING bots, so the person sees that they wait and that the Start is refused while any does (a Start's session opening resumes none of them, `BOT-183`; the reason is above, `BOT-201`). Deleting a bot is not a request the host takes (the owner dropped `bot delete` from the command directory on 2026-10-17): it stays `bot apply --prune` on a stopped host. The command file's `action` word is the only new key value: an older host reads `start` as a malformed document.
`bot edit` is `EditBotForHostCommand` (`src/modules/bots/application/use_cases/edit_bot_for_host/handler.py` → `EditBotForHostCommandHandler.execute`), the Bots tab's Save for one bot at rest reached through the command directory (`EPIC-038L`). Under `BotCommandLock`, the lock `StartBotCommandHandler` holds while it reads every bot and moves one to STARTING, it (1) asks the lifecycle table (`bot_lifecycle_fsm_matrix.py` → `permits_edit`: DRAFT and STOPPED only; every other state is refused in words that say to stop it first, or to wait when it is STOPPING), (2) refuses an empty set, a repeated key or more than `MAX_SETTINGS_PER_EDIT` settings (`src/core/contracts/parameter_setting.py` → `ParameterSetting`, `MAX_SETTINGS_PER_EDIT`), (3) merges the settings into the bot's parameters and asks the bot's kind whether the changed ones can be stored, without the exchange (`i_bot_kind.py` → `IBotKind.parameter_problem`, closed by default so a kind that declares nothing is edited by no command line; the Grid answers through `grid_parameter_check.py` → `grid_parameter_problem`, which builds a probe and asks `GridParams.from_config`, so `validate` and the edit share one set of rules and only the changed keys, with the other end of the range and the `direction`/`leverage` pair they are judged against, are blamed on the edit), (4) refuses a set that changes nothing, then (5) dispatches the screen's own `EditBotCommand` (`edit_bot/handler.py` → `EditBotCommandHandler.execute`: the bot lands on DRAFT; kind, venue and symbol are not editable) and answers each `key old -> new`. An edit places no order and asks no venue, so a mainnet bot needs no `--confirm-venue`; the money question stays at `bot start`, whose guard is untouched. A bot at rest has no executor and no worker, so there is no queue to run on: the write is the one the Save makes, serialized with a Start by the lock. The values to edit are read with `bot show <id> --params` (`GetBotStatusReportQueryHandler` fills `BotStatusEntry.parameters` for the one-bot read only; a plain read of the file, no host round trip). The command file gains the optional key `set` (`host_command_codec.py` → `parse_command`, `encode_command`) next to the action word `edit`; an older host reads the unknown key as a malformed document and does nothing. `state/bot_plan.json` (`AppliedPlan`) records a desired state per bot and no parameters, so an edit leaves it alone; the plan file is the owner's and must be edited to match, or the next `bot apply` of the old plan edits the bot back.
The transport is the `operations` module's (`Docs/MODULES/README.md` has no `operations` folder yet): the host's `HostedControlPoller` (`src/modules/operations/adapters/hosted_control_poller.py` → `HostedControlPoller`) runs on the Engine scheduler's thread, so these five commands are dispatched from that thread, as the stop policy's worker dispatches Stop; each is queued on the bot's own executor, which is the bot's one writer. At shutdown the Engine stops the scheduler first and the hosted services after, and the poller's `stop()` waits for a poll already running and then refuses further ones, so no command is dispatched into a closing application.

## Built: what the headless host does to a Futures bot when it stops

[`diagrams/06-host-stop.puml`](diagrams/06-host-stop.puml) — *what does the headless host do to a Futures
bot when it stops (`systemctl stop`, `sew-update`, a restart)?* Built by `EPIC-038M` for owner question O12
([`DECISION_2026-10-20`](../../../Tasks/epics/EPIC-038_headless_operation/DECISION_2026-10-20_a_futures_bot_at_host_stop.md)).
Under the default `--on-stop leave-orders` the policy (`src/modules/operations/adapters/leave_orders_resting.py` →
`LeaveOrdersResting`) asks `GetBotStopCoverageQuery` (`src/modules/bots/contracts/bot_stop_coverage.py` →
`GetBotStopCoverageQuery`, `StopCoverage`) of each active bot. The handler (`src/modules/bots/application/queries/get_bot_stop_coverage/handler.py` →
`GetBotStopCoverageQueryHandler`) answers `NOT_APPLICABLE` for an inventory venue without touching the exchange (the
venue profile's `ExposureKind`, `src/modules/bots/contracts/venue_profile.py` → `ExposureKind`) and, for a position venue, asks the bot's
executor (`IBotRunner.stop_coverage` → `GridExecutor.stop_coverage` → `IExposureProtection.read_coverage`), which reads **now** the
bot's open protective orders, its position and its open ladder orders
(`src/modules/bots/application/kinds/grid/protection/stop_coverage_reader.py` → `StopCoverageReader.read`, judged by
`stop_words.py` → `judge_stop`, the judgement the halt's words use). The read is not queued behind the bot's worker: one racing a
placement finds the stop missing and errs toward closing.

A Spot bot (`BotStatusEntry.may_hold_position` false, set from the venue profile by `GetBotStatusReportQueryHandler`) is decided first and is always left: it is never read and never closed, whatever the budget says. A bot is **left** when its position stands under a recorded stop that stands on the exchange on the side that closes it
(`COVERED`), or when it holds no position and rests no ladder (`NOTHING_EXPOSED`): its position, orders and stop stay and it
returns RECOVERING. It is **closed** otherwise (`UNCOVERED`: no stop, a recorded stop the exchange does not list, a stop on the
wrong side, or a flat account whose ladder still rests, because a fill would open a position no stop covers, or a NEUTRAL grid whose ladder rests, because it stands the stop of one side only and a fill through zero would open the other (`StopCoverageReader._covered_unless_it_can_flip`); `UNREAD`: the
exchange could not be read, which is not covered): the policy dispatches `StopBotForHostCommand` with `ExposureHandling.CLOSE_AT_MARKET`
(`src/modules/operations/adapters/host_bot_stopper.py` → `HostBotStopper.begin`), the Stop the Bots tab's "Close the position at market"
reaches through `StopBotCommand`, names the bot at WARNING and keeps it in the `StopLedger` until it reads STOPPED. Reading takes
`READ_SHARE` of `--stop-timeout` (`leave_orders_resting.py` → `READ_SHARE`); a bot not read by then is closed unread and the log says the
deadline made closing the safe side. The close never opens the venue's order session, so a RECOVERING bot on a closed session stays
STOPPING and the host names it as left. A Spot bot is left as before. `--on-stop stop-bots` is unchanged: it still asks `KEEP`,
which a position venue refuses.

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
plainly, and a Futures venue has no rule but the exchange's pause. The ladder comes off on entering the state
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
symbol that does not trade, a rejected key) ends in `HALTED` through `halt_with`; one that meets the
exchange's pause goes back to waiting, for the pause (below); one that
changes nothing (the budget registration refused, the price unreadable) leaves the bot waiting with the
attempt spent, and with the budget spent it goes to `HALTED` with `budget_exhausted`. The run does
nothing while a person's resume proposal is held, and a person's Resume, a Stop or an Emergency Stop
moves the bot out and the next beat forgets the wait. The cancel in step (3) is also the retry of an
entry park that failed during the outage: no ladder is laid over orders that may still rest.

**The exchange's pause** (`EPIC-042F`). A rate limit is one more reason of the policy, `rate_limited`,
declared in the Grid's layer (`GRID_RECOVERY_LAYER`) with a dwell of `AUTO_RESUME_MARGIN` and the common
budget (three per rolling 24 h per bot, counted with every other reason) and stalled alert; a Futures
venue clears the lower layers and lists it alone, so a Futures bot resumes from a pause as it always did
(`BUG-216`). The halt reaches the mechanism from two doors that end in one function
(`.../kinds/grid/grid_order_failure.py` → `pause_with`): an order the venue's gate refused (`fail_with`)
and a read or cancel that raised (`GridRateLimitPause.halt`). A bot that places or waits to goes to
`AWAITING_RECOVERY`, keeping its ladder (no cancel is sent into a pause, `GridTaskGuard`), unless the
pause is longer than `MAX_AUTO_RESUME_WAIT` (`.../domain/grid/rate_limit_pause.py` →
`too_long_to_wait_words`): that halt is plain and says "resume by hand". After the task,
`GridRateLimitPause.after_task` records when the pause ends on the bot's monotonic clock; the probe
(`GridHaltProbe`) says `rate_limited` is clear when it has ended (`GridRateLimitPause.holds`), so the
run's dwell is the margin and its attempt is the person's own Resume, **with the exits re-checked on a
fresh price first**: a stop loss crossed during the pause ends the bot as a Stop and no ladder is laid,
which the retired timer never checked. A bot already waiting for another reason keeps that reason and its
dwell; the pause only joins the causes the run samples (`GridHaltRecovery._every_cause_clear`), so a
limit cannot shorten a quiet feed's 120 s. A limit met by an attempt costs that attempt, and the waiting
bot attempts again after the pause; a spent budget ends the wait in `HALTED` (`budget_exhausted`). What
the mechanism never recovers is left to a person and says so: a `PAUSED` or `RECOVERING` bot that meets a
limit is `HALTED` (the owner's Pause is not undone by a machine), and so is a `HALTED` bot whose Resume met
one (resume again once the pause ends). The pause's end is kept in memory: a restart ends the wait in
`HALTED` like any other. All bots of a venue wait for the same instant (the gate is the venue's) and
attempt on the same beat of the price watch, about a beat later than the old timer fired.

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

## Built: a backtest from the workbench (EPIC-040D)

[`diagrams/06-backtest-run.puml`](diagrams/06-backtest-run.puml) — *what happens, in order, when the
owner presses Run on the Backtest workbench?* The replay and the candle sync run off the UI thread
(`bots/ui/backtest_workbench/backtest_run_coordinator.py` → `BacktestRunCoordinator.start_backtest`,
`start_sync`) and answer with the id of the action that started them
(`backtest_workbench_presenter.py` → `BacktestWorkbenchPresenter._on_finished`). One fence
(`ActionOwnershipTracker`) covers both, so the page has at most one action at a time. **Cancel**
invalidates the action before it stops the worker (a per-run `threading.Event` the kind's backtester
polls): the answer of a cancelled run is never shown, and the last result stays; a Cancel with
nothing running does nothing. **Another bot selected** replaces the sandbox with that bot's copy,
ends the run the same way and clears the result, because a result is only ever shown beside the
bot it was run for; the same bot read again changes nothing. While the sandbox keeps edits (the
question is open, or the person chose to keep them) it stays the source bot's: it is judged,
replayed and drawn with the market numbers and risk facts that bot came with
(`backtest_workbench_presenter.py` → `BacktestWorkbenchPresenter.follow`; `sandbox_editing.py` → `SandboxEditing.copies`),
never another symbol's, and a run already in flight when the question opens is not cancelled: it
finishes for the sandbox's own bot. **A refusal for candles that
are not stored** offers a sync and never fetches by itself (`BUG-107`); after the sync the same query
runs again with the funding the person chose for it. **A failure** is a command failure to the notifier (`bots.backtest.backtest` or
`bots.backtest.sync`) and the page says "The run failed." only; the exception travels as the
notice's detail (`BOT-169`). The sandbox plan the request carries is a copy, so no step of this
sequence reaches the bot, its orders or the account.

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
