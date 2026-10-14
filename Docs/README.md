Status: Current

# Docs — which file answers which question

Start from the question, not from the folder. One fact lives in one place (decision D2 of
[`DECISION_2026-10-14_documentation_philosophy.md`](../Tasks/epics/EPIC-041_documentation_standard/DECISION_2026-10-14_documentation_philosophy.md));
a document that needs it links there.

## The map

| You want to know | Go to | Kind |
| :--- | :--- | :--- |
| What the app must do, one use case per file | [`SPEC/`](SPEC/README.md) | Description |
| How the system is built: context, module map, runtime, crosscutting concerns | [`ARCHITECTURE/`](ARCHITECTURE/README.md) | Description |
| How one module works: its components, states, sequences, data, threads and timing | [`MODULES/`](MODULES/README.md) | Description |
| Why a decision was taken, and what it rejected | [`DECISIONS/`](DECISIONS/README.md) | Decision |
| How to run and operate the host | [`OPERATIONS/`](OPERATIONS/headless_runbook.md) | Operations |
| What a word means | [`VOCABULARY/`](VOCABULARY/README.md) | Description |
| What went wrong and why the gate missed it | [`CASE_STUDIES/`](CASE_STUDIES/README.md) | Description |
| What the process numbers say | [`METRICS/`](METRICS/README.md) | Generated data |

The three kinds have three lifecycles (decision D5). A *description* is true of `master-warrior` and
changes in the pull request that changes the code. A *decision* is immutable once accepted; a new
record supersedes it. An *operations* document is true of what runs on a server.

## Every document has a status

The first line of every `.md` under `Docs/` is one of:

| Line | Meaning |
| :--- | :--- |
| `Status: Current` | Someone vouches that it is true of `master-warrior` |
| `Status: Superseded by <link>` | A newer document replaces it; read that one |
| `Status: Historical` | Kept for its record, not vouched for. Do not build on it without checking the code |

A document with nothing to vouch for it is `Historical`, never `Current` (decision D6). A `SPEC`'s own
`- **Status:**` bullet is a different thing: it says how much of the use case is built.

## Being replaced

`HLD/`, `SDD/` and `Diagrams/` predate this layout. They are marked, not moved; `EPIC-041D` and
`EPIC-041I` decide what each file becomes. Until then, this is what each still holds that nothing
else does:

| Tree | Still the only home of | Status |
| :--- | :--- | :--- |
| [`HLD/`](HLD/README.md) | The criteria for cutting a module (§1), the context map (§2), module contracts (§3), surfaces and contribution points (§4), the Engine/application split (§5), the build-or-buy survey (§7), the test strategy (§10) and the desktop workbench contract (§11, which `ui-presentation-rule.md` cites) | §11 `Current`, the rest `Historical` |
| [`SDD/`](SDD/README.md) | The contribution mechanism (§2), ownership, lifetime and threads (§3), boot and configuration writes (§4), and the measured Phase 0 baselines (§6) | `Historical` |
| [`Diagrams/`](Diagrams/architecture.md) | Three design notes for shipped mechanisms: `correlation_id`, symbol market metadata, tick provisional/commit (all in Vietnamese). `architecture.md` and `ui_architecture.md` are superseded | Mixed |
| [`PROJECT_INTENT_AND_USER_STORIES.md`](PROJECT_INTENT_AND_USER_STORIES.md), [`SCREEN-REGISTRY-PATTERN/`](SCREEN-REGISTRY-PATTERN/README.md) | Product intent as of the first rounds; the screen-registry design | `Historical` |

## Writing a document

Name the reader and the question first. Leave out a section that has nothing to say. State a rule by
citing it, never by copying it. Each home folder's `README.md` gives its layout. A task that changes a
module's shape, a boundary, a lifecycle, a thread or a timing constant updates that module's document
in the same pull request and lists it under "Docs touched" (`.claude/rules/task-execution-rule.md`).
