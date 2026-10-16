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
`RuntimeLevel`, `LevelOrder`). A level's own lifecycle is the second table in
[`state-machines.md`](state-machines.md). An order is the bot's when its client order id carries the
bot's tag, which is how the reconcile finds and adopts it after a restart.

## Built: storage

Each bot is one JSON file, `state/bots/<id>.json`, under the data root
(`bots/composition/state_bindings.py` → `bots_directory`), written atomically by `JsonBotStore`
(`bots/adapters/persistence/json_bot_store.py` → `JsonBotStore`). A file this build cannot read is
reported, not dropped (`bots/contracts/i_bot_store.py` → `RefusedBotFile`), and the host's pre-flight
check fails on it (`BotsModule.declare_operations`). The plan a user applies from a file is
`AppliedPlan` (`bots/contracts/applied_plan.py` → `AppliedPlan`).

**Planned.** `EPIC-040C` adds the sandbox copy of a plan; `EPIC-040G` the strategy bot's config.
