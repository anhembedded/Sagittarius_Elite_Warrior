# EPIC-036F — Remote control from Discord: allowlisted commands reach the same handlers as the UI

**Status:** 🔵 Planned — not started (Phase 4); waits for [`EPIC-035X`](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035X_every_bot_decision_is_in_an_audit_trail.md) and for the owner's approval of the library
**Source:** the owner's approval of the alerting design, 2026-10-08 (N6), relayed by the coordinator session.
**Risk:** 🔴 — a remote door to a trading app: authorisation, replay, a new dependency and a persistent outbound connection
**Complexity:** L
**Epic:** [EPIC-036](../README.md)
**SPEC:** none yet; a journey "stop a bot from my phone" is added by this task.
**Depends on:** [EPIC-036A](EPIC-036A_alerting_core.md), [EPIC-036C](EPIC-036C_discord_channel_and_telegram_migration.md), [EPIC-035X](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035X_every_bot_decision_is_in_an_audit_trail.md) (the audit trail, so the first remote command already has a record). **Needs owner approval before starting:** the Discord gateway library, or a hand-written client (`requirements.txt` is a dependency change, `ONBOARDING.md` §7; decision O1).

---

## 1. Context and problem
An alert that says "bot g3n092 halted" is most useful when the owner can answer from the phone. `AlertSubject` already carries the bot id, so an alert can name the bot to act on. The real risks are the ones other bots' users hit: an exposed webhook or token lets anyone act; adding a bot to a group gives every member control; a command can arrive twice; a mainnet Start must never be one tap. A webhook carries no authentication and is never a command path.

## 2. Acceptance criteria
- [ ] **`IRemoteCommandSource`** is the receive side, separate from `IAlertChannel` (a channel may implement either or both; Telegram may stay send-only). A Discord implementation connects **outbound** over the gateway; the app opens no port.
- [ ] **`RemoteCommandGate`** is the one door: every remote command passes it, and a command that skips it cannot reach a handler. It checks, in order: the **user ID is in the allowlist** (an empty allowlist accepts nothing; never authorised by channel, group or role), the **request id has not been run** (idempotency, durable across a restart), the **command tier**, then writes the audit record, runs the command and audits the result.
- [ ] **Command tiers:** status, pause and stop run at once; **start and resume need a second confirmation** (a confirm step with a short expiry) and are **disabled on mainnet by default**; anything else is refused with a reason.
- [ ] **Same handlers as the UI:** a remote stop dispatches the UI's own stop command through `ICommandDispatcher`; instance locking, Start preconditions and the state machine apply exactly as for a click.
- [ ] **Audit:** who (Discord user id), when, which command, which bot and the result are written to the `EPIC-035X` journal before and after the action; a refused command is audited too; no token or secret is written.
- [ ] An `INFO` alert reports "bot X stopped by a command from Discord" after a successful command.
- [ ] A lost gateway connection reconnects with backoff and raises `CHANNEL_FAILING` after its bound; commands issued while disconnected are not replayed on return.
- [ ] The allowlist is managed in the Options page of `EPIC-036D` and stored with the settings (user ids are not secrets; the bot token is, and lives in the keyring).
- [ ] The library choice (or the decision to hand-write a client) is recorded in the decision record and approved by the owner **before** any dependency is added.

## 3. Design
A **command gate** in front of the existing command handlers (the *Anti-Corruption Layer* and *Facade* for an external input), with an idempotency key (a request id) and *tiered authorisation*; the receive side and the send side are two ports so that a send-only channel stays simple (*Interface Segregation*). A button on an alert carries the bot id and a one-time request id, so a replayed click is a no-op. The library question is open (O1): the choices to put to the owner are a maintained gateway library, a minimal hand-written client, and Discord's HTTP interactions (which need an inbound endpoint and are therefore not preferred).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/contracts/i_remote_command_source.py` (new) | The receive-side port and the request type |
| `src/modules/alerting/application/remote_command_gate.py` (new) | Allowlist, idempotency, tiers, audit, dispatch |
| `src/modules/alerting/adapters/discord_gateway_source.py` (new) | The gateway adapter |
| `src/modules/alerting/ui/options/` | The allowlist editor |
| `requirements.txt` / `pyproject.toml` | The approved library only, after the owner's approval |

## 5. Testing
Tier per `ci-rule.md` §2: unit with a fake command source and dispatcher; one integration journey; the gateway checked manually.
- `test_a_command_from_a_user_not_on_the_allowlist_is_refused_and_audited`
- `test_an_empty_allowlist_accepts_no_command`
- `test_authorisation_is_by_user_id_never_by_channel_or_role`
- `test_a_repeated_request_id_runs_once`
- `test_a_request_id_stays_spent_across_a_restart`
- `test_stop_runs_at_once_and_start_needs_confirmation`
- `test_an_unconfirmed_start_expires`
- `test_start_is_refused_on_mainnet_by_default`
- `test_a_remote_stop_dispatches_the_same_command_the_ui_dispatches`
- `test_the_audit_record_is_written_before_and_after_the_action`
- `test_no_secret_is_written_to_the_audit_record` (red-flag test)
- `test_a_command_cannot_reach_a_handler_without_the_gate` (guard)
- `test_commands_issued_while_disconnected_are_not_replayed`
- `test_a_webhook_is_never_a_command_path`
- manual: a stop and a refused start from the owner's own Discord account, recorded in the task

Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. Blocked on `EPIC-035X` and on the owner's decision on the library (O1). First action when released: put the library options to the owner, then `test_a_command_from_a_user_not_on_the_allowlist_is_refused_and_audited`, run red.
