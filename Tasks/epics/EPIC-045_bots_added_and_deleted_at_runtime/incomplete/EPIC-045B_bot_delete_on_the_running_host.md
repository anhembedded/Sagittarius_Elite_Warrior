# EPIC-045B — `bot delete` forgets a DRAFT or STOPPED bot on the running host

**Status:** 🟡 In progress
**Source:** the owner, 2026-10-21, quoted in the [epic README](../README.md)
**Risk:** 🟡 — it removes a bot's file; the exposure refusal is stricter than the tab
**Complexity:** M
**Epic:** [EPIC-045](../README.md)
**Depends on:** None

---

## 1. Context and problem
The owner reversed the 2026-10-17 choice that dropped `bot delete`: the Bots tab deletes, the host must too.

## 2. Acceptance criteria
- [ ] `bot delete <id>` on a running host removes a DRAFT or STOPPED bot with nothing left on the exchange, places and cancels no order, and answers in words.
- [ ] Every other state, an unknown id, and a bot whose record shows a held base, a live order or an owed order are refused; the file stays.
- [ ] It runs under the lock a Start holds: a delete racing a start either sees STARTING and is refused, or lands first and the start finds no bot.

## 3. Design
See [the decision record](../DECISION_2026-10-21_add_and_delete_on_the_running_host.md) D2, D4..

## 3a. Reuse
Used `DeleteBotCommand` (the tab's), `BotLookup`, `BotCommandLock`. New: `IBotKind.exposure_left`.

## 4. Changes, per file
| `bots/contracts/i_bot_kind.py`, `bots/domain/grid/grid_kind.py`, `bots/domain/grid/` | `exposure_left`, closed by default; the Grid reads its record |
| `bots/application/use_cases/delete_bot_for_host/`, `host_bot_requests.py`, `command_bindings.py` | handler, request, binding |
| `core/contracts/host_control.py`, codec, verbs, `cli_commands.json` | the `delete` word and verb |

## 5. Testing
Unit: handler (states, exposure, lock), codec, verb. Integration: delete beside a running host on the fake exchange.

## 6. Docs touched
`headless_runbook.md` §6 (045E), `Docs/MODULES/bots/05-building-blocks.md`.
