Status: Current

# `alerting` — 6. Runtime

*What happens, step by step, on the journeys that matter?*

## Built: one alert from `publish` to a channel

`publish` takes the hub's lock, runs the steps of [`05-building-blocks.md`](05-building-blocks.md)
and writes one alert row and one delivery row per admitted channel in one transaction
(`alert_hub.py` → `AlertHub._accept`; `sqlite_outbox.py` → `SqliteOutbox.enqueue`), then nudges the
lanes ( `alerting/adapters/wake_signal.py` → `WakeSignal.notify`). Each lane wakes, expires what is
too old, takes the due delivery of the highest severity and calls the channel outside every lock
(`channel_delivery.py` → `ChannelDelivery.run_due`, `ChannelDelivery._call`). A wait the platform
asks for pauses the whole channel, not one message, and survives a restart, because the next process
reads it back from the open `RETRYING` rows (`channel_delivery.py` → `ChannelDelivery._pause_until`;
`sqlite_outbox.py` → `SqliteOutbox.retry_horizon`). A CRITICAL left behind a wait longer than five
minutes is queued on another channel (`channel_delivery.py` →
`ChannelDelivery._fail_over_waiting_criticals`). Grouped alerts and the quiet-hours summary leave
from the housekeeping tick, `AlertHub.flush_due` (`alert_hub.py` → `AlertHub.flush_due`). A source
that sees its condition clear calls `condition_cleared`, which sends one INFO "Recovered" alert and
re-arms the key (`alert_hub.py` → `AlertHub.condition_cleared`).

## Built: boot

At boot the module starts the lanes, subscribes the bot sources to the bots' events, then seeds the
state source from the bots' report without alerting (`alerting/module.py` → `AlertingModule.boot`).
A read-only copy returns before any of it.

## Built: the skeleton journey — a bot halts on the VPS, Discord hears it once

The picture: [`diagrams/06-halt-to-discord.puml`](diagrams/06-halt-to-discord.puml). *Which thread
does what, and where is the alert safe if the process dies?* What the skeleton is, and what in it is
real: [`04-solution-strategy.md`](04-solution-strategy.md).

If the process dies after `enqueue`, the alert is sent at the next start; if it dies between
Discord's answer and `mark`, it is sent twice (at-least-once, the docstring of `alerting/contracts/i_outbox.py`).
A halt written by the bots' store and lost before `publish` is not covered: the source seeds its
last-seen states at boot without alerting, so the skeleton does not re-alert old halts on every
restart. `EPIC-036B` decides whether a boot-time "still halted" summary is wanted.

## Built: a filled order, a cycle and an exit reach Discord

`BOT-189`, `PRO-015` phase 1. On the bot's worker, `on_fill` returns the orders a fact filled whole
beside the new runtime (`bots/domain/grid/grid_reactions.py` → `on_fill`, `Reaction.filled`;
`grid_filled_order.py` → `FilledOrder`), with the cycle profit `book_cycle` booked and the run's totals
right after it. The executor saves the runtime, then publishes one `BotOrderFilledEvent` per filled
order (`bots/application/kinds/grid/grid_facts.py` → `GridFacts._apply_fill`;
`grid_fill_announcer.py` → `GridFillAnnouncer.announce`); a fill a reconcile applies from history after
a restart is announced the same way (`grid_missed_fills.py` → `GridMissedFills._apply_missed`). The
alerting source words it and calls `publish` (`BotFillAlertSource.on_order_filled`); the hub treats it as
any INFO: deduplicated by the order, held in quiet hours, routed silent, bounded by `FillBacklog`.
A partial fill, a trade the run already counted and an exit's market sell announce nothing. A stop loss,
a take profit or a range exit that closes is `STOPPING` with its reason: `BotAlertSource` raises the
CRITICAL at once, with the bot's own detail ("price 2290, traded to 2288"). Nothing here places or
changes an order.

**What a restart does.** The bot counts a fill once and so publishes it once; the dedup windows are in
memory ([`08-concepts.md`](08-concepts.md)), so the guarantee is the bot's, not the hub's. A fill that
happened while the app was closed is told once, by the reconcile that finds it.

**What is not measured.** Discord's real behaviour under a burst. What is measured, on the fake
channel (`tests/unit/modules/alerting/application/test_fill_backlog.py`): with a channel that answers 429,
60 fills and one CRITICAL, the lane tries nothing until the wait is over, then sends the CRITICAL first,
the newest 25 fills and one "35 fill messages skipped" line.

## Built: the Options page, Save and Send test

The picture: [`diagrams/06-options-save-and-test.puml`](diagrams/06-options-save-and-test.puml).
*Which thread does what, and where does the URL go?* Tools → Options → Alerts has one Discord
webhook field, masked, and the buttons Save, Remove and Send test. Each acts at once and runs off
the UI thread: the presenter begins an action (`alerts_settings_presenter.py` →
`AlertsSettingsPresenter._begin`), the pool thread runs the use case and reads the new state beside
it, so a locked keyring never blocks the UI thread (`AlertsSettingsPresenter._work_on_pool`), and
`AlertsActionRelay` delivers the answer on the UI thread, where the tracker checks the action is
still the current one (`AlertsSettingsPresenter._on_action_done`; a stale or post-`shutdown()`
answer is dropped, `AlertsSettingsPresenter.shutdown`). The buttons are off while one runs.

- **Save** puts the typed text in `DiscordWebhookSetup.save`: a value that is not a Discord webhook
  URL is refused with a sentence and nothing is written; a valid one goes to the keyring, the field
  is cleared and the page shows only the last four characters of the token
  (`discord_webhook_setup.py` → `DiscordWebhookSetup.save`). A host that provisions the webhook
  elsewhere answers first on read, so the page says "saved, but not used" and never "saved".
- **Send test** builds the catalog again and sends one loud TEST alert straight to the channel, as
  `alert test` does, so a webhook saved a moment ago is tested without a restart
  (`send_test_to_configured_channels.py` → `SendTestToConfiguredChannels.run`). The page shows the
  channel's own sanitised reason ("Discord refused the webhook message (404)").
- **Remove** asks first, with its own verbs (Remove webhook / Keep webhook) and the safe one as the
  default (`alerts_settings_view.py` → `confirm_removal`).

**Restart or hot rebuild: restart.** The lanes are started once at boot from the catalog's ids
(`threaded_delivery_host.py` → `ThreadedDeliveryHost.start`; `alerting_bindings.py` →
`bind_alerting`), and the hub, the status port and the delivery pass hold the run's catalog, which
is fixed for its life. A hot rebuild would need a mutable catalog, lanes started and stopped while
the hub routes, and a status that changes under the host's warning: machinery on the delivery path,
and a real-money-adjacent one, for a setting changed once. So a replaced webhook applies at the next
send (the channel reads its secret at each send, `discord_webhook_channel.py` →
`DiscordWebhookChannel.deliver`), but a first save or a removal changes the lane only after a
restart, and the page says so in its channel line (`alerts_words.py` → `channel_line`): "Saved, not
sending yet: restart the app to start sending", "Removed, but this run still has the Discord
channel: its alerts are refused until you restart the app". Whether the lane can start without a
restart is a task of its own if the owner wants it (`EPIC-036D`).

**No URL anywhere.** An unexpected exception raised under a save or a test can quote the webhook, so
the page shows and logs the exception's type name only (`alerts_settings_presenter.py` →
`AlertsSettingsPresenter._work_on_pool`, `AlertsSettingsPresenter._tell_failed`);
`test_alerts_page_never_shows_the_url.py` locks the logs, the notice and the labels on every path.

## Planned

Telegram and the remote command are drawn in design 036 §9 and §11 and are drawn here when
`EPIC-036C` and `036F` build them.
