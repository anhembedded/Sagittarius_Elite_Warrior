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

## Built: the Options page, Save and Send test

The picture: [`diagrams/06-options-save-and-test.puml`](diagrams/06-options-save-and-test.puml).
*Which thread does what, and where does the URL go?* Tools → Options → Alerts has one Discord
webhook field, masked, and the buttons Save, Remove and Send test. Each acts at once and runs off the
UI thread: the presenter begins an action (`alerts_settings_presenter.py:182-187`), the pool thread
runs the use case and reads the new state beside it, so a locked keyring never blocks the UI thread (`:188-199`), and `AlertsActionRelay` delivers the answer on the UI thread, where
the tracker checks the action is still the current one (`:200-223`; a stale or post-`shutdown()`
answer is dropped, `:119-123`). The buttons are off while one runs.

- **Save** puts the typed text in `DiscordWebhookSetup.save`: a value that is not a Discord webhook URL
  is refused with a sentence and nothing is written; a valid one goes to the keyring, the field is
  cleared and the page shows only the last four characters of the token
  (`discord_webhook_setup.py:93-117`). A host that provisions the webhook elsewhere answers first on
  read, so the page says "saved, but not used" and never "saved".
- **Send test** builds the catalog again and sends one loud TEST alert straight to the channel, as
  `alert test` does, so a webhook saved a moment ago is tested without a restart
  (`send_test_to_configured_channels.py:31-34`). The page shows the channel's own sanitised reason
  ("Discord refused the webhook message (404)").
- **Remove** asks first, with its own verbs (Remove webhook / Keep webhook) and the safe one as the
  default (`alerts_settings_view.py`, `confirm_removal`).

**Restart or hot rebuild: restart.** The lanes are started once at boot from the catalog's ids
(`threaded_delivery_host.py:41-72`, `alerting_bindings.py:203`), and the hub, the status port and the
delivery pass hold the run's catalog, which is fixed for its life. A hot rebuild would need a mutable
catalog, lanes started and stopped while the hub routes, and a status that changes under the host's
warning: machinery on the delivery path, and a real-money-adjacent one, for a setting changed once. So
a replaced webhook applies at the next send (the channel reads its secret at each send,
`discord_webhook_channel.py:51-52`), but a first save or a removal changes the lane only after a
restart, and the page says so in its channel line (`alerts_words.py:86-107`): "Saved, not sending yet:
restart the app to start sending", "Removed, but this run still has the Discord channel: its alerts
are refused until you restart the app". Whether the lane can start without a restart is a task of its
own if the owner wants it (`EPIC-036D`).

**No URL anywhere.** An unexpected exception raised under a save or a test can quote the webhook, so
the page shows and logs the exception's type name only (`alerts_settings_presenter.py:188-199`,
`:237-250`); `test_alerts_page_never_shows_the_url.py` locks the logs, the notice and the labels on
every path.

## Planned

Telegram and the remote command are drawn in design 036 §9 and §11 and are drawn here when
`EPIC-036C` and `036F` build them.
