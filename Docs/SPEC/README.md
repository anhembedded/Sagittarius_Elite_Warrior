# SPEC — what the application does, one use case per file

This is the **behaviour** specification: what a person does with this app, step by step, and
what the app must do in return. It is the third of three documents and the only one written
from outside the code:

| Document | Question it answers | Written from |
| :--- | :--- | :--- |
| [`Docs/HLD/`](../HLD/README.md) | how is the system divided, and what may depend on what? | the architecture |
| [`Docs/SDD/`](../SDD/README.md) | what shape does each contract have, and which thread may call it? | the design |
| **`Docs/SPEC/`** (this) | **what does a person do, and what must happen?** | **the user's side of the screen** |

## Why this exists, given two documents already mention user stories

Neither is a specification, and the gap showed the day Phase 0 of `EPIC-025` had to be
accepted. Its acceptance test was four sentences inside a task file — *"Trading loads history,
Dev Board's Start Live syncs and streams, Data Management syncs a symbol, CLI `sync`/`stream`
work"* — written once, for one phase, and impossible to re-run later because nothing said what
"loads history" means precisely enough to check twice.

- [`Docs/PROJECT_INTENT_AND_USER_STORIES.md`](../PROJECT_INTENT_AND_USER_STORIES.md) is the
  product **intent**: who this is for and which direction it goes. It is grouped by priority and
  epic, and it is deliberately not a checklist.
- [`Tasks/UserStory_Propose.md`](../../Tasks/UserStory_Propose.md) holds `US-01`… — **proposals**.
  A user story there is something somebody wants; a `SPEC` here is something the app does, or is
  specified to do, with the flow spelled out and the evidence named.

**A `US-xx` becomes a `SPEC-xxx` when it is specified**, and the SPEC then outlives it: the story
is why, the spec is what. Neither file is a copy of the other — the SPEC names its `US` in
"Origin" and that is the only link.

## The convention

- One use case, one file: `SPEC-<three digits>_<slug>.md`. Ids are permanent and never reused,
  the way `BUG-`, `PRO-` and `EPIC-` ids are in this repository.
- Every file follows [`SPEC-000_template.md`](SPEC-000_template.md). The template is not a
  suggestion, and it is not enforced by good intentions either: a guard under
  `tests/unit/architecture/` fails on a SPEC missing a required section, on a duplicate id, on an
  id that is not in the index below, and on a **test path a SPEC cites that does not exist** —
  which is the whole point of the "Proven by" section and the way this directory avoids becoming
  prose nobody re-reads. Find it by name with
  `ls tests/unit/architecture/ | grep spec`, the way every other ratchet in that directory is
  found.
- **Status is per file and honest.** ✅ built and proven · 🟡 partly built (the file says which
  step is missing) · 🔵 specified, not built. A SPEC may be written before the code — that is
  the useful case — but it may not claim to be built when it is not.
- Language: English, book register, like every `.md` here (`ONBOARDING.md` §10).

## Index

| Id | Use case | Actor | Status |
| :-- | :--- | :--- | :-: |
| [SPEC-001](SPEC-001_sync_a_symbols_history.md) | Bring a symbol's candle history up to date | trader, operator | ✅ |
| [SPEC-002](SPEC-002_watch_the_live_market.md) | Watch the live market for chosen symbols | trader | ✅ |
| [SPEC-003](SPEC-003_check_the_exchange_connection.md) | Check that the app can reach the exchange | trader, operator | ✅ |
| [SPEC-004](SPEC-004_enable_and_disable_live_trading.md) | Turn live trading on, and off | trader | ✅ |
| [SPEC-005](SPEC-005_place_a_manual_order.md) | Place one order by hand | trader | ✅ |

Planned, and numbered here so the ids are reserved rather than invented twice:

| Id | Use case | Status |
| :-- | :--- | :-: |
| SPEC-006 | Cancel one open order | 🔵 |
| SPEC-007 | Stop everything at once (emergency stop) | 🔵 |
| SPEC-008 | Inspect what is stored, and repair a gap | 🔵 |
| SPEC-009 | Run a backtest over stored history | 🔵 |
| SPEC-010 | Arm a strategy on a symbol, and disarm it | 🔵 |

## How a SPEC is used

- **Accepting a phase or a pull request.** The "Proven by" section is the acceptance test. Where
  it says *the user runs it*, that is a human step and the pull request is not done without it —
  `EPIC-025`'s epic README ends every phase with the app running, not with a green gate.
- **Reviewing.** A change that alters a flow updates its SPEC in the same pull request, the way
  `Docs/SDD/05_module_contracts.md` takes a contract deviation
  (`.agents/Skills/epic-025.prompt.md` §3 step 10).
- **Writing a new feature.** Write the SPEC first at 🔵, build, then move it to ✅ with the test
  paths filled in. A 🔵 SPEC with no "Proven by" is a plan; a ✅ one without it is a lie, and the
  guard treats it as one.
