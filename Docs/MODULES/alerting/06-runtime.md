Status: Current

# `alerting` — 6. Runtime

*What happens, step by step, on the journeys that matter?*

## Built: one alert from `publish` to a channel

`publish` takes the hub's lock, runs the steps of [`05-building-blocks.md`](05-building-blocks.md)
and writes one alert row and one delivery row per admitted channel in one transaction
(`alert_hub.py:205-246`, `sqlite_outbox.py:126-154`), then nudges the lanes (`WakeSignal`,
`alerting/adapters/wake_signal.py:23-26`). Each lane wakes, expires what is too old, takes the due
delivery of the highest severity and calls the channel outside every lock
(`channel_delivery.py:68-90`, `:149-159`). A wait the platform asks for pauses the whole channel,
not one message, and survives a restart, because the next process reads it back from the open
`RETRYING` rows (`channel_delivery.py:173-185`, `sqlite_outbox.py:235-242`). A CRITICAL left
behind a wait longer than five minutes is queued on another channel (`channel_delivery.py:135-147`).
Grouped alerts and the quiet-hours summary leave from the housekeeping tick, `AlertHub.flush_due`
(`alert_hub.py:139-151`). A source that sees its condition clear calls `condition_cleared`, which
sends one INFO "Recovered" alert and re-arms the key (`alert_hub.py:112-135`).

## Built: boot

At boot the module starts the lanes, subscribes the bot source to both bots events, then seeds it
from the bots' report without alerting (`alerting/module.py:111-125`).

## Built: the skeleton journey — a bot halts on the VPS, Discord hears it once

The picture: [`diagrams/06-halt-to-discord.puml`](diagrams/06-halt-to-discord.puml). *Which thread
does what, and where is the alert safe if the process dies?* What the skeleton is, and what in it is
real: [`04-solution-strategy.md`](04-solution-strategy.md).

If the process dies after `enqueue`, the alert is sent at the next start; if it dies between
Discord's answer and `mark`, it is sent twice (at-least-once, `alerting/contracts/i_outbox.py:1-10`).
A halt written by the bots' store and lost before `publish` is not covered: the source seeds its
last-seen states at boot without alerting, so the skeleton does not re-alert old halts on every
restart. `EPIC-036B` decides whether a boot-time "still halted" summary is wanted.

## Planned

Telegram, the Options page's Send test and the remote command are drawn in design 036 §9 and §11 and
are drawn here when `EPIC-036C`, `036D` and `036F` build them.
