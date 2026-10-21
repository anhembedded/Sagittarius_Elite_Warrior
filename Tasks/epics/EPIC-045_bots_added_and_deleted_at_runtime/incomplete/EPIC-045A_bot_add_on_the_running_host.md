# EPIC-045A — `bot add` creates a DRAFT bot on the running host

**Status:** 🟡 In progress
**Source:** the owner, 2026-10-21, quoted in the [epic README](../README.md)
**Risk:** 🟡 — a new document key crosses the command directory's trust boundary
**Complexity:** M — one verb on the `bot edit` path
**Epic:** [EPIC-045](../README.md)
**Depends on:** None

---

## 1. Context and problem
Adding a bot designed in the desktop app today costs a host restart (`bot apply` exits 3 beside a running host).

## 2. Acceptance criteria
- [ ] `bot add plan.json [--name X]` on a running host creates one DRAFT bot from the entry, answers its id, and starts and places nothing.
- [ ] A plan with several entries needs `--name`; a name that is not in the plan, a duplicate (name, venue), an unknown kind or a parameter the kind cannot read is refused in words and creates nothing.
- [ ] A hostile document (a key, a name or a value outside its shape, an `entry` on another action, a venue typed) is `malformed`; an older host rejects the new word without effect.

## 3. Design
See [the decision record](../DECISION_2026-10-21_add_and_delete_on_the_running_host.md) D3, D6..

## 3a. Reuse
Used `ICommandDispatcher` with the tab's `CreateBotCommand`; `parse_plan` for the file; `ParameterSetting` and `BotCommandLock` as `bot edit` does. Not used: `PlanApplier` (it records a desired state `add` must not).

## 4. Changes, per file
| `core/contracts/host_control.py`, `operations/contracts/host_command.py`, `operations/application/host_command_codec.py` | the `add` word and the `entry` key |
| `bots/contracts/host_bot_requests.py`, `bots/application/use_cases/add_bot_for_host/` | the host request and its handler |
| `bots/composition/command_bindings.py`, `bots/cli/bot_control_verbs.py`, `bots/cli/bot_verbs.py`, `config/cli_commands.json` | the table row, the verb, the CLI word |

## 5. Testing
Unit: codec, handler, verb. Integration: host-control world beside a running host. Architecture guards.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` §6 (045E), `Docs/MODULES/bots/05-building-blocks.md`, `Docs/MODULES/operations` if it lists the actions.
