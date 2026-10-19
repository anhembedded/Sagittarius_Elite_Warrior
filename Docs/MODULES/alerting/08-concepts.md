Status: Current

# `alerting` — 8. Concepts: the data model and what is stored

*What is an alert, what is stored, in what shape, and what is kept in memory on purpose?* The
patterns the module applies are named where they act: the transactional outbox, at-least-once
([`05-building-blocks.md`](05-building-blocks.md), [`06-runtime.md`](06-runtime.md)), and the
anti-corruption layer at the edge (`BotAlertSource`, same file).

## Built: the domain

An `Alert` is frozen: kind, severity, subject, title, detail, time (UTC), `dedup_key` naming the
*condition*, and a `recovery` flag (`alerting/domain/alert.py` → `Alert`); `Alert.raised` keys it by
kind, subject identity and reason (`alert.py` → `Alert.raised`) through `Alert.condition_key`. The
subject is a bot, a venue or the app (`alerting/domain/alert_subject.py` → `AlertSubject`,
`SubjectScope`); a bot subject carries id, name, kind, venue and symbol, so a later "stop this bot"
can point at the right one. Each `AlertKind` (`alerting/domain/alert_kind.py` → `AlertKind`) has one
group, one default severity and one label in `KIND_PROFILES` (`alerting/domain/alert_catalog.py` →
`KIND_PROFILES`); `TEST` is the Send test's; `ORDER_FILLED`, `FILLS_SKIPPED` (`BOT-189`) and `EXIT_CLOSED` (`BOT-190`) are INFO in the `ROUTINE` group,
so by N4's defaults they are sent without a sound. `AlertSettings` holds disabled channels, route cells,
per-bot modes and quiet hours, and **no secret** (`alerting/domain/alert_settings.py` →
`AlertSettings`).

## Built: the outbox

The outbox is one SQLite file, `<data root>/state/alerts.sqlite3`
(`alerting/composition/alerting_bindings.py` → `outbox_path`), schema version 1
(`alerting/adapters/sqlite_outbox.py` → `SCHEMA_VERSION`, `_SCHEMA`): table `alerts` (the alert's
fields plus `count` and `last_at`, so a repeat is one row with a counter) and table `deliveries`
(one row per alert and channel: loudness, state, attempts, next attempt time, a sanitised reason). A
file written by a newer schema is refused (`sqlite_outbox.py` → `SqliteOutbox._prepare`). The
records that cross the port are in `alerting/contracts/outbox_records.py`.

## Built: in memory, on purpose

Dedup windows, groups, inhibitors and the held quiet-hours list are in memory and do not survive a
restart, on purpose: after a restart a repeat is heard twice, never zero times
(`alert_deduplicator.py` → `AlertDeduplicator`; `condition_book.py` → `ConditionBook`).

The skeleton (`EPIC-036G`) stores nothing new in the outbox. The Discord webhook is a secret named
`alerting_discord_webhook` (`discord_webhook_channel.py` → `DISCORD_WEBHOOK_SECRET`), read by name
at each send and never written by the app on a headless host (ADR 036 of 2026-10-15, D3). On a
desktop the only writer is the Options page, through `DiscordWebhookSetup`, to the keyring entry of
that name (`discord_webhook_setup.py` → `DiscordWebhookSetup.save`, `DiscordWebhookSetup.remove`);
the page keeps nothing of the URL but the last four characters of its token, read back each time
(`DiscordWebhookSetup.state`), and the line edit is cleared once the webhook is saved. The fill messages add no
column and no table: a fill is an ordinary alert row whose `dedup_key` ends with the order's id. No
setting mutes them yet beyond a per-bot mode in the code (`AlertSettings.bot_modes`); the Options
page has no control for it, so every bot's fills are sent (limit, see `Tasks/proposal/PRO-015.md`). The per-bot
last-seen state of `BotAlertSource` is in memory and is seeded from the bots' report at boot,
without alerting (`bot_alert_source.py` → `BotAlertSource.seed`).
