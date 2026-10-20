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
(`.../executor_bindings.py` → `_build_ticker`), with a daemon thread per task. A bot waiting to recover has its recovery run posted onto its own worker at that beat (`.../kinds/grid/recovery/grid_halt_recovery.py` → `GridHaltRecovery.check`), so the attempt, the cancels and the new ladder run on the thread that owns the bot and never beside a fill. The account-level loss cap's sample (`EPIC-026L`; `bots/application/services/loss_cap/account_loss_cap.py` →
`AccountLossCap.sample`) is one more task on that ticker, so it has a daemon thread of its own;
its acknowledgement arrives on the host's command thread, and one lock guards its record while the
reads, the stops and the publish run outside it. The user-stream and
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

**The loss cap's record.** One more file, `state/loss_cap.json`, beside the bots' folder and not in it
(a file inside would be read as a bot; `bots/composition/loss_cap_bindings.py` → `loss_cap_record_path`), written
atomically by `bots/adapters/file_loss_cap_store.py` → `FileLossCapStore`. Its only writer is
`AccountLossCap`, on the sampling thread (the day's ledger, when it changes, and a trip) and on the
host's command thread (an acknowledgement). A host with no figure set never writes it.

## Built: a second process

A second process on the same data root is read-only (`EPIC-035H`): `boot()` returns before restoring
any bot or subscribing to fills (`bots/module.py` → `BotsModule.boot`; the writable half is
`bots/composition/writable_boot.py` → `boot_writable`, reached by path so a read-only copy does not
import it, `PRO-014`), because a restart rule run
there would rewrite the first copy's running bots, and the store and the runner are the read-only
wrappers. `bot list`, `bot show` and `status` read through the same queries the Bots tab reads through.
A read-only Bots tab hears no `BotChangedEvent` (the writer publishes on its own process's bus), so it
re-reads the bots' files on its 30 s clock (`bots/ui/bots_screen/presenter_pacing.py` → `BotsClock`;
`BUG-227`); the writing copy does not.
`bot show` also prints the bot's effective halt-recovery table, one `Recovery` row per reason with the
attempts used inside its window, or `no automatic recovery (<layer> layer)` for a Futures bot
(`bots/application/queries/get_bot_status_report/recovery_table.py` → `recovery_table_of`; `EPIC-042G`).
`bot list` and `bot show` also print the run's grid profit, completed cycles, total PnL and (show only) unrealised (`BOT-192`; grid
profit first, net of both legs' fees and without Futures funding): the Bots tab's figures and words, its table's `Grid profit` and `Cycles` columns and its panel's rows, built once in `bots/contracts/run_earnings.py` → `RunEarnings`, `grid_profit_text`, `total_pnl_text`,
`plain_money`, `plain_price` (Qt-free, because a headless host installs no Qt) from `BotProgress`; `GetBotStatusReportQueryHandler` fills
`BotStatusEntry.earnings`, `bots/cli/bot_status_reports.py` prints it. Read from the bot's file, no exchange call.
`bot show` also prints the Grid bot's ladder summary, the average cycle it booked and where the last price it heard stands, `bot show --grids` one row per grid and `bot list` a `GRID STEP` column (`BOT-193`): the Bots tab's Plan rows and Ladder table, built once in `bots/contracts/grid_ladder.py` → `grid_ladder_of` and worded by `bots/contracts/grid_ladder_texts.py` (Qt-free), carried by `BotStatusEntry.ladder` (`GetBotStatusReportQueryHandler` fills it with the bot clock's `now`), printed by `bots/cli/bot_status_reports.py` → `bot_show_grids_report`, and in JSON by `bots/contracts/grid_ladder_payload.py` → `ladder_payload`. Read from the bot's file, no exchange call; the maker fee rate is recorded when a run starts (`BOT-194`), so the net columns are filled for a run that recorded one and blank for an older file; the Futures liquidation price is not in the file, so its row says so.
`bot order <id>` (`BOT-187`) prints the orders the bot's file records, the Bots tab's orders table
(`BotProgress.orders` through `GetBotQuery`). The verb is `bots/cli/bot_order_verbs.py` → `OrderBotVerb`;
the report is built in `bots/cli/bot_order_reports.py` → `bot_order_report`. It is stored, not live, and asks the exchange
nothing: live open orders need an order session and are a later source behind the same report.
Design: design 038 §5.2 (`status` from a second process).

## Built: the headless host

On the headless host `operations`' `run` boots the same module with no window. What stopping does to
the bots is a shutdown policy chosen on the command line (design 038 §6.1, decision O1): leave the
orders resting, the default and what the shipped unit runs (`--on-stop leave-orders`,
`deploy/linux/sew-run.service`; `src/modules/operations/adapters/leave_orders_resting.py` →
`LeaveOrdersResting`), or stop every bot first (`src/modules/operations/adapters/stop_bots_first.py` →
`StopBotsFirst`). A restart leaves running bots `RECOVERING` until a person resumes them, or until
`run --resume-recovering` does (design 038 §6.2, decision O2;
[`06-runtime.md`](06-runtime.md)). A `HALTED` or `AWAITING_RECOVERY` bot is resumed by a person, or by
`run --resume-halted` (`EPIC-042E`, ADR 042 D13), which gives the screen's Resume and Confirm in advance. Between a stop and the next start nothing watches a stop loss or a
take profit; `EPIC-039L` closes that gap on Futures with an order resting on the exchange.
