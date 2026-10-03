# EPIC-029B — A `bots` module holds bots: identity, kind seam, lifecycle and a crash-safe store

**Status:** 🔵 Backlog
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

- [ ] **Registration.** `src/modules/bots/` exists with `module.py` (`module_id = "bots"`) and is
  listed in `MODULES` (`src/shell/modules.py`).
  - Its `dependencies` equal the contracts it imports.
  - Every architecture guard passes, the list in ADR §1.6 among them.
- [ ] **The aggregate.** `Bot` holds `BotId`, `name`, `kind`, `venue`, `symbol`, `config`, `state`,
  `created_at` and `run_started_at`, and is immutable; each change returns a new value.
  - `run_started_at` is set on each `start` from DRAFT or STOPPED, and kept across HALTED,
    RECOVERING and STOPPING (ADR D6, review round 2). Trading derives the inventory per run from it.
  - `BotId` is 6 characters of `[a-z0-9]` and is unique across the store. A collision on creation
    retries.
- [ ] **The kind seam.** `IBotKind` is an ABC with:
  - `kind_id`;
  - `validate(config, terms) -> Verdicts`;
  - `executor_factory`;
  - `overlay(config, state)`.

  Its docstring lists the extension cases: signal, DCA, Futures Grid and trailing Grid. Only Grid
  implements it, in `EPIC-029C` and `EPIC-029E`.
- [ ] **The lifecycle table.** `bot_lifecycle_fsm_matrix.py` declares every transition of ADR §3.1, as
  revised in round 1.
  - A table-driven test walks every declared transition.
  - Every undeclared pair raises `InvalidBotTransition`, naming the state and the event.
- [ ] **The store.** `JsonBotStore` writes `state/bots/<id>.json` atomically (tmp + `replace`).
  - A crash simulated between the write and the `replace` leaves the previous file intact.
  - A file with an unknown `schema_version` is refused with a named error. It is never silently
    dropped.
- [ ] **Restart** follows ADR D12:
  - a bot saved as RUNNING or PAUSED loads as RECOVERING;
  - a bot saved as STARTING loads as HALTED (review round 2);
  - a bot saved as STOPPING loads as STOPPING;
  - a bot saved as HALTED loads as HALTED.
- [ ] **Every event the tasks use is declared.** `edit` (DRAFT and STOPPED) and `delete` (DRAFT
  and STOPPED only) are in the table. A test proves that `delete` from any other state raises.
- [ ] **One running bot.** Starting a second bot while one is RUNNING is refused with
  `ONE_RUNNING_BOT_DURING_FAST_TRACK` (D20).
- [ ] **Documentation.** The documents name the new module:
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

## Resume (optional; while unfinished)
