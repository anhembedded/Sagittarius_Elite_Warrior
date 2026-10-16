Status: Current

# Modules — how one module works

**Reader:** someone about to change a module, or to build against it, who needs its parts, its states,
its threads and its clocks in one place. **Question it answers:** *how does this module work, and what
must I not break?*

One module, one file: `Docs/MODULES/<module>.md`, never inside `src/` (decision D3). Two modules have
one: `bots`, as a skeleton that `EPIC-040` and `EPIC-041E` fill ([`bots.md`](bots.md)), and `alerting`,
the module's design before most of it is built, marking each fact built or planned
([`alerting.md`](alerting.md), `EPIC-036`). The other five modules (`backtesting`, `market_data`,
`operations`, `strategy`, `trading`) each get theirs as their own task, with this template.

## What belongs here, and what does not

| Belongs | Does not belong |
| :--- | :--- |
| The seven views below, for one module | The app's shape or other modules' internals: [`../ARCHITECTURE/`](../ARCHITECTURE/README.md) |
| Reasons and trade-offs the code cannot show, with a link to the decision record | The decision's full argument: [`../DECISIONS/`](../DECISIONS/README.md) |
| `file:line` citations to the code that owns each fact | A copy of the code, a rule, or a contract's member list: cite them |

A view with nothing to say is left out, not filled with "N/A" (decision D7). A fact appears in exactly
one view.

## The module-doc template

Every module document opens with `Status:` (see [`../README.md`](../README.md)), its reader and the one
question the module answers, then the views in this order. Under each heading, a `Filled by:` line names
the task that completes the view until it is complete, and is removed then.

| # | View | Answers | Facts come from |
| :-: | :--- | :--- | :--- |
| 1 | Context | What does the module depend on, who depends on it, and which commands and events cross its edge? | `module.py` (`dependencies`), the module's `contracts/` package, the boundary guards under `tests/unit/architecture/boundaries/` |
| 2 | Components | Which classes do the work, and which one calls which? | The module's `application/`, `domain/`, `adapters/` and `composition/` packages; the contract ports under `contracts/` |
| 3 | State machines | Which states exist, which events move between them, and which moves are refused? | The `*_fsm_matrix.py` transition tables in `domain/` |
| 4 | Sequences | What happens, step by step, on the journeys that matter (start, fill, stop, restart)? | The use-case handlers and the services they call, read in order |
| 5 | Data model | What is stored, in what shape, where, and what owns each field? | The aggregate and value objects in `domain/`, the store port in `contracts/`, the adapter that writes it |
| 6 | Threading and deployment | Which thread runs what, what is shared, and what happens in a second process? | The thread adapters in `adapters/`, `module.py` `boot()`, the instance-access check |
| 7 | Timing | Which constants decide when something is stale, retried, paused or given up, and what are their values? | The named constants beside the code that uses them |

## Generated, not hand-kept

State machines and timing tables are **generated from code** (decision D4): the transition table and
the constants are the truth, a hand-drawn copy drifts. The task that fills view 3 or 7 adds the
generator and the guard that compares its output with the document, as `scripts/render_exit_codes.py`
and `tests/unit/support/cli_host/test_exit_code_table.py` do for `OPERATIONS/exit_codes.md`. Until that
task lands, the view is a summary that cites the table or constant it will be generated from.

## Diagrams

PlantUML, sources under `Docs/MODULES/diagrams/` (decision D8), named `<module>-<view>.puml`. Each
diagram answers one question and the document states it above the picture. No diagram is required to
fill a skeleton view: a paragraph that cites the code is enough until a picture answers something the
paragraph cannot.

## Linking a module document to its rule and its guard

A module document explains shape and reasons; it does not restate what a rule requires. Where the
module's design encodes a rule (the instance lock, the order pacer, the one-writer thread), the
document cites the rule clause, and the clause links back with `Why:` (decision D1).

Worked example: the module boundary. `bots.md` view 1 says the shell imports only `module.py`. The
file's own docstring states the rule ("the only file under `modules/bots/` that `shell/` may
import"), and the boundary guards under `tests/unit/architecture/boundaries/` hold it. A change to what
the module exposes touches the document, the docstring and the guard in one pull request.

## Keeping it true

A task that changes a module's shape, a boundary, a lifecycle, a thread or a timing constant updates
that module's document in the same pull request, and says so under "Docs touched" in the task and the
pull request (`.claude/rules/task-execution-rule.md`).
