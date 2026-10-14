Status: Current

# Decisions — why it was decided

**Reader:** someone about to change, or to question, something that was chosen on purpose.
**Question it answers:** *why is it like this, and what was rejected?*

Decisions are **immutable once accepted**: a new record supersedes an old one and links to it; the old
one is never edited to agree with the new (decision D5). This folder is the single entry point. It
does not hold the records yet: the 24 `DECISION_*.md` records stay in their epic folders, where rules,
tasks and documents already cite them. `EPIC-041C` adds a generated index here and a guard for it.

## What belongs here, and what does not

| Belongs | Does not belong |
| :--- | :--- |
| The index of every decision, proposal and epic design record, generated from the files | A copy of a decision's text: link to the record |
| The rule for writing one (the template is `.claude/templates/decision.md`) | The current shape of the system: [`../ARCHITECTURE/`](../ARCHITECTURE/README.md) and [`../MODULES/`](../MODULES/README.md) |

## Layout and naming

`DECISIONS/README.md` (this file) and, from `EPIC-041C`, a generated `INDEX.md` with one row per record:
id, date, title, status, the epic it lives in, and the record it supersedes. Records keep their name
`DECISION_{date}_{slug}.md` and their place under `Tasks/epics/EPIC-{nnn}_{slug}/`.

## Diagrams

A decision record rarely needs one. When it does, PlantUML with the source under `diagrams/` beside the
record (decision D8), or a short mermaid block as tasks and epics use.

## Linking a decision to its rule and its guard

A decision gives the reason; the rule states the obligation it created; a guard holds the rule. The
rule clause carries a `Why:` link to the record, and the record's "Implementation evidence" table
names the rule or guard (decision D1).

Worked example: [`DECISION_2026-10-14_documentation_philosophy.md`](../../Tasks/epics/EPIC-041_documentation_standard/DECISION_2026-10-14_documentation_philosophy.md)
decides (D5) that a description changes in the pull request that changes the code. The rule clause
that holds it is the "Docs touched" clause of
[`task-execution-rule.md`](../../.claude/rules/task-execution-rule.md), and the "Docs touched" section
of the task and pull-request templates is how a reviewer sees it. The record's "Implementation
evidence" table names the task that delivered them.
