# EPIC-045C — `bot apply` goes through the command directory

**Status:** ✅ Done (2026-10-22)
**Source:** the owner, 2026-10-21, quoted in the [epic README](../README.md)
**Risk:** 🔴 — many entries, prune, and the applied-plan record cross the boundary
**Complexity:** L
**Epic:** [EPIC-045](../README.md)
**Depends on:** A, B

---

## 1. Context and problem
A plan-file workflow (create, edit, prune) still needed the host stopped: `bot apply` beside a running host exited `3`, and the only way to use it was to stop the host, which sends every RUNNING bot through RECOVERING and a manual resume.

## 2. Acceptance criteria
- [x] `bot apply` beside a running host with no restart, each document inside the 4096-byte limit (one command per entry, never one document for the plan).
- [x] An honest answer for a partly applied plan: a per-entry result, a refused entry never stops the others, a host that goes quiet leaves the rest `not sent` (exit `11`), no host at the first command is the old exit `3` with nothing changed.
- [x] The applied record `state/bot_plan.json` ends as an offline apply of the same plan leaves it, so `run --start-planned` stays coherent.
- [x] `--prune` on a running host deletes only bots at rest, with `bot delete`'s refusals; a running bot the plan omits keeps running and loses its wish.
- [x] Nothing places or cancels an order; a mainnet start never happens implicitly.

## 3. Design
[`DECISION_2026-10-22_bot_apply_beside_a_running_host.md`](../DECISION_2026-10-22_bot_apply_beside_a_running_host.md), C1–C9.

## 3a. Reuse
`PlanApplier` (one new method, `apply_entry`, the offline apply's own `_compare` and `_carry_out`), `parse_plan` (the entry is re-read as a one-bot plan), `BotCommandLock`, `DeleteBotForHostCommandHandler`, `NewBotEntry`, the codec/rules split of `host_command_codec.py` / `host_command_rules.py`, `BotHostCommandExecutor` rows, `ICommandDispatcher`. No new port, dependency, setting or Engine file.

## 4. Changes, per file
- `src/core/contracts/host_control.py`, `src/modules/operations/contracts/host_command.py`, `adapters/directory_host_control.py`, `application/host_command_codec.py`, `host_command_rules.py`, `bot_host_command_executor.py`: actions `apply-entry`, `unplan`; subject `plan`; key `desired_state`.
- `src/modules/bots/application/use_cases/apply_plan_entry_for_host/`, `unplan_bot_for_host/`, `delete_bot_for_host/` (forgets the wish), `plan/wish_ledger.py`, `plan/plan_applier.py` (`apply_entry`), `composition/command_bindings.py`.
- `src/modules/bots/cli/bot_plan_host_apply.py` (`HostPlanApplier`), `bot_plan_verbs.py`, `src/config/cli_commands.json` (`--wait`).
- #714's optional notes: the arm handler reads `saved_selection()` once and a `POSITION_OPEN` refusal is `INVALID_TRANSITION` as the disarm's is.

## 5. Testing
`tests/unit/modules/bots/cli/test_bot_apply_beside_a_host.py` (end to end over `InProcessHost`, including record equality with an offline apply), `tests/unit/modules/bots/application/plan/test_plan_entry_handlers_for_the_host.py`, `tests/unit/modules/operations/application/test_host_command_codec_plan.py`, `tests/integration/modules/bots/test_bot_apply_beside_a_running_host_on_the_fake_exchange.py` (the composed app: a create, an edit of a stopped bot, a refused edit of a running bot and a prune at rest; the per-entry results, the bots' files, the exchange's orders and the applied record), the executor and delete-handler tests. Mutation-checked: `set_wish` not replacing the row, `forget_wish` not writing, a write on every `set_wish`, deletes sent before the entries.

## 6. Docs touched
Runbook §6 and §8, SPEC-015, `Docs/MODULES/bots/06-runtime.md`.

## 7. Implementation notes
- One command per entry: a plan of any size fits the file limit; the cost is one round trip per entry (decision O1, batching not built).
- The result is per entry, not all-or-nothing; the order is entries, then forgotten wishes, then deletes.
- The full gate (`ci-local.ps1 -Full`) could not be read when this was pushed: GitHub Actions was not starting jobs. Verification was local (commit tier, unit suites).

**Board:** `bot apply` beside a running host sends one `apply-entry` per plan entry (plus `unplan` and `delete` for prune) under the Start lock, reuses the offline applier, and leaves the applied record as an offline apply would; no restart, no order.
