# EPIC-029B — A `bots` module holds bots: identity, kind seam, lifecycle and a crash-safe store

**Status:** ✅ Done (2026-10-03)
**Source:** [`PRO-006`](../../../proposal/PRO-006.md), accepted by the user on 2026-10-03. The
user's words: *"Thiết kế cho nhiều bot ngay từ đầu"* ("design for many bots from the start"). The
design is in ADR D1–D4 and D20.
**Risk:** 🟡 — a new module must pass every module guard on its first commit, and the lifecycle
table becomes the contract every later task builds on.
**Complexity:** M — domain types, one FSM matrix, one store adapter, module registration and
documentation. No UI.
**Epic:** [EPIC-029](../README.md)
**Depends on:** None. It can start in parallel with `EPIC-029A`.

---

## 1. Context and problem

There is no bot entity today. A strategy is armed by a desk card, and the symbol it trades is
whatever the chart shows (`desk_strategy.py:65`). It has no lifecycle beyond arm and disarm
(`trading/contracts/i_strategy_arming_control.py:30-45`) and no identity.

## 2. Acceptance criteria

- [x] **Registration.** `src/modules/bots/` exists with `module.py` (`module_id = "bots"`) and is
  listed in `MODULES` (`src/shell/modules.py`).
  - Its `dependencies` equal the contracts it imports.
  - Every architecture guard passes, the list in ADR §1.6 among them.
- [x] **The aggregate.** `Bot` holds `BotId`, `name`, `kind`, `venue`, `symbol`, `config`, `state`,
  `created_at` and `run_started_at`, and is immutable; each change returns a new value.
  - `run_started_at` is set on each `start` from DRAFT or STOPPED, and kept across HALTED,
    RECOVERING and STOPPING (ADR D6, review round 2). Trading derives the inventory per run from it.
  - `BotId` is 6 characters of `[a-z0-9]` and is unique across the store. A collision on creation
    retries.
- [x] **The kind seam.** `IBotKind` is an ABC with:
  - `kind_id`;
  - `validate(config, terms) -> Verdicts`;
  - `executor_factory`;
  - `overlay(config, state)`.

  Its docstring lists the extension cases: signal, DCA, Futures Grid and trailing Grid. Only Grid
  implements it, in `EPIC-029C` and `EPIC-029E`.
- [x] **The lifecycle table.** `bot_lifecycle_fsm_matrix.py` declares every transition of ADR §3.1, as
  revised in round 1.
  - A table-driven test walks every declared transition.
  - Every undeclared pair raises `InvalidBotTransition`, naming the state and the event.
- [x] **The store.** `JsonBotStore` writes `state/bots/<id>.json` atomically (tmp + `replace`).
  - A crash simulated between the write and the `replace` leaves the previous file intact.
  - A file with an unknown `schema_version` is refused with a named error. It is never silently
    dropped.
- [x] **Restart** follows ADR D12:
  - a bot saved as RUNNING or PAUSED loads as RECOVERING;
  - a bot saved as STARTING loads as HALTED (review round 2);
  - a bot saved as STOPPING loads as STOPPING;
  - a bot saved as HALTED loads as HALTED.
- [x] **Every event the tasks use is declared.** `edit` (DRAFT and STOPPED) and `delete` (DRAFT
  and STOPPED only) are in the table. A test proves that `delete` from any other state raises.
- [x] **One running bot.** Starting a second bot while one is RUNNING is refused with
  `ONE_RUNNING_BOT_DURING_FAST_TRACK` (D20).
- [x] **Documentation.** The documents name the new module:
  - the vocabulary terms Bot, Bot kind, Bot lifecycle and Bot store, and the module count;
  - HLD 02 (context map) and 03 (module contracts).

## 3. Design

- **Layout** follows the `strategy` module, the smallest complete one:
  - `domain/`: `bot.py`, `bot_id.py`, `bot_lifecycle_fsm_matrix.py`, `verdict.py`;
  - `contracts/`: `i_bot_kind.py`, `i_bot_store.py`, and the read model for the UI;
  - `application/use_cases/`: `create_bot/`, `start_bot/`, `pause_bot/`, `resume_bot/`,
    `stop_bot/` and `delete_bot/`, each a command and a handler (CQRS);
  - `application/queries/`: `list_bots/` and `get_bot/`;
  - `adapters/persistence/json_bot_store.py`;
  - `composition/`: state, port and command bindings.
- **What the lifecycle table rules.** The FSM matrix is the only place transitions are declared
  (`code/quality.md` FSM cohesion). Use-case handlers ask it for the next state. They never set
  the state directly.
- **File format.** JSON with `schema_version: 1`, `definition` and `runtime`. The runtime part is
  owned by the kind and opaque to the shell.
- **Writing.** The store serialises writes per bot. The actor in `EPIC-029E` is the only runtime
  writer.
- **No Qt** below `ui/`.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/bots/**` (new) | the module, as above |
| `src/shell/modules.py` | add `BotsModule` |
| `tests/unit/modules/bots/**` (new) | domain, FSM, store and use-case tests |
| `tests/unit/architecture/allowlist_*` | nothing may be added; the new module must pass with no allowlist entry |
| `Docs/VOCABULARY/README.md`, `Docs/HLD/02_context_map.md`, `Docs/HLD/03_module_contracts.md` | the new module and terms |

## 5. Testing

- **FSM:** a table-driven unit test over every transition, plus a loop over every undeclared pair.
- **Store:**
  - round trip;
  - an atomic write with a failure injected before `replace`;
  - an unknown schema refused;
  - restart restoration per ADR D12 (RUNNING or PAUSED → RECOVERING, STOPPING → STOPPING, HALTED → HALTED).
- **Use cases:** the one-running-bot refusal, and every handler going through the FSM, tested with
  a fake store.
- **Guards:** the architecture guards on the first commit.

## Implementation notes (written when done)

**Evidence, per criterion** (all from the fast checks of PR1; the full gate is the PR's GitHub Actions run):

| Criterion | Evidence |
| :--- | :--- |
| Registration | `BotsModule` in `MODULES` (`src/shell/modules.py`); `tests/unit/architecture` green, `test_module_declarations.py` included, no allowlist entry added |
| Aggregate | `tests/unit/modules/bots/domain/test_bot.py`: immutability, `run_started_at` stamped from DRAFT/STOPPED and kept through HALTED → resume → RECOVERING → STOPPING |
| Kind seam | `contracts/i_bot_kind.py` (docstring lists signal, DCA, Futures Grid, trailing Grid); Grid implements it in `EPIC-029C` |
| Lifecycle table | `test_bot_lifecycle_fsm_matrix.py`: the table equals an independently typed copy of ADR §3.1, every declared cell is walked, every undeclared pair raises naming state and event |
| Store | `tests/integration/modules/bots/contracts/test_json_bot_store.py`: the contract suite on disk, a crash injected at `Path.replace` leaves the old file byte-identical, unknown `schema_version`, bad JSON and a misnamed file are refused by name |
| Restart | `test_bot.py::test_restart_follows_d12`, `test_json_bot_store.py::test_a_restart_through_the_real_store_follows_d12`, `test_bot_use_cases.py::test_restore_applies_d12_...` |
| Events declared | `delete` from every state but DRAFT/STOPPED raises (matrix, aggregate and use-case tests) |
| One running bot | `test_bot_use_cases.py::test_a_second_bot_cannot_start_while_one_is_active` over all seven active states |
| Documentation | `Docs/VOCABULARY/README.md` (five modules, a `bots` section), HLD 02 (diagram, distillation, integration row), HLD 03 (`bots` contracts) |

**Decisions made while building, and why:**

- **`app_restart` is the restart rule.** Restoring a bot is applying the table's `app_restart` cell, so D12 is declared in the matrix, not in a second `if` chain. `BotRestoreService` runs it at `boot()` and saves only changed bots.
- **`reconcile_ok → PRIOR`.** The table's "prior (RUNNING or PAUSED)" needs memory, so `BotLifecycle.recovering_from` records it on entering RECOVERING. A RECOVERING bot with nothing recorded (a hand-edited file) refuses `reconcile_ok` instead of guessing.
- **`delete → REMOVED`** is a declared target, not a state: a removed bot has no next value, so `Bot.apply(DELETE)` raises and `require_deletable()` is the check.
- **"One running bot" counts every state but DRAFT and STOPPED**, plus any file the store refused. A HALTED, RECOVERING, STOPPING or ERROR bot may still own orders, a lease or a budget, and an unreadable file's state is unknown.
- **The store names refused files** (`BotStoreReading.refused`) instead of raising on the first. One bad file never hides the others, and the bot behind it is never silently dropped.
- **An `edit_bot` use case was added** to the six listed. The `edit` event is in the table and `EPIC-029F` needs it. Kind, venue and symbol cannot be edited, because the orders, lease and derived inventory hang on them.
- **`IBotClock`** is a port with a verified fake and a contract suite (UTC-aware). `created_at` and `run_started_at` are facts trading will derive inventory from, so a test must be able to pin them.
- **`IBotExecutor` and `IBotExecutorFactory` are a seam only.** Each method asks the actor to begin, and the outcome arrives as a lifecycle event. Nothing binds an executor or a kind yet; `EPIC-029E` does.
- **Start's other preconditions** (venue enabled, no REFUSED verdict, lease, budget) need trading's ports and the kind's terms. They arrive with `EPIC-029E`, which also turns STARTING into orders. Until then nothing in the UI dispatches `StartBotCommand` (the tab is `EPIC-029F`, after `EPIC-029E`).
- **`dependencies = ["trading"]`** since `EPIC-029C`: the planner reuses trading's `OrderQuantityRoundingPolicy`.

## Resume (optional; while unfinished)
