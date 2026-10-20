Status: Current

# `bots` — 8. Concepts

*Which techniques and patterns does the module apply, and why; what is stored, in what shape?*

The picture of the types is [`diagrams/05-domain.puml`](diagrams/05-domain.puml).

## Built: the bot aggregate

A bot is an aggregate: a `BotDefinition` (name, kind, venue, symbol and a string-valued `config`) and a
`BotLifecycle` (state, run start, the state it is recovering from), `bots/domain/bot.py` →
`BotDefinition`, `BotLifecycle`, `Bot`. Its state changes only through the lifecycle table
([`state-machines.md`](state-machines.md)); the enum, the events and the table live in one file
(`code/quality.md` §3). The store port is `IBotStore`, which hands out a `StoredBot`: the bot plus its
kind's runtime as plain JSON (`bots/contracts/i_bot_store.py` → `IBotStore`, `StoredBot`).

## Built: what a Grid adds

A Grid's parameters are `GridParams` (`bots/domain/grid/grid_params.py` → `GridParams`), parsed from
the definition's `config`, and what it has done so far is `GridRuntime`, with one `RuntimeLevel` per
level and at most one `LevelOrder` on each (`bots/domain/grid/grid_runtime.py` → `GridRuntime`,
`RuntimeLevel`, `LevelOrder`), and on a position venue the protective stops saved with it
(`GridRuntime.protective_stops`, `bots/domain/grid/protective_stop.py` → `ProtectiveStop`), written
only when there are some. The runtime also records the account's maker fee rate the run's start read
(`GridRuntime.maker_fee`, `bots/application/kinds/grid/start/grid_start_sequence.py` →
`GridStartSequence.run`; `BOT-194`), kept by a resume and absent from a file an earlier build wrote: it
is what a reader with no exchange (the Bots tab's Ladder, `bot show`) takes the net after fees from,
and it is the rate of the run's start, not today's. A level's own lifecycle is the second table in
[`state-machines.md`](state-machines.md). An order is the bot's when its client order id carries the
bot's tag, which is how the reconcile finds and adopts it after a restart.

## Built: storage

Each bot is one JSON file, `state/bots/<id>.json`, under the data root
(`bots/composition/state_bindings.py` → `bots_directory`), written atomically by `JsonBotStore`
(`bots/adapters/persistence/json_bot_store.py` → `JsonBotStore`). A file this build cannot read is
reported, not dropped (`bots/contracts/i_bot_store.py` → `RefusedBotFile`), and the host's pre-flight
check fails on it (`BotsModule.declare_operations`). The plan a user applies from a file is
`AppliedPlan` (`bots/contracts/applied_plan.py` → `AppliedPlan`).

**The halt-recovery ledger** (`EPIC-042B`). The lifecycle of the bot record carries `recovery_attempts`, a list of `{code, at}`, one entry per automatic recovery attempt (`bots/adapters/persistence/bot_record_codec.py` → `encode`, `decode`; `bots/domain/bot.py` → `BotLifecycle`). It is written inside `lifecycle` with no new `schema_version` and read as empty when the key is missing; a damaged list refuses the file by name, because reading it as empty would hand a flapping bot a fresh budget. Entries older than the longest effective window are dropped on every write and the list is capped (`bots/domain/halt_recovery_policy.py` → `MAX_RECORDED_ATTEMPTS`). It is the bot's own account, kept with the bot and not in the Grid's runtime, because the mechanism is every kind's.

**The loss cap's record** (`EPIC-026L`). `state/loss_cap.json`, schema `sew.loss-cap-record/1`: the UTC day, each
bot's `{run_started_at, baseline, last, banked}` for that day (decimals as text) and, when the cap has
tripped, the trip `{reason, at, day, loss, figure, detail}` (`bots/adapters/file_loss_cap_store.py` →
`RECORD_SCHEMA`, `FileLossCapStore`). It holds the bots' day results, which the health snapshot must not
(`LossCapStatus.payload` leaves them out), so the file is read by the host and by no report. A trip
outlives the day: the owner's acknowledgement is what ends it. A record this build cannot read is
refused by name with none of its content.

**Built (`EPIC-040C`).** A backtest's parameters are a copy of a bot's *saved* plan, never the bot's own: `bots/domain/backtest/sandbox_plan.py` → `SandboxPlan` (the kind, venue and symbol; the config being tried; the saved config it was copied from; the source bot). It names what differs (`changed_fields`) and is reset to its source (`reset`); an edit returns a new plan. `bots/ui/backtest/sandbox_session.py` → `SandboxSession` copies a selected bot's saved plan unless the sandbox has edits, and then asks once before discarding them (a copy the person declined is not asked about again). `bots/ui/backtest/sandbox_judge.py` → `judge_sandbox` judges it by the kind's own `IBotKind.validate` with no account and no view of the account's open orders, so the symbol's rules (tick, step, minimum notional) and the venue's limits still refuse a bad plan; `sandbox_line` says of the two checks that need the account that they were "Not checked in a simulation". Two inputs are the account's even so, supplied by the caller and read by the sandbox from nowhere: the fees in the terms are the account's fee tier (the break-even verdicts use them, as a live run would), and on a position venue the risk facts carry the account's current symbol setting; a position venue with no risk facts answers `LIQUIDATION_FACTS_NOT_READ` instead of dropping its liquidation checks in silence. Nothing in these files can send a command, open an order session or read an account (`tests/unit/architecture/test_sandbox_sends_no_command.py`). No screen shows a sandbox until `EPIC-040D`.

**Planned.** `EPIC-040G` the strategy bot's config.
