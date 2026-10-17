Status: Current

# `bots` — the module that runs, supervises and backtests bots

**Reader:** someone changing a bot kind, the shell every kind shares, or what the host does with
bots; someone deciding whether a bot can be left alone with real money.
**Question it answers:** *which bots exist, what is each one doing, and how does it stay correct
across a start, a fill, a stop and a restart?*

Each fact in this folder is marked **Built** (on `master-warrior`, cited by path and symbol) or
**Planned** (the task that builds it is named). Paths are from the repository root; `bots/` means
`src/modules/bots/`. The layout is the template's, [`../README.md`](../README.md); the app around
the module is [`../../ARCHITECTURE/`](../../ARCHITECTURE/README.md), whose module map `EPIC-041D`
writes. The rules this design encodes are cited where they apply: module boundaries
(`architecture-rule.md` §3), one file per lifecycle (`code/quality.md` §3), and the design kept in
step with the code (`commit-rule.md` §1, "Design in step" and "Citing code").

## Which file to read

| You want to know | Read |
| :--- | :--- |
| Who calls the module, what it calls, and which events cross its edge | [`03-context.md`](03-context.md) |
| Which components carry a command and an event, where a new kind plugs in, the domain types and contracts | [`05-building-blocks.md`](05-building-blocks.md) |
| A start, a fill, a stop, an Emergency Stop and a restart, step by step | [`06-runtime.md`](06-runtime.md) |
| Which thread runs what; a second copy of the app; the headless host | [`07-deployment.md`](07-deployment.md) |
| What a bot is made of and how it is stored | [`08-concepts.md`](08-concepts.md) |
| The decision records behind the module | [`09-decisions.md`](09-decisions.md) |
| The constants that decide when a bot waits, retries, pauses or halts | [`10-quality.md`](10-quality.md) |
| The bot lifecycle and a Grid level's lifecycle, every transition | [`state-machines.md`](state-machines.md) |

## Built and Planned, at a glance

| Part | State | Task |
| :--- | :--- | :--- |
| The bot aggregate, its store, its lifecycle and the Bots tab; the Grid on Spot | **Built** | `EPIC-029` |
| Unattended safety: the price, user-stream and sleep watches, stop retries, the boot recovery | **Built** | `EPIC-035` |
| The headless host's view of the bots: `bot` verbs, the status report, `run --resume-recovering` | **Built** | `EPIC-038` |
| The Futures venue profile and the Futures Grid | **Built** | `EPIC-039` |
| The exchange-side protective stop on Futures: placed, kept, cancelled after flat, adopted on restart | **Built** (C2 of four pull requests) | `EPIC-039L` ([`06-runtime.md`](06-runtime.md), [`state-machines.md`](state-machines.md)) |
| What a halt does with a position under that stop; the Emergency Stop's order; the mainnet gate | Planned | `EPIC-039L` C3, C4 |
| The state `AWAITING_RECOVERY`, the layered halt-recovery policy and the attempt ledger in the bot record | **Built**, not yet used by any halt | `EPIC-042B` |
| A transient halt waits in `AWAITING_RECOVERY` and recovers by itself through the Resume path; `run --resume-halted` | Planned | `EPIC-042` ([`state-machines.md`](state-machines.md), [`06-runtime.md`](06-runtime.md)) |
| The kind-neutral backtest result and simulator port; the strategy kind | Planned | `EPIC-040B`, `EPIC-040G` |
