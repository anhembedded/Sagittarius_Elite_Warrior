# EPIC-036G — Walking skeleton: a bot that halts on the headless host reaches the owner's Discord once

**Status:** ✅ Done (2026-10-16)
**Source:** the owner, 2026-10-15, relayed by the coordinator in English: *"Discord. But do the design for this module first, as a walking skeleton."* (translated from Vietnamese by the coordinator).
**Risk:** 🟡 — the first outbound message to a third party, a secret read on the production host, and a change to what the host tells the operator before a mainnet resume
**Complexity:** M — one source, one channel, one transport, one status port, one verb, and a move of the venue-neutral secret stores; the hub, outbox and lanes are reused unchanged
**Epic:** [EPIC-036](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md): the alert a halting bot raises is added there
**Depends on:** [EPIC-036A](../completed/EPIC-036A_alerting_core.md) (done). Design: [`Docs/MODULES/alerting/04-solution-strategy.md`](../../../../Docs/MODULES/alerting/04-solution-strategy.md). Decisions: D1–D5 of [`DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md`](../DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md); N1–N8 of [`DECISION_2026-10-08_alerting_module.md`](../DECISION_2026-10-08_alerting_module.md).

---

## 1. Context and problem
The alerting core sends nothing: its channel list is empty (`src/modules/alerting/composition/channel_bindings.py:39-40`) and it reads no other module (`src/modules/alerting/module.py:61`). On the owner's VPS the host warns at every start that nothing will tell the owner if a bot halts (`src/modules/operations/application/host_steps.py:63-77`). The webhook cannot come from the keyring there: the keyring is unreadable on that host (`src/modules/trading/adapters/binance/mainnet/keyring_secret_store.py:73-77`). A stop that gives up is only text in the bot's reason and an ERROR log line (`src/modules/bots/application/kinds/grid/stop/grid_stop_retry.py:112-124`). Re-read each citation when the task starts (`execute-task`).

## 2. Acceptance criteria
- [x] **One alert per entry.** A bot entering `HALTED` produces exactly one CRITICAL `BOT_HALTED` alert; entering `ERROR`, one `BOT_ERROR`; a stop whose automatic retries are used up, one `STOP_FAILED`. The subject is the bot (id, name, kind, venue, symbol from `BotStatusEntry`); the detail is the bot's reason. A rewrite of a bot already `HALTED` is not a second alert. A bot that returns to `RUNNING` clears its condition (`IAlertPublisher.condition_cleared`).
- [x] **No re-alert on restart.** At boot the source seeds every bot's state from `GetBotStatusReportQuery()` without alerting.
- [x] **Typed give-up fact (D4).** `bots/contracts/events/` gains an event for a stop that gave up, published once per round by `GridStopRetry._exhausted`; nothing in `alerting` reads the reason text to find it. `bots` still imports nothing from `alerting`.
- [x] **Through the outbox.** The alert is in `state/alerts.sqlite3` before any request is made; an alert enqueued while Discord is unreachable is sent after the network or the app comes back, unless older than 24 h.
- [x] **Discord channel.** `DiscordWebhookChannel` posts the alert's subject, title and detail; a silent cell sets Discord's silent flag. It never raises: 2xx → `sent`; 429 → `retry_later` with Discord's wait (the body's `retry_after`, else the `Retry-After` header); 401, 403 or 404 → `refused` (permanent); a timeout, a connection error or a 5xx → `failed`. A webhook value that is not a Discord webhook URL is `refused` without a request.
- [x] **Retry-After honoured.** No request is sent to Discord before the wait it named, on the injected clock; a 429 uses no attempt (as `ChannelDelivery` already does).
- [x] **No secret anywhere (N3).** No log record, exception text, `DeliveryResult.reason`, outbox row or `alert test` output contains the webhook URL or any path segment of it, on every success and failure path.
- [x] **The secret on a headless host (D3).** The webhook is read by name, `alerting_discord_webhook`, through `ISecretStore` in the order systemd credential → permission-checked file → keyring. The venue-neutral stores and their order are importable by `alerting` without importing `trading`'s adapters; `trading`'s behaviour and its secret tests are unchanged. `scripts/render_service_files.py` emits the credential line, `deploy/linux/sew-run.service` is regenerated, and `Docs/OPERATIONS/headless_runbook.md` §3 says how to create the file (empty for no Discord) and how to rotate it.
- [x] **The host's answer (D5).** `alerting/contracts` gains a port that answers whether a channel carries bot events: `True` only when the Discord channel is declared and its secret is non-empty. `operations` binds an adapter over it in place of `NoAlertChannels`. With a webhook the start log says "an alert channel carries bot events"; without one it still warns. The unit file's header names what is still unsupported (`036B`'s other sources and `036E`'s dead man's switch).
- [x] **Headless Send test.** `alert test` sends one INFO test alert through the channel directly (not the outbox, so it works from a second, read-only process), prints the sanitised outcome and exits non-zero when it was not sent, using an existing exit code from `Docs/OPERATIONS/exit_codes.md`. The runbook shows how to run it with the unit's credential.
- [x] **Off the bot's thread.** The Discord request runs on the lane `alerting-lane-discord`; a Discord that hangs never delays a bot's thread (`publish` only writes the outbox).
- [x] **Owner's run on the VPS**, recorded in the notes: the credential file provisioned, the unit regenerated and restarted, `alert test` arriving in the owner's Discord channel, and `run` starting without the "no alert channel" warning. Done 2026-10-16 ("The owner's run on the VPS" in the notes); a real halt on the VPS has not happened yet.

## 3. Design
A walking skeleton (Cockburn; the shape of `PRO-004` and `Docs/HLD/06_enforcement_and_migration.md` §6.3): one path through every seam, each part as thin as it can be while real. An anti-corruption layer at the edge (`BotAlertSource` translates a `bots` fact into the alerting vocabulary, DDD); the adapter pattern behind `IAlertChannel`, with the HTTP transport injected so tests use a fake and never the network (`ci-rule.md` §2). The source reads the one bot through the contract query `GetBotStatusReportQuery(bot_id)` (`src/modules/bots/contracts/bot_status_report.py:51-69`) and the lifecycle state's value, never `bots`' domain types. The secret stores move rather than being copied (P3; O2's recommendation): the target package is the one the boundary guards allow both modules to import, decided at the start and recorded here. Nothing in the hub, the outbox or the lanes changes: if the skeleton needs a change there, stop and record why. Full picture: `Docs/MODULES/alerting/04-solution-strategy.md`.

## 3a. Reuse
Checked against `.claude/rules/capabilities.md` and `src/` on 2026-10-16. No UI need.
| Need | Checked | Result |
| :--- | :--- | :--- |
| Publish an alert, persist, retry, honour a wait | `AlertHub`, `SqliteOutbox`, `ChannelDelivery`, `ThreadedDeliveryHost` (`EPIC-036A`) | used unchanged (no line of the hub, outbox, worker or host changed) |
| Read one bot | `GetBotStatusReportQuery` in `bots/contracts` | used, as `operations`' `read_bot_status` does |
| Read a secret on the host | `SystemdCredentialStore`, `secret_store_order.py` (`trading`) | moved to `src/support/secrets/`, not copied (D3); `trading` imports it from there |
| An HTTP POST | `urllib`, as `TelegramNotificationChannel` does | used; no new dependency |
| A command-line command | catalog row `ICliRegistry`, `CliCommandDescriptor`; the bots' verbs | used: `declare_cli` in `module.py`, the report through `IReportPrinter` |
| A test double for the transport | none existed | `FakeWebhookTransport`, written from the port, held to the contract the real transport passes |
| A test double for the secret store | `tests/secret_stores.py` | used: `InMemorySecretStore`, `UnavailableSecretStore` |
| A capability entry | `Capability:` block | added for `support/secrets` (`build_secret_stores`); the catalog regenerated |

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

Run 2026-10-16; results in the notes below.

## 6. Docs touched
- `Docs/MODULES/alerting/`: views 1–7 move the skeleton's parts from Planned to Built with their `file:line`; the skeleton section (now `04-solution-strategy.md`) records the proof.
- `Docs/OPERATIONS/headless_runbook.md`: §0 (what is still unsupported), §3 (the webhook credential, rotation, Windows), §5 (`alert test` through `systemd-run`), §12 (not proven).
- `Docs/SPEC/SPEC-014_run_a_grid_bot.md`: §5, the alert a halting bot raises and the stop-gave-up event; §8, its proof.
- `.claude/rules/capabilities.md`: regenerated (the `support/secrets` row).

## Implementation notes (written when done)
Written 2026-10-16 on `claude/epic-036g-walking-skeleton`, stacked on the design branch (`claude/epic-036-alerting-module-design`, PR #536) over `master-warrior` `7ef62c7`. Engine at the pinned `f4ef582`, untouched. No dependency, `pyproject.toml`, lock or settings change.

**What exists**, in three commits:
1. `refactor(epic-036g)` — the systemd-credential, permission-checked-file and keyring stores, their file checks, `OrderedSecretStores` and the order moved verbatim from `trading` to `src/support/secrets/`, with their tests (`tests/unit/support/secrets/`). **Where they went (decided at the start, §3):** a support package, because a module may import a support package only through its `contracts/` and `infrastructure/` is the legacy tree no module may reach; one new boundary rule lets a module's `composition/` import `support/secrets` and nothing else of a module (`rules.py` `_SECRETS_SUPPORT_ZONES`, six rows pinned in `test_boundary_rules.py`). `support/secrets` imports `support/binance_gateway/contracts` for `CredentialsSource` (support → support contracts is allowed); the name is Binance's, the values are neutral.
2. `feat(bots)` — `BotStopGaveUpEvent(bot_id, retries)` in `bots/contracts/events/`, published once per round from `GridStopRetry._exhausted` (D4).
3. `feat(alerting)` (with this record and the documents) — `BotAlertSource`; `DiscordWebhookChannel` with `discord_message.py` (body) and `discord_answer.py` (answer → `DeliveryResult`); `IWebhookTransport`, `UrllibWebhookTransport`, `FakeWebhookTransport` and the transport contract suite; `IAlertingStatus` and `ChannelAlertingStatus`; `SendTestMessage` and `alert test`; `AlertKind.TEST`; `Alert.condition_key`; `operations`' `AlertingAlertChannels` replacing the deleted `NoAlertChannels`; the unit file's credential line and header; the runbook; SPEC-014.

**Decisions taken, and why.**
- **A channel not configured here is not in the catalog.** The descriptor's factory answers `None` when no webhook (or no Discord webhook URL) is stored, so no lane starts for it and `IAlertingStatus` is simply "a channel in the catalog and not disabled". The channel still reads its secret at each send, so a desktop rotation applies to the next message; a channel *added* after the start needs a restart, as a systemd credential does anyway.
- **`allowed_mentions.parse = []` on every message.** A bot's name or reason is text the owner typed or the exchange sent; `@everyone` in it must not ping a server.
- **429 → Discord's wait, rounded up to the millisecond; none named → 5 s** (`DEFAULT_RETRY_AFTER`). Any other 4xx is `refused` (a 400 recurs for every message too); 5xx and no answer are `failed`.
- **Recovery:** entering `RUNNING` clears `BOT_HALTED` and `BOT_ERROR`, entering `STOPPED` clears `STOP_FAILED`; a halted bot that the owner stops is not "recovered". `EPIC-036B` owns the full table.
- **A stop that gave up alerts even when the bot cannot be read** (subject with the id only): the alert that money may be on the exchange is not lost to a failed read.
- **`alert test` is read-only and goes straight to the channel** (design 036 §9), so it runs beside a running host; its exit is `5` when no channel is configured or a channel refused, `1` when Discord did not answer or asked to wait.
- **The unit header stays "not supported for unattended money"**, now naming `036B` and `036E`: D5 said "narrows to the heartbeat and the dead man's switch", but a stop loss hit, a lost user-data stream or a revoked key is still alerted by nobody until `036B`, so naming only `036E` would overstate.
- **`render_service_files.alerting_credential_names()`** sits beside `mainnet_credential_names()`; the webhook's name comes from the channel's constant, so the unit and the channel cannot disagree (`test_the_unit_loads_the_discord_webhook_under_the_name_the_channel_reads`).

**Verification, on the checked tree.**
- Red first: the stop-gave-up tests failed on the assertion (no event published) before `_exhausted` published; every new alerting test file failed to import before its module existed.
- Mutation checks (each turned a test red, then restored): the webhook added to the "did not answer" reason (killed by the red-flag test only after it was tightened: it first survived, because a later success overwrote the row and the old bytes sat in the WAL file; the test now collects each reason as the channel gives it and scans every `alerts.sqlite3*` file); the webhook added to the channel's debug log; the 429 wait halved; `bus.on(BotChangedEvent, ...)` removed from `boot()` (2 integration tests red).
- `pytest tests/unit` (8 workers): 14 487 passed. `tests/sanity`: 65 passed. `tests/integration`: 718 passed, 3 skipped, 1 failed — `test_workbench_conformance[True-1024x700]` ("backtest needs 719x706" in a 700 px window), the container's font-metric failure `EPIC-036A`'s notes record on a clean `master-warrior`; nothing here touches the Backtest mode. The new integration tests log no WARNING or ERROR.
- `pwsh scripts/ci-local.ps1 -SkipTests`: PASS on the refactor commit (log grepped, no `FAILED|ERROR|Traceback|ResourceWarning`); rerun on the final tree before the push.
- **The real entry point:** `main.py alert test` with no webhook exits 5 with the guidance line; with a credentials directory holding a well-formed webhook URL whose id and token do not exist, the real `UrllibWebhookTransport` reached Discord through the proxy, Discord answered 404 (`Unknown Webhook`), the report read `discord    not sent: Discord refused the webhook message (404)`, the exit was 5, and the token appeared in neither stream. Nothing was posted to any channel.
- `ci-local.ps1 -Full` is GitHub Actions' to run on the PR head.

**Review round 1 (PR #537, reviewer comment on `a31ecf9`, re-review on `17c0f50`) and CodeQL.** `master-warrior` merged in after #536 was squashed (merge commit, the branch's documents kept: they equal master's plus this task's edits). CodeQL raised three "clear-text logging of sensitive information" alerts on `channel_bindings.py`: each line passed the secret's *name* constant to the logger, never its value; the credential is now named in the message text and no value from the secret store reaches a log call. Finding 2 (a writer whose read finished first could record an older state over a newer one) fixed: the read of the bot is inside the source's lock; `test_a_second_writer_never_leaves_a_stale_remembered_state` was red first (the return to RUNNING was swallowed). Question 3 (is a second stop give-up deduplicated?) answered by `test_a_second_round_that_gives_up_is_told_again_through_the_real_hub`: no, the CRITICAL dedup window is one minute and a round of retries lasts about nine, so the owner hears it again; the source's docstring says so. Nit 4: `[0-9]` instead of `\d` in the webhook pattern, with Arabic-Indic digits refused by a test. Observation: the runbook now tells an existing install to create the webhook file before installing the regenerated unit.

**The owner's run on the VPS (2026-10-16).** Run by the owner on the Linux VPS (systemd), at a commit at or after `455dec2` (`master-warrior` pulled that day); the log lines below were relayed by the owner.
- The credential file was written: `121 /etc/sew/credentials/alerting_discord_webhook` (`wc -c`).
- `alert test` through `systemd-run` with `LoadCredential`: `[alert-channel] discord is on: webhook read from the Discord webhook credential (alerting_discord_webhook)`, then `Test message` / `discord    sent`, exit 0. The message arrived in the owner's Discord channel.
- The service after the restart, at 23:26:04: `[alert-channel] discord is on: …`; at 23:26:08 `App.Operations.Host - INFO - [alerts] an alert channel carries bot events`. The `spot_mainnet` bot `44wa1x` went `RECOVERING -> RUNNING on reconcile_ok` with its 6 resting orders.
- Earlier the same day, on the owner's Windows desktop, a real halt (bot `djwx0w`, `futures_testnet`, `price_feed_stale` during Wi-Fi congestion) logged `[alert-source] bot djwx0w: BOT_HALTED published`.

**Still not proven.** A real halt on the VPS has not happened yet, so the whole chain (bot halts, source publishes, outbox, lane, Discord) has not run end to end on that host; the pieces are proven separately (the integration test with a fake transport; the real `alert test` on the VPS; the real `BOT_HALTED` publication on the desktop). Whether the desktop's `BOT_HALTED` reached a Discord channel was not reported. Discord's pacing under its own limit (`EPIC-036C`). The other alert sources and the dead man's switch (`036B`, `036E`) do not exist yet, so the unit file's header still says the host is not supported for unattended money.

## Resume
Done 2026-10-16. Nothing left in this task. The first real halt on the VPS is the next confirmation; it belongs to ordinary operation, not to a task.
