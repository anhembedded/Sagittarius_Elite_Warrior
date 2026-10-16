Status: Current

# `alerting` — 8. Concepts: the data model and what is stored

*What is an alert, what is stored, in what shape, and what is kept in memory on purpose?* The
patterns the module applies are named where they act: the transactional outbox, at-least-once
([`05-building-blocks.md`](05-building-blocks.md), [`06-runtime.md`](06-runtime.md)), and the
anti-corruption layer at the edge (`BotAlertSource`, same file).

## Built: the domain

An `Alert` is frozen: kind, severity, subject, title, detail, time (UTC), `dedup_key`
naming the *condition*, and a `recovery` flag (`alerting/domain/alert.py:18-45`); `Alert.raised`
keys it by kind, subject identity and reason (`:46-66`) through `Alert.condition_key` (`:67-71`). The
subject is a bot, a venue or the app (`alerting/domain/alert_subject.py:9-59`); a bot subject carries
id, name, kind, venue and symbol, so a later "stop this bot" can point at the right one. Each
`AlertKind` (`alerting/domain/alert_kind.py:9-30`) has one group, one default severity and one label
in `KIND_PROFILES` (`alerting/domain/alert_catalog.py:31-74`); `TEST` is the Send test's.
`AlertSettings` holds disabled channels, route cells, per-bot modes and quiet hours, and **no
secret** (`alerting/domain/alert_settings.py:20-43`).

## Built: the outbox

The outbox is one SQLite file, `<data root>/state/alerts.sqlite3`
(`alerting/composition/alerting_bindings.py:94-95`), schema version 1
(`alerting/adapters/sqlite_outbox.py:49-85`): table `alerts` (the alert's fields plus `count` and
`last_at`, so a repeat is one row with a counter) and table `deliveries` (one row per alert and
channel: loudness, state, attempts, next attempt time, a sanitised reason). A file written by a newer
schema is refused (`sqlite_outbox.py:104-113`). The records that cross the port are in
`alerting/contracts/outbox_records.py:15-76`.

## Built: in memory, on purpose

Dedup windows, groups, inhibitors and the held quiet-hours list are in memory and do not survive a
restart, on purpose: after a restart a repeat is heard twice, never zero times
(`alert_deduplicator.py:29-32`, `condition_book.py:32-34`).

The skeleton (`EPIC-036G`) stores nothing new in the outbox. The Discord webhook is a secret named
`alerting_discord_webhook` (`discord_webhook_channel.py:43`), read by name at each send and never
written by the app on a headless host (ADR 036 of 2026-10-15, D3). The per-bot last-seen state of
`BotAlertSource` is in memory and is seeded from the bots' report at boot, without alerting
(`bot_alert_source.py:108-120`).
