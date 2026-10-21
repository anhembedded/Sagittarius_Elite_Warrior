# EPIC-045A — `bot add` creates a DRAFT bot on the running host

**Status:** ✅ Done (2026-10-21)
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

## Implementation notes (written when done)
Built in the first PR of the epic. Decisions taken on the way, all in the [decision record](../DECISION_2026-10-21_add_and_delete_on_the_running_host.md): D3 (the `add` word, the `entry` key, the fixed subject `new-bot`), D6 (the closed shape of the entry). The brief said the bot lands "DRAFT, or STOPPED for a mainnet venue": no code path creates a STOPPED bot (`CreateBotCommandHandler` saves `Bot.draft`), so it lands DRAFT everywhere; asked as O2.
A real bug met and fixed on the way: `TradingVenue` is a `str` enum, so `isinstance(venue, str)` in the handler read a valid venue as a refusal sentence; the unit tests caught it.
Evidence: handler tests (`tests/unit/modules/bots/application/test_bot_add_for_the_host.py`), codec tests (`tests/unit/modules/operations/application/test_host_command_codec_add_delete.py`), the verb tests (`tests/unit/modules/bots/cli/test_bot_add_and_delete_verbs.py`), the composed-app journey (`tests/integration/modules/bots/test_bot_add_and_delete_on_the_running_host_on_the_fake_exchange.py`, which also proves the handlers are bound). Mutation-checked: the duplicate-venue clause, the lock, the credential-name refusal and the venue refusal each turn a test red when removed.
Not run: the VPS, a real second process (`test_control_of_a_running_host_process.py` has no add case); the `-Full` run on the PR head.

## Resume
None: merged in #692 (b4127df); the `-Full` run on its head 0ec9b44 was green and the reviewer's round 3 passed.
