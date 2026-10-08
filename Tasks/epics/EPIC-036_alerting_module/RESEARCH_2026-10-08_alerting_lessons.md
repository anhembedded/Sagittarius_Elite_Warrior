# RESEARCH — Lessons from real users and operators of alerting and trading bots

**Epic:** [EPIC-036](README.md)
**Date:** 2026-10-08
**Collected by:** the coordinator session, for the owner, before the design was approved; handed over to this epic so no later session has to search again. Used by [`DESIGN_2026-10-08_alerting_module.md`](DESIGN_2026-10-08_alerting_module.md).

> **Caveat.** Most sources are vendor blogs or single anecdotes. **Every number below is indicative and is "to verify against real response headers when implemented"**; the implementing task records the measured values in its own notes.

## 1. Discord: a 429 counts as an invalid request, and too many get the IP blocked
- The docs say: do not hard-code limits; read the rate-limit headers and `retry_after`. Too many invalid requests (a 429 is one) get the whole IP temporarily blocked from the Discord API, so **every** message is lost.
- Webhook limits are reported inconsistently: about 5 messages per 2 s per webhook, 30 requests per 5 s, about 30 messages per minute per channel (to verify).
- **Design consequence:** a queue per channel; never retry before `retry_after`; a bounded number of retries (5), then `CHANNEL_FAILING`; a test that asserts no request is sent before `retry_after`. → [036A](incomplete/EPIC-036A_alerting_core.md), [036C](incomplete/EPIC-036C_discord_channel_and_telegram_migration.md)
- Sources: https://docs.discord.com/developers/topics/rate-limits · https://space-node.net/blog/discord-webhook-rate-limits-official-2026 · https://help.squarecloud.app/en-us/article/how-to-handle-rate-limits-in-the-discord-api-mkkz7n/ · https://client.falixnodes.net/guides/troubleshooting/discord-rate-limits

## 2. Telegram: tight per-chat limits and waits that can last hours
- About 1 message per second per chat, about 20 per minute per group, about 30 per second globally (to verify). A 429 carries `parameters.retry_after`; after bursts it can reach hours (one real log reads `retry after 26965`, about 7.5 h).
- **Design consequence:** per-chat pacing; when `retry_after` exceeds 5 minutes a CRITICAL alert fails over to another channel; coalescing is the main defence. → 036A, 036C
- Sources: https://qna.habr.com/q/1017438 · https://telega.hexdocs.pm/telega/broadcast.html · https://telegram.js.org/docs/rest/TelegramError/

## 3. Critical alerts get stuck behind noise
- Common advice: a separate webhook for critical alerts, and batching noisy events.
- **Design consequence:** a priority queue with CRITICAL first; INFO is dropped before CRITICAL ever is; the Options page suggests a dedicated critical channel. → 036A, [036D](incomplete/EPIC-036D_alerts_ui.md)

## 4. "Sent" is not "seen"
- Telegram Android push notifications can arrive 30 minutes late or never (weak network, battery saving). A 3Commas user reported notifications inconsistent between the app and Telegram.
- **Design consequence:** CRITICAL goes to two channels when two exist (N8); the UI words delivery status as "accepted by Discord/Telegram"; a Phase-4 acknowledgement is motivated by this. → 036A, 036D, [036F](incomplete/EPIC-036F_remote_control_from_discord.md)
- Sources: https://bugs.telegram.org/c/40870/1 · https://justuseapp.com/en/app/1370977008/3commas-crypto-trading-tools/contact

## 5. A Telegram bot cannot message a user who never pressed /start
- "chat not found" means a wrong chat id, a blocked bot, or no `/start`.
- **Design consequence:** Send test maps these errors to plain guidance. → 036C, 036D

## 6. Freqtrade: three levels per message type, and the control risks
- Each message type is on / silent / off, and noisy types are recommended off. Adding the bot to a Telegram group gives every member control. `authorized_users` limits control by user ID; an empty list means nobody controls the bot but messages still go out. Anyone holding the bot token can control the bot. The REST API should not be exposed (localhost plus an SSH tunnel).
- **Design consequence:** loudness is loud / silent / off (Discord `@silent`, Telegram `disable_notification`); remote control authorises by user-ID allowlist, never by channel or group; an empty allowlist means receive-only; nothing listens on a port (the Discord gateway is outbound). → 036A, 036C, 036F
- Sources: https://dev.to/henry_lin_3ac6363747f45b4/lesson-17-telegram-setup-1241 · https://gitea.com/freebitcoingenerator/free-bitcoin-generator/src/branch/develop/docs/telegram-usage.md · https://dev.to/henry_lin_3ac6363747f45b4/lesson-18-web-ui-and-api-usage-20f0

## 7. A leaked Discord webhook lets anyone post to the channel
- There is no authentication and no signature; leaked webhooks are abused, including for data exfiltration. The response is to delete and recreate the webhook.
- **Design consequence:** the webhook lives in the keyring only; a "Rotate webhook" action; the Options page states that a message in the channel is not proof, check the app; remote control never takes commands through a webhook; a test that the secret is never in logs or errors. → 036C, 036D, 036F
- Sources: https://www.gitguardian.com/remediation/discord-webhook-url · https://documentation.sailpoint.com/entro/help/supported-secrets/specific-secrets/discord-webhook-url.html · https://www.securityscientist.net/blog/12-questions-and-answers-about-discord-webhook-abuse/

## 8. Grid bots fail silently on stops
- A Gainium grid bot's stop loss did not execute because of an exchange-specific bug (Binance US); stopping a grid bot left the deal open with no prompt.
- **Design consequence:** `AlertKind.STOP_FAILED` (CRITICAL) fires when a Stop or stop loss does not complete, or leaves orders or balance behind. The owner hit this class of defect on 2026-10-08 (`BUG-191`, a stop loss missed on a wick). → 036A, [036B](incomplete/EPIC-036B_alert_sources.md)
- Sources: https://community.gainium.io/t/stop-loss-in-grid-bot-not-executing-binanceus/1079 · https://community.gainium.io/t/grid-bot-failed-to-close-the-deal-when-you-stop-the-bot/1965 · https://intercom.help/pionex/en/articles/15500905-grid-trading-bot-faq

## 9. Alert fatigue
- Dedup by fingerprint, so a repeat updates one record with a count. Group by stable keys (service, environment, time window), not by wording; keys that are too broad hide critical alerts. Inhibition: a parent alert suppresses its children. Urgency tiers. Prune alerts nobody acts on.
- **Design consequence:** `dedup_key` with a counter row in the dock; group by kind + venue; a venue-down alert inhibits per-bot feed-stale alerts; severity tiers; a recovery message. → 036A, 036B, 036D
- Sources: https://betterstack.com/community/guides/monitoring/best-practices-alert-fatigue.md · https://rootly.com/alert-management/alert-deduplication-and-correlation.md · https://www.techinterview.org/post/3233469424/lld-alerting-system/

## 10. A dead monitor is silent
- The fix is a watchdog / dead man's switch: an external service expects a periodic ping and alerts when it stops.
- **Design consequence:** N7, a ping adapter to healthchecks.io or a URL the owner picks, every 5 minutes, off by default, the URL in the keyring. → [036E](incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md)
- Source: the sources of §9.
