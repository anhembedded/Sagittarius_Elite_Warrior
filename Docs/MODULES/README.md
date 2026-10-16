Status: Current

# Modules — how one module works

**Reader:** someone about to change a module, or to build against it, who needs its parts, its states,
its threads and its clocks in one place. **Question it answers:** *how does this module work, and what
must I not break?*

**One module, one folder:** `Docs/MODULES/<module>/`, never inside `src/`, laid out in arc42's order
([decision of 2026-10-16](../../Tasks/epics/EPIC-041_documentation_standard/DECISION_2026-10-16_module_docs_one_folder_arc42.md),
D1–D3). Two modules have a design today:

| Module | Design | State |
| :--- | :--- | :--- |
| `alerting` | [`alerting/`](alerting/README.md) | The pilot of the folder layout; each fact marked Built or Planned (`EPIC-036`) |
| `bots` | [`bots.md`](bots.md) | A single-file skeleton; moves to `bots/` in `EPIC-041E` |

The other five modules (`backtesting`, `market_data`, `operations`, `strategy`, `trading`) each get
theirs as their own task, with this template.

## What belongs here, and what does not

| Belongs | Does not belong |
| :--- | :--- |
| The files below, for one module | The app's shape or other modules' internals: [`../ARCHITECTURE/`](../ARCHITECTURE/README.md) |
| Reasons and trade-offs the code cannot show, with a link to the decision record | The decision's full argument: [`../DECISIONS/`](../DECISIONS/README.md), or the record in its epic |
| Citations by path and symbol to the code that owns each fact: `` `<path>.py` → `<symbol>` `` | A line number: it moves with every unrelated edit. A copy of the code, a rule, or a contract's member list: cite them |
| A link to the use case | The use case itself: [`../SPEC/`](../SPEC/README.md) |
| A term used as defined | The term's definition: [`../VOCABULARY/`](../VOCABULARY/README.md) |

A file with nothing to say is left out, never filled with "N/A" (decision D7 of 2026-10-14). A fact
appears in exactly one file; another file links to it (D2 of 2026-10-14).

## The folder

The numbers are arc42's section numbers and are **fixed**: a section with no content is left out, and
the files after it keep their numbers. `05-building-blocks.md` is always §5, whichever module you open.

| File | Required | arc42 | Answers | Facts come from |
| :--- | :-: | :-: | :--- | :--- |
| `README.md` | ✅ | — | What is this module, who reads which file, what is Built and what is Planned? One screen | The files below |
| `01-goals-use-cases.md` | | 1 | What must the module achieve, and for which use case? | Links to [`../SPEC/`](../SPEC/README.md); never a copy |
| `02-constraints.md` | | 2 | What is the module not free to choose (platform, dependency, rule)? | The rule clause or decision that imposes each one |
| `03-context.md` | ✅ | 3 | What does the module depend on, who depends on it, and which commands, queries and events cross its edge? | `module.py` (`dependencies`), the module's `contracts/` package, the boundary guards under `tests/unit/architecture/boundaries/` |
| `04-solution-strategy.md` | | 4 | Which few choices shape everything else, and in which order is it built? | The module's decision records |
| `05-building-blocks.md` | ✅ | 5 | Which components do the work, which one calls which, and what are the domain types and contracts? | The module's `application/`, `domain/`, `adapters/`, `composition/` and `contracts/` packages |
| `06-runtime.md` | ✅ | 6 | What happens, step by step, on the journeys that matter? | The use-case handlers and the services they call, read in order |
| `07-deployment.md` | ✅ | 7 | Which thread runs what, what is shared, which files it writes, what a second process does, how the host runs it? | The thread adapters, `module.py` `boot()`, the instance-access check, `deploy/` |
| `08-concepts.md` | | 8 | Which techniques and patterns does the module apply, and why; what is stored, in what shape? | The domain value objects, the store port and its adapter; the pattern each one names |
| `09-decisions.md` | ✅ | 9 | Which decisions shaped the module? | An index: one line and a link per record. Never a copy of a record |
| `10-quality.md` | | 10 | Which quality scenarios must hold, and which constants decide when something is stale, retried, paused or given up? | The tests that prove each scenario; the named constants beside the code that uses them |
| `11-risks-debt.md` | | 11 | What is known to be weak, and which task removes it? | The tasks and bug reports that track each item |
| `state-machines.md` | | — | Which states exist, which events move between them, and which moves are refused? | The `*_fsm_matrix.py` transition tables in `domain/` |
| `diagrams/*.puml` | | — | The pictures the files above show | Drawn by hand (below) |

Every `.md` in the folder opens with `Status:` (see [`../README.md`](../README.md)); `README.md` then
names its reader and the one question the module answers. Each file opens with the question it
answers. Until a file is complete, a `Filled by:` line under its title names the task that completes
it, and is removed then.

## Diagrams: by hand, high level

A diagram is drawn by hand in PlantUML (decision D8 of 2026-10-14), kept in the module's `diagrams/`
folder as `<arc42 number>-<what it shows>.puml`, and linked from the file that explains it. Each
diagram answers one question, stated above the link. It shows components, ports and the arrows
between them, never every class. **A complex picture is split:** when one diagram needs more than
about seven boxes, or carries two journeys or two questions, it becomes several diagrams, one question
each (`05-publish-path.puml`, `05-delivery-path.puml` rather than one `05-components.puml`). A
sequence keeps to one journey; `05-building-blocks.md`'s class diagrams hold the domain types and
the contracts only, with their few defining members. A class diagram is never generated from the
code (decision D3 of 2026-10-16): a generated picture of every class answers no question.

**Tables stay generated.** The transition table of a state machine and the timing table are the code's
own data, so they are generated from it and guarded (D4 of 2026-10-14), as
`scripts/render_exit_codes.py` and `tests/unit/support/cli_host/test_exit_code_table.py` do for
`OPERATIONS/exit_codes.md`. Until the task that adds the generator lands, the table is a summary that
cites the matrix or the constant it will be generated from.

## Linking a module document to its rule and its guard

A module document explains shape and reasons; it does not restate what a rule requires. Where the
module's design encodes a rule (the instance lock, the order pacer, the one-writer thread), the
document cites the rule clause, and the clause links back with `Why:` (decision D1 of 2026-10-14).

Worked example: the module boundary. A module's `03-context.md` says the shell imports only
`module.py`. The file's own docstring states the rule ("the only file under `modules/bots/` that
`shell/` may import"), and the boundary guards under `tests/unit/architecture/boundaries/` hold it. A
change to what the module exposes touches the document, the docstring and the guard in one pull
request.

## Keeping it true

A pull request that changes `src/modules/<module>/` for a module that has a folder here changes the
folder too, or writes `No design change: <reason>` under its `## Design` section. The rule is
`commit-rule.md` §1 ("Design in step"); `scripts/check_design_in_step.py` holds it on every pull
request, and review check K10 judges whether the answer is true.

A citation names a symbol, never a line (`commit-rule.md` §1, "Citing code";
[decision of 2026-10-16](../../Tasks/epics/EPIC-041_documentation_standard/DECISION_2026-10-16_cite_code_by_symbol.md)):
`` `alerting/composition/channel_bindings.py` → `discord_channel` ``. A symbol changes only when the
code it names changes, which is when the design should be read again.
`tests/unit/architecture/test_module_docs_cite_code_by_symbol.py` fails on a line citation anywhere
in this folder and on a cited symbol that its file no longer defines.
