# EPIC-036C1 — Telegram is an alert channel again: its token and chat in the secret store, the old config moved once

**Status:** ✅ Done (2026-10-20) — built and proven by unit and integration tests; a message received in the owner's Telegram chat, from a desktop and from the VPS, is still to be seen
**Source:** the coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, 2026-10-20, "go on with 036C" after [`EPIC-036B`](EPIC-036B_alert_sources.md); and its consequence: `036B` removed the direct Telegram wiring, so an owner with a Telegram token in the config got nothing on Telegram. This slice restores that, as the design intended (N1, N3, N8).
**Risk:** 🟡 — a secret (the bot token sits in the request URL), a one-time write to the owner's config file, a new outbound call to Telegram
**Complexity:** M
**Epic:** [EPIC-036](../README.md); split from [EPIC-036C](../incomplete/EPIC-036C_discord_channel_and_telegram_migration.md), which keeps the Discord embed, pacing under the platform limit, `RotateSecret` and the Options-page fields
**SPEC:** none yet
**Design:** [`Docs/MODULES/alerting/`](../../../../Docs/MODULES/alerting/README.md)
**Depends on:** [EPIC-036G](EPIC-036G_walking_skeleton_halt_to_discord.md) (the channel seam and the webhook transport), [EPIC-036B](EPIC-036B_alert_sources.md)

---

## 1. Context and problem
`TelegramNotificationChannel` (`BOT-018`) read its token from `user_config.json`, did not retry, did not honour Telegram's wait and swallowed a failure into a log line; and after `036B` nothing built it. Real users report (research 036 §1) that Telegram can demand a wait of hours and answers "chat not found" when the owner never pressed Start.

## 2. Acceptance criteria
- [x] **`TelegramChannel`** is an `IAlertChannel` in `alerting/adapters`: it posts `sendMessage` through `IWebhookTransport`, HTML-escaped text with one bold head, `disable_notification` for a silent cell. (`test_telegram_message.py`, `test_telegram_channel.py`)
- [x] **The token and the chat id come from `ISecretStore` by name at each send** (`alerting_telegram_bot_token`, `alerting_telegram_chat_id`; a systemd credential on a server, the keyring on a desktop). Both are checked against the shapes Telegram issues before they go into a URL path. (`test_a_value_of_the_wrong_shape_is_refused_without_a_request`, `test_the_token_is_read_at_each_send_so_a_rotation_applies_to_the_next`)
- [x] **A 429 is never retried early**: the wait is Telegram's `parameters.retry_after`, else the header, else a default; a non-positive or non-numeric wait is not believed. (`test_telegram_answer.py`)
- [x] **A permanent failure is permanent**: a rejected token, a blocked or never-started bot and a missing chat are refusals the worker does not retry. (`test_a_refusal_will_not_be_retried`)
- [x] **Plain guidance, not a raw code**: "chat not found" and a 403 read "Open the bot on Telegram and press Start, then check the chat id and try again"; a rejected token says to check it with @BotFather. `alert test` and the Send test show the channel's reason, so they say this. (`test_chat_not_found_becomes_guidance_and_is_permanent`)
- [x] **No secret leaks**: the red-flag test drives every answer Telegram can give, through the real hub, worker pass and outbox, and finds no piece of the token in the log, a reason, a stored detail or the SQLite file. (`test_no_part_of_the_token_reaches_a_log_an_error_a_reason_or_the_outbox`)
- [x] **Migration**: the old config keys move to the store at boot, once, and are cleared only when the store reads the value back equal; a store that cannot be used, or another store that answers first, leaves the file untouched and says so in the log; a file that cannot be written keeps the secret in the store and says so. (`test_telegram_config_migration.py`)
- [x] **The shared channel contract**: Discord and Telegram pass one contract run over each (never raises, no answer fails and may pass, a rate limit is a wait, a refusal is not retried, a 5xx is retried); a third channel is one row. (`test_channel_contract.py`)
- [x] **Wired in the composed app** (`test_an_old_config_token_is_moved_at_boot_and_then_used_by_the_telegram_channel`, red when the migration call or the descriptor is removed).
- [x] The old `TelegramNotificationChannel`, its test and `036B`'s pause notice are deleted; `ConfigKeys` keeps the two keys, for the migration only.
- [ ] **A message received in the owner's Telegram chat.** Needs the owner (a bot token and a chat); not run.

## 3. Design
Adapter behind `IAlertChannel`, like Discord: the message, the meaning of the answer and the channel are three files; the words shared with Discord (`alert_text.py`: the severity mark and the subject line) are one. No new dependency.

**HTML, not MarkdownV2 (an agent decision the owner may veto).** MarkdownV2 makes eighteen characters special and a bot name or an exchange message holds any of them; one missed escape and Telegram refuses the whole message, which for an alert is a lost alert. HTML has three characters to escape and `html.escape` does it. The design page said "Markdown ... escapes user-controlled text"; this keeps the escape and chooses the format that cannot fail on a stray character.

**The migration runs in `AlertingModule.boot`, before the channels are built**, and only in a writable copy. On a headless host with no keyring nothing is migrated (the file is left as it was) and the runbook says to provision the two credentials (§3b2 of the headless runbook); the unit's credentials directory already loads any file placed there.

## 3a. Reuse
`IWebhookTransport` and its `urllib` implementation (errors already reduced to their kind), `FakeWebhookTransport`, `InMemorySecretStore`, the channel descriptor list, `IConfigReader`/`IConfigWriter`, the hub-and-outbox rig of the Discord leak test.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/adapters/telegram_channel.py`, `telegram_message.py`, `telegram_answer.py`, `alert_text.py` (new) | The channel, the body, the answer's meaning, the shared words (moved out of `discord_message.py`) |
| `src/modules/alerting/application/telegram_config_migration.py` (new) | The one-time move |
| `src/modules/alerting/composition/channel_bindings.py`, `alerting_bindings.py`, `module.py` | The descriptor, the migration binding, the call at boot |
| `src/infrastructure/notifications/` , `src/shell/telegram_pause_notice.py` | Deleted |
| `Docs/MODULES/alerting/`, `Docs/OPERATIONS/headless_runbook.md` | Telegram built; the runbook's §3b2 |

## 5. Testing
Unit: `test_telegram_message.py`, `test_telegram_answer.py`, `test_telegram_channel.py`, `test_telegram_config_migration.py`, `test_channel_contract.py`. Integration: `test_the_composed_app_moves_the_telegram_token_and_delivers.py`.

## Implementation notes (written when done)
2026-10-20. Branch `claude/epic-036c-telegram-channel`, from `master-warrior` after `036B` (#651).

- The Telegram answer text is never echoed: a reason names the status and a fixed instruction, not Telegram's description (which an exchange-style message could shape).
- `TelegramChannel` keeps no state and reads both secrets at each send, so a rotated token applies to the next message without a restart; the lane itself exists only if both were stored at boot (a first save needs a restart, as for Discord).
- The Options page has no Telegram fields yet (`036C` remainder with `036D`).

Not run: a real Telegram message; the migration against a real keyring.

## Resume
Done. The owner's check: store the two values (desktop: set `notifications.telegram.*` in `user_config.json` and start the app, then see them gone from the file and `telegram is on` in the log; server: runbook §3b2), then `alert test` and read the message in the chat.
