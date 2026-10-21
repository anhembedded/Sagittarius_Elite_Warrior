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

## Implementation notes (written when done)
Built in the first PR of the epic. D2 (the owner's reversal), D4 and D4a (the exposure refusal and the dust figure). The Bots tab's Delete refuses only by lifecycle state; the host adds `IBotKind.exposure_left` because a command line has no dialog. Review round 1 made the dust line USD-stable quotes only (any base on another quote keeps the bot; the figure stays the owner's 10) and summed the absolute values of the two held amounts. The fake-exchange journey showed the consequence: a Spot grid stopped with `bot stop` keeps the coin it bought and is refused; stopped with `--close-position` it holds dust and is deleted; a coin an earlier run kept (`earlier_runs_base`) keeps the bot even after a later sell-stop, because a run sells only its own orders. That is asked as O1.
Evidence: handler tests (`tests/unit/modules/bots/application/test_bot_delete_for_the_host.py`) over the record the real runtime codec writes, the kind-default tests (`tests/unit/modules/bots/domain/test_bot_kind_exposure_left.py`), the integration journey. Mutation-checked: the exposure refusal, the state gate, the dust comparison (`<` to `<=`, a doubled figure) and the lock each turn a test red when changed.
Not run: the `-Full` run on the PR head; the VPS.

## Resume
Built and under review in the epic's first pull request; flip to Done and move to `completed/` once it is merged and the `-Full` run is green.
