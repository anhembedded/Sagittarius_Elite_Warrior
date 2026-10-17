Status: Current

# `bots` — 7. Deployment

*Which thread runs what, what is shared, which files it writes, what a second process does, and how
the host runs it?*

[`diagrams/07-threads.puml`](diagrams/07-threads.puml) — *which thread runs what for the bots, and
which one writes a running bot's file?*

## Built: threads

Each bot has its own worker thread and FIFO queue, so one slow bot never delays another
(`bots/adapters/thread_bot_work_queue.py` → `ThreadBotWorkQueue`, one queue per bot from the factory's
`queues` argument, `bots/composition/executor_bindings.py` → `grid_executor_deps`). Everything that
changes a running bot runs there: the router on the bus thread only copies an event and queues it
([`05-building-blocks.md`](05-building-blocks.md)). Periodic checks run on `ThreadBotTicker`
(`bots/adapters/thread_bot_ticker.py` → `ThreadBotTicker`): one ticker, named `bots-ticker`
(`.../executor_bindings.py` → `_build_ticker`), with a daemon thread per task. A bot waiting to recover has its recovery run posted onto its own worker at that beat (`.../kinds/grid/recovery/grid_halt_recovery.py` → `GridHaltRecovery.check`), so the attempt, the cancels and the new ladder run on the thread that owns the bot and never beside a fill. The user-stream and
sleep watches re-arm on the retry scheduler's heartbeat ([`10-quality.md`](10-quality.md) gives the
periods). `BotsModule.shutdown` (`bots/module.py` → `BotsModule.shutdown`) closes the scheduler first,
then the price streams, then every worker, each after running what is queued, so the app exits with
no bot thread left and nothing half-written.

## Built: files, and who writes them

Each bot is one file, `state/bots/<id>.json`, under the data root
(`bots/composition/state_bindings.py` → `bots_directory`), written atomically by `JsonBotStore`; its
shape is in [`08-concepts.md`](08-concepts.md). Four writers call `IBotStore.save`, each in its own phase
of the bot's life:

| Writer | Thread | When it may write |
| :--- | :--- | :--- |
| `BotRunState` (`.../bot_run_state.py` → `BotRunState`) | the bot's worker | while the bot has a worker: every fill, transition and update of a run |
| The create, edit and venue-change use cases (`.../create_bot/handler.py` → `CreateBotCommandHandler`; `.../edit_bot/handler.py` → `EditBotCommandHandler`; `.../change_bot_venue/handler.py` → `ChangeBotVenueCommandHandler`) | the caller's | a bot at rest only: the lifecycle admits `edit` in `DRAFT` and `STOPPED`, and a venue change in a Spot `DRAFT` that never ran (`bots/domain/bot.py` → `Bot.edited`, `Bot.moved_to`) |
| `BotRunner.start` (`.../bot_runner.py` → `BotRunner.start`) | the caller's | once, the `STARTING` it saves after retiring the earlier run's worker and before it queues the new one ([`06-runtime.md`](06-runtime.md)) |
| `BotRestoreService.restore_all` (`.../bot_restore_service.py` → `BotRestoreService.restore_all`) | boot | before any worker exists or any event is subscribed |

**Rolling back across `AWAITING_RECOVERY`** (`EPIC-042B`). An older build reads the new `recovery_attempts` key as nothing (it reads only the keys it knows) and so loses the ledger on its next write. It **refuses** a file whose state is `AWAITING_RECOVERY` (`bots/adapters/persistence/bot_record_codec.py` → `decode` rejects an unknown state value): the bot is *reported* as unreadable, left untouched and never dropped (`bots/contracts/i_bot_store.py` → `RefusedBotFile`), and the host's pre-flight fails on it. So before a downgrade, resume or stop every bot in `AWAITING_RECOVERY`; the status report lists them (`bot list`, the `awaiting_recovery` count in the health snapshot).

## Built: a second process

A second process on the same data root is read-only (`EPIC-035H`): `boot()` returns before restoring
any bot or subscribing to fills (`bots/module.py` → `BotsModule.boot`), because a restart rule run
there would rewrite the first copy's running bots, and the store and the runner are the read-only
wrappers. `bot list`, `bot show` and `status` read through the same queries the Bots tab reads through.
Design: design 038 §5.2 (`status` from a second process).

## Built: the headless host

On the headless host `operations`' `run` boots the same module with no window. What stopping does to
the bots is a shutdown policy chosen on the command line (design 038 §6.1, decision O1): leave the
orders resting, the default and what the shipped unit runs (`--on-stop leave-orders`,
`deploy/linux/sew-run.service`; `src/modules/operations/adapters/leave_orders_resting.py` →
`LeaveOrdersResting`), or stop every bot first (`src/modules/operations/adapters/stop_bots_first.py` →
`StopBotsFirst`). A restart leaves running bots `RECOVERING` until a person resumes them, or until
`run --resume-recovering` does (design 038 §6.2, decision O2;
[`06-runtime.md`](06-runtime.md)). Between a stop and the next start nothing watches a stop loss or a
take profit; `EPIC-039L` closes that gap on Futures with an order resting on the exchange.
