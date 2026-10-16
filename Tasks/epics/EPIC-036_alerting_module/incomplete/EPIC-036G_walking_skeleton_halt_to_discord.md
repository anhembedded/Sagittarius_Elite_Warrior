# EPIC-036G — Walking skeleton: a bot that halts on the headless host reaches the owner's Discord once

**Status:** 🟡 In progress — the owner gave the go and accepted O1 (D3) and O2 (D5) of the [2026-10-15 decision](../DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md) on 2026-10-16
**Source:** the owner, 2026-10-15, relayed by the coordinator in English: *"Discord. But do the design for this module first, as a walking skeleton."* (translated from Vietnamese by the coordinator).
**Risk:** 🟡 — the first outbound message to a third party, a secret read on the production host, and a change to what the host tells the operator before a mainnet resume
**Complexity:** M — one source, one channel, one transport, one status port, one verb, and a move of the venue-neutral secret stores; the hub, outbox and lanes are reused unchanged
**Epic:** [EPIC-036](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md): the alert a halting bot raises is added there
**Depends on:** [EPIC-036A](../completed/EPIC-036A_alerting_core.md) (done). Design: [`Docs/MODULES/alerting.md`](../../../../Docs/MODULES/alerting.md) §8. Decisions: D1–D5 of [`DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md`](../DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md); N1–N8 of [`DECISION_2026-10-08_alerting_module.md`](../DECISION_2026-10-08_alerting_module.md).

---

## 1. Context and problem
The alerting core sends nothing: its channel list is empty (`src/modules/alerting/composition/channel_bindings.py:39-40`) and it reads no other module (`src/modules/alerting/module.py:61`). On the owner's VPS the host warns at every start that nothing will tell the owner if a bot halts (`src/modules/operations/application/host_steps.py:63-77`). The webhook cannot come from the keyring there: the keyring is unreadable on that host (`src/modules/trading/adapters/binance/mainnet/keyring_secret_store.py:73-77`). A stop that gives up is only text in the bot's reason and an ERROR log line (`src/modules/bots/application/kinds/grid/stop/grid_stop_retry.py:112-124`). Re-read each citation when the task starts (`execute-task`).

## 2. Acceptance criteria
- [ ] **One alert per entry.** A bot entering `HALTED` produces exactly one CRITICAL `BOT_HALTED` alert; entering `ERROR`, one `BOT_ERROR`; a stop whose automatic retries are used up, one `STOP_FAILED`. The subject is the bot (id, name, kind, venue, symbol from `BotStatusEntry`); the detail is the bot's reason. A rewrite of a bot already `HALTED` is not a second alert. A bot that returns to `RUNNING` clears its condition (`IAlertPublisher.condition_cleared`).
- [ ] **No re-alert on restart.** At boot the source seeds every bot's state from `GetBotStatusReportQuery()` without alerting.
- [ ] **Typed give-up fact (D4).** `bots/contracts/events/` gains an event for a stop that gave up, published once per round by `GridStopRetry._exhausted`; nothing in `alerting` reads the reason text to find it. `bots` still imports nothing from `alerting`.
- [ ] **Through the outbox.** The alert is in `state/alerts.sqlite3` before any request is made; an alert enqueued while Discord is unreachable is sent after the network or the app comes back, unless older than 24 h.
- [ ] **Discord channel.** `DiscordWebhookChannel` posts the alert's subject, title and detail; a silent cell sets Discord's silent flag. It never raises: 2xx → `sent`; 429 → `retry_later` with Discord's wait (the body's `retry_after`, else the `Retry-After` header); 401, 403 or 404 → `refused` (permanent); a timeout, a connection error or a 5xx → `failed`. A webhook value that is not a Discord webhook URL is `refused` without a request.
- [ ] **Retry-After honoured.** No request is sent to Discord before the wait it named, on the injected clock; a 429 uses no attempt (as `ChannelDelivery` already does).
- [ ] **No secret anywhere (N3).** No log record, exception text, `DeliveryResult.reason`, outbox row or `alert test` output contains the webhook URL or any path segment of it, on every success and failure path.
- [ ] **The secret on a headless host (D3).** The webhook is read by name, `alerting_discord_webhook`, through `ISecretStore` in the order systemd credential → permission-checked file → keyring. The venue-neutral stores and their order are importable by `alerting` without importing `trading`'s adapters; `trading`'s behaviour and its secret tests are unchanged. `scripts/render_service_files.py` emits the credential line, `deploy/linux/sew-run.service` is regenerated, and `Docs/OPERATIONS/headless_runbook.md` §3 says how to create the file (empty for no Discord) and how to rotate it.
- [ ] **The host's answer (D5).** `alerting/contracts` gains a port that answers whether a channel carries bot events: `True` only when the Discord channel is declared and its secret is non-empty. `operations` binds an adapter over it in place of `NoAlertChannels`. With a webhook the start log says "an alert channel carries bot events"; without one it still warns. The unit file's header names what is still unsupported (the heartbeat and the dead man's switch, `036E`).
- [ ] **Headless Send test.** `alert test` sends one INFO test alert through the channel directly (not the outbox, so it works from a second, read-only process), prints the sanitised outcome and exits non-zero when it was not sent, using an existing exit code from `Docs/OPERATIONS/exit_codes.md`. The runbook shows how to run it with the unit's credential.
- [ ] **Off the bot's thread.** The Discord request runs on the lane `alerting-lane-discord`; a Discord that hangs never delays a bot's thread (`publish` only writes the outbox).
- [ ] **Owner's run on the VPS**, recorded in the notes: the credential file provisioned, the unit regenerated and restarted, `alert test` arriving in the owner's Discord channel, and `run` starting without the "no alert channel" warning.

## 3. Design
A walking skeleton (Cockburn; the shape of `PRO-004` and `Docs/HLD/06_enforcement_and_migration.md` §6.3): one path through every seam, each part as thin as it can be while real. An anti-corruption layer at the edge (`BotAlertSource` translates a `bots` fact into the alerting vocabulary, DDD); the adapter pattern behind `IAlertChannel`, with the HTTP transport injected so tests use a fake and never the network (`ci-rule.md` §2). The source reads the one bot through the contract query `GetBotStatusReportQuery(bot_id)` (`src/modules/bots/contracts/bot_status_report.py:51-69`) and the lifecycle state's value, never `bots`' domain types. The secret stores move rather than being copied (P3; O2's recommendation): the target package is the one the boundary guards allow both modules to import, decided at the start and recorded here. Nothing in the hub, the outbox or the lanes changes: if the skeleton needs a change there, stop and record why. Full picture: `Docs/MODULES/alerting.md` §8.

## 3a. Reuse
To be checked against `.claude/rules/capabilities.md` and `src/` when the task starts. Known candidates:
| Need | Checked | Result |
| :--- | :--- | :--- |
| Publish an alert, persist, retry, honour a wait | `AlertHub`, `SqliteOutbox`, `ChannelDelivery`, `ThreadedDeliveryHost` (`EPIC-036A`) | to be used unchanged |
| Read one bot | `GetBotStatusReportQuery` in `bots/contracts` | to be used |
| Read a secret on the host | `SystemdCredentialStore`, `secret_store_order.py` (`trading`) | to be moved, not copied (D3) |
| An HTTP POST | `urllib`, as `TelegramNotificationChannel` does | to be used; no new dependency |
| A command-line verb | the bots' verbs (`src/modules/bots/cli/bot_verbs.py`) | the pattern to follow |
| A test double for the transport | none | `FakeWebhookTransport`, written from the port, with its contract test |

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/application/sources/bot_alert_source.py` (new) | The three mappings, seeding at boot, `condition_cleared` on `RUNNING` |
| `src/modules/alerting/adapters/discord_webhook_channel.py` (new) | The channel |
| `src/modules/alerting/contracts/i_webhook_transport.py`, `contracts/testing/fake_webhook_transport.py`, `adapters/urllib_webhook_transport.py` (new) | The transport port, its fake and the real one |
| `src/modules/alerting/contracts/` (new port), `src/modules/operations/adapters/`, `src/modules/operations/module.py` | D5: the status port and the adapter replacing `NoAlertChannels`; `operations` depends on `alerting` |
| `src/modules/alerting/cli/` (new) | `alert test` |
| `src/modules/alerting/composition/channel_bindings.py`, `alerting_bindings.py`, `module.py` | One `AlertChannelDescriptor`; the source subscribed in `boot()`; `dependencies = ["bots"]` |
| `src/modules/bots/contracts/events/` (new event), `src/modules/bots/application/kinds/grid/stop/grid_stop_retry.py` | D4 |
| The venue-neutral secret stores and `secret_store_order.py`, out of `src/modules/trading/` | D3: moved; `trading` imports them from the new place |
| `scripts/render_service_files.py`, `deploy/linux/sew-run.service` | D3: the credential line; D5: the header |
| `Docs/OPERATIONS/headless_runbook.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | The credential, rotation and `alert test`; the alert a halt raises |

## 5. Testing
Tier per `ci-rule.md` §2; every test red before the change.
- Integration, the skeleton end to end: `test_a_halted_bot_reaches_discord_once_after_its_retry_after` — composed app, real `bots` and `alerting`, outbox on `tmp_path`, a fake secret store, `FakeWebhookTransport` answering 429 (`retry_after` 2 s) then 204; one POST, none before 2 s on the injected clock, a second that succeeds, the row `SENT`, the body naming the bot and the kind, no part of the URL in the captured log or the outbox.
- Integration: `test_an_error_and_a_stop_that_gave_up_each_reach_discord_once`.
- Unit, source: `test_entering_halted_publishes_one_critical_alert`, `test_a_rewrite_of_a_halted_bot_publishes_nothing`, `test_seeding_at_boot_publishes_nothing`, `test_a_return_to_running_clears_the_condition`, `test_a_stop_that_gave_up_publishes_stop_failed`.
- Unit, channel: `test_a_429_answers_retry_later_with_discords_wait`, `test_retry_after_from_the_header_when_the_body_has_none`, `test_a_deleted_webhook_is_refused`, `test_a_timeout_and_a_5xx_are_failures_that_pass`, `test_a_value_that_is_not_a_discord_webhook_is_refused_without_a_request`, `test_a_silent_cell_sets_the_silent_flag`, `test_the_channel_never_raises`.
- Unit, red flag: `test_no_part_of_the_webhook_reaches_a_log_an_error_a_reason_or_the_outbox` (every path above, captured logs and exception text scanned).
- Unit, secrets: the moved stores keep their existing tests; `test_the_webhook_is_read_from_the_systemd_credential_first`; `test_service_files.py` gains the credential name.
- Unit, host: `test_the_host_says_a_channel_carries_bot_events_only_with_a_webhook`.
- Unit, verb: `test_alert_test_prints_the_sanitised_outcome_and_exits_non_zero_when_not_sent`.
- Guards: `pytest tests/unit/architecture -q` (`bots` never imports `alerting`; `alerting` imports no `trading` adapter).
- Manual on the VPS (the owner), recorded: §2's last criterion.

Not run yet.

## 6. Docs touched
- `Docs/MODULES/alerting.md`: views 1, 2, 3, 5, 6 and 7 move the skeleton's parts from Planned to Built; §8 records the proof.
- `Docs/OPERATIONS/headless_runbook.md` §3 (the credential, rotation) and §5 or §6 (`alert test`).
- `Docs/SPEC/SPEC-014_run_a_grid_bot.md`: the alert a halting bot raises.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action, after the owner's go: `test_entering_halted_publishes_one_critical_alert`, run red.
