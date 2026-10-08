# EPIC-036C — Discord channel and Telegram migration: two real channels, secrets only in the keyring

**Status:** 🔵 Planned — not started
**Source:** the owner's approval of the alerting design, 2026-10-08 (N3, N8), relayed by the coordinator session; owner decision D3 of [`EPIC-035`](../../EPIC-035_spot_grid_unattended_safety/DECISION_2026-10-08_spot_grid_audit_owner_decisions.md) (Discord).
**Risk:** 🟡 — a secret webhook URL, a config-to-keyring migration and a new outbound dependency on Discord
**Complexity:** L
**Epic:** [EPIC-036](../README.md)
**SPEC:** none yet.
**Design:** [`DESIGN_2026-10-08_alerting_module.md`](../DESIGN_2026-10-08_alerting_module.md) (the design of record; the owner's page is a secondary reference). **Research:** [`RESEARCH_2026-10-08_alerting_lessons.md`](../RESEARCH_2026-10-08_alerting_lessons.md) §1, §2, §5, §7.
**Depends on:** [EPIC-036A](EPIC-036A_alerting_core.md) (`IAlertChannel`, the worker, `ISecretStore` in core).

---

## 1. Context and problem
`TelegramNotificationChannel` (`src/infrastructure/notifications/telegram_notification_channel.py`, 76 lines) reads its token from the config, does not retry and swallows a failure into a log line. There is no Discord channel. Real users report: Discord bans an IP that keeps retrying after a 429; Telegram can demand a wait of hours; a Discord webhook has no authentication, so a leaked URL lets anyone post; Telegram answers "chat not found" when the owner never pressed `/start`. Verify the limits with real response headers when the task starts; the design's numbers come from vendor blogs and single reports.

## 2. Acceptance criteria
- [ ] **`DiscordWebhookChannel`** (in `alerting/adapters`) posts an **embed** coloured by severity with the subject, title, detail and time; **silent** loudness sets Discord's `@silent` flag; grouped and counted alerts show their count and bots.
- [ ] **`TelegramChannel`** moves into `alerting/adapters` and implements `IAlertChannel`; it formats Markdown, uses `disable_notification` for silent, and **escapes** user-controlled text.
- [ ] **Rate limits:** each channel reads the platform's `Retry-After` / `retry_after`, returns it in `DeliveryResult`, and is never called again before it; the channel's own pacing stays under the platform limit; a 429 is never retried in a loop (an IP ban would lose every alert).
- [ ] **Keyring:** the Discord webhook URL and the Telegram token are stored by name through `ISecretStore` and read when sending. **Migration:** on first run the Telegram token in the config is written to the keyring and then removed from the config, once; a second run changes nothing; a keyring that is unavailable leaves the config untouched and reports it (`SecretStoreUnavailableError`), never loses the token.
- [ ] **No secret leaks:** a webhook URL, a bot token or a ping URL appears in no log line, exception message, traceback, config file, history record or UI text; a channel's errors are sanitised at the channel.
- [ ] **Send test** returns the outcome as a value: a missing/invalid webhook, a 404 (deleted), a Telegram "chat not found" or a bot never started becomes plain guidance ("Open the bot on Telegram and press Start, then try again"), never a raw error code.
- [ ] **Rotate webhook:** replaces the stored secret and invalidates nothing else; the old value is not shown anywhere.
- [ ] A permanent failure (deleted webhook, revoked token) is reported as `permanent`, so the worker stops retrying and raises `CHANNEL_FAILING`.
- [ ] Both channels pass one shared **channel contract test** (never raises; maps a transport failure to a `DeliveryResult`).

## 3. Design
Adapter pattern behind `IAlertChannel`; plain `urllib` POST as Telegram does today, so no new dependency (`CONSTITUTION.md` P5; a library would be the owner's call, `ONBOARDING.md` §7). The transport is injected so tests use a fake HTTP, never the network (`ci-rule.md` §2, unit tests reach no network). Sanitising is done once, in a helper used by both channels, and tested by feeding the secrets through every failure path. The embed colours and Telegram escaping are pure functions. Migration is a one-shot application service run at the module's `boot()` and covered by a before/after config test.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/adapters/discord_webhook_channel.py` (new) | The Discord channel |
| `src/modules/alerting/adapters/telegram_channel.py` (new) | The moved Telegram channel |
| `src/infrastructure/notifications/telegram_notification_channel.py` and its test | Deleted; tests move |
| `src/modules/alerting/application/` | `SecretMigration`, the sanitiser, `SendTest` and `RotateSecret` use cases |
| `src/shell/composition_root.py` | The Telegram wiring removed |
| Config template / docs | The Telegram token key documented as migrated and removed |

## 5. Testing
Tier per `ci-rule.md` §2: unit with a fake transport and a fake secret store; the real-network checks are manual and recorded.
- `test_the_discord_embed_is_coloured_by_severity`
- `test_a_silent_alert_sets_the_discord_silent_flag`
- `test_a_silent_alert_sets_the_telegram_disable_notification_flag`
- `test_telegram_text_from_an_alert_is_escaped`
- `test_a_429_is_never_retried_before_retry_after` (both channels, fake clock)
- `test_the_channel_paces_itself_under_the_platform_limit`
- `test_the_token_moves_from_config_to_the_keyring_once`
- `test_an_unavailable_keyring_leaves_the_config_token_in_place`
- `test_no_secret_appears_in_logs_errors_or_tracebacks` (red-flag test: feeds a webhook URL, a token and a ping URL through every success and failure path and scans captured logs, exception text and the history)
- `test_send_test_turns_chat_not_found_into_guidance`
- `test_send_test_turns_a_deleted_webhook_into_guidance`
- `test_rotating_the_webhook_replaces_the_stored_secret_and_shows_nothing`
- `test_a_deleted_webhook_is_a_permanent_failure`
- `test_both_channels_satisfy_the_channel_contract_and_never_raise`
- manual: a real Discord webhook and a real Telegram chat, recorded in the task

Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: `test_no_secret_appears_in_logs_errors_or_tracebacks`, run red against the current Telegram channel.
