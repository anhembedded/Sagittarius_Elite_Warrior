Status: Current

# Architecture — how the whole app is built

**Reader:** someone who needs the shape of the app before reading any one module: a new contributor, a
reviewer judging a boundary, the owner deciding where a feature belongs.
**Question it answers:** *what are the parts, who may depend on whom, and what runs where?*

Nothing is written here yet. `EPIC-041D` adds the context, container and module map, `EPIC-041G` the
runtime, crosscutting, security and quality documents. Until then the design of record is
[`../HLD/`](../HLD/README.md), marked `Historical` (see [`../README.md`](../README.md)).

## What belongs here, and what does not

| Belongs | Does not belong |
| :--- | :--- |
| The app as one system and how it meets the outside (exchange, owner, operating system) | How one module works: that is [`../MODULES/`](../MODULES/README.md) |
| The module map and the direction of every dependency, as a summary that links to the contracts | A rule stated in full: cite it from `.claude/rules/` |
| Runtime and deployment of the whole app; crosscutting concerns as a table joining topic, rule, guard and reason | The reason for one decision: that is [`../DECISIONS/`](../DECISIONS/README.md) |
| Quality goals, risks, security | Numbers about the process: [`../METRICS/`](../METRICS/README.md) |

Detail lives at the lowest level that owns it: code first, then the module document, then here. An
upper level summarises and links (decision D2).

## Layout and naming

Two levels (decision D3): the app is the system, a module is a component. Files are named for the
reader's question, never for an arc42 section number, and a section with nothing to say is left out.
Example names: `context.md`, `module_map.md`, `runtime.md`, `crosscutting.md`.

## Diagrams

PlantUML (decision D8). Each diagram answers one question and names its source: the `.puml` files sit
in `diagrams/` beside the document that embeds them, and the document states the question above each
picture. Mermaid stays for short diagrams in tasks and epics.

## Linking a document to its rule and its guard

A document says why and what shape. A rule under `.claude/rules/` says what must be done. A guard or
the gate holds the rule. A normative statement in a document cites the rule clause that holds it and
does not restate it. A rule clause that encodes a design choice links back with a `Why:` to the
document that explains it (decision D1; `EPIC-041B` makes `scripts/rule_integrity/` check both
directions).

Worked example: the desktop shell. [`HLD §11`](../HLD/11_desktop_workbench.md) explains why the app is
one `QMainWindow` with a workbench host per mode. The clause at
[`ui-presentation-rule.md`](../../.claude/rules/ui-presentation-rule.md) (the line beginning "The app is
one `QMainWindow` shell") states what must be done and cites HLD §11. The guard
[`test_workbench_conformance.py`](../../tests/integration/presentation/ui/test_workbench_conformance.py)
holds it. Changing the shape of the shell touches all three in one pull request.
