Status: Current

# `alerting` — 5. Building blocks

*Which classes carry an alert, which one calls which, and what are the domain types and contracts?*

Five pictures, drawn by hand at a high level, one question each:

- [`diagrams/05-publish-path.puml`](diagrams/05-publish-path.puml) — *what runs on the caller's
  thread when an alert is raised, and where does it stop?*
- [`diagrams/05-delivery-path.puml`](diagrams/05-delivery-path.puml) — *what runs on a channel's
  lane, from the outbox to Discord?*
- [`diagrams/05-channel-catalog.puml`](diagrams/05-channel-catalog.puml) — *where is a channel
  registered, and who asks whether one is carried?*
- [`diagrams/05-domain.puml`](diagrams/05-domain.puml) — *what is an alert made of, and which values
  describe its delivery?*
- [`diagrams/05-contracts.puml`](diagrams/05-contracts.puml) — *which ports does a channel or a
  source build against?*

## Built: an alert's path, in classes

- **`AlertHub`** (`alerting/application/alert_hub.py` → `AlertHub`) is the publisher. `publish` runs
  on the caller's thread and only writes the outbox (`AlertHub.publish`, `AlertHub._accept`): in
  order it **inhibits** through `ConditionBook` (`condition_book.py` →
  `ConditionBook.inhibitor_of`), **deduplicates** through `AlertDeduplicator`
  (`alert_deduplicator.py` → `AlertDeduplicator.repeat_of`), **holds** INFO and WARNING in quiet
  hours through `QuietHoursHold` (`quiet_hours_hold.py` → `QuietHoursHold.hold`), **groups** one
  kind and venue through `AlertCoalescer` (`alert_coalescer.py` → `AlertCoalescer.add`), then
  **routes** through `AlertRouter` (`alert_router.py` → `AlertRouter.route`) and **admits** each
  target to its channel's bounded queue through `DeliveryAdmission` (`delivery_admission.py` →
  `DeliveryAdmission.admit`). It is also the worker's one door back, `IDeliveryFollowUp`
  (`alert_hub.py` → `AlertHub.channel_failing`, `AlertHub.fail_over`).
- **`SqliteOutbox`** (`alerting/adapters/sqlite_outbox.py` → `SqliteOutbox`) implements `IOutbox`
  (`alerting/contracts/i_outbox.py` → `IOutbox`): the transactional outbox, at-least-once.
- **`ChannelDelivery`** (`alerting/application/channel_delivery.py` → `ChannelDelivery`) is one
  worker pass over one channel, with no thread of its own (`channel_delivery.py` →
  `ChannelDelivery.run_due`); **`ThreadedDeliveryHost`**
  (`alerting/adapters/threaded_delivery_host.py` → `ThreadedDeliveryHost`) runs it on a lane per
  channel.
- **`RegisteredChannelCatalog`** (`alerting/adapters/registered_channel_catalog.py` →
  `RegisteredChannelCatalog`), built from `CHANNEL_DESCRIPTORS`
  (`alerting/composition/channel_bindings.py` → `CHANNEL_DESCRIPTORS`), is the one list a channel is
  added to. The test double is `FakeAlertChannel`
  (`alerting/contracts/testing/fake_alert_channel.py` → `FakeAlertChannel`).
- **`InMemoryAlertSettings`** (`alerting/adapters/memory_alert_settings.py` →
  `InMemoryAlertSettings`) holds N4's defaults behind `IAlertSettingsSource`; `NullAlertPublisher`
  stands in on a read-only copy (`alerting/composition/alerting_bindings.py` → `bind_alerting`);
  `AlertingHealthContributor` (`alerting/application/alerting_health_contributor.py` →
  `AlertingHealthContributor`) reports the backlog.

The walking skeleton (`EPIC-036G`) added:

- **`BotAlertSource`** (`alerting/application/sources/bot_alert_source.py` → `BotAlertSource`), the
  anti-corruption layer at the edge: `on_bot_changed` reads the bot and alerts on the *entry* into a
  state of `ALERT_ON_ENTRY` (`bot_alert_source.py` → `ALERT_ON_ENTRY`); `on_stop_gave_up` raises
  `STOP_FAILED` even when the bot cannot be read (`bot_alert_source.py` →
  `BotAlertSource.on_stop_gave_up`); `on_recovery_stalled` raises the one `BOT_RECOVERY_STALLED`
  warning of a bot that waits in `AWAITING_RECOVERY` (a wait is silent on entry, so it is not in
  `ALERT_ON_ENTRY`; the bot leaving the wait is in `CLEARED_ON_ENTRY`); `on_auto_recovered` raises a
  `BOT_AUTO_RECOVERED` warning for each automatic recovery, keyed by the attempt so a second
  recovery inside the dedup window is not a count on the first; the `BOT_HALTED` alert's `Reason:`
  line carries the bot's `reason_detail` (`bot_alert_source.py` → `_reason_line`), which is where
  "the automatic recoveries are used up" is said; the entry into a state of `CLEARED_ON_ENTRY`
  (`bot_alert_source.py` → `CLEARED_ON_ENTRY`) calls `condition_cleared` with the key
  `Alert.condition_key` gives (`alerting/domain/alert.py` → `Alert.condition_key`).
- **`DiscordWebhookChannel`** (`alerting/adapters/discord_webhook_channel.py` →
  `DiscordWebhookChannel`) joins `discord_payload` (`alerting/adapters/discord_message.py` →
  `discord_payload`) and `result_of` (`alerting/adapters/discord_answer.py` → `result_of`); it reads
  `alerting_discord_webhook` at each send (`discord_webhook_channel.py` → `DISCORD_WEBHOOK_SECRET`,
  `DiscordWebhookChannel.deliver`). The transport is **`UrllibWebhookTransport`**
  (`alerting/adapters/urllib_webhook_transport.py` → `UrllibWebhookTransport`); its test double is
  **`FakeWebhookTransport`** (`alerting/contracts/testing/fake_webhook_transport.py` →
  `FakeWebhookTransport`), and both pass one contract suite
  (`alerting/contracts/testing/contract_webhook_transport.py`).
- **`discord_channel`** (`alerting/composition/channel_bindings.py` → `discord_channel`), the
  descriptor's factory: it answers `None` when no webhook, or no Discord webhook URL, is stored, so
  an unconfigured channel is not in the catalog and starts no lane (`channel_bindings.py` →
  `build_channel_catalog`). Its secrets come from `ChannelSecrets` (`channel_bindings.py` →
  `ChannelSecrets`), bound to `build_secret_stores()` of `support/secrets` (`alerting_bindings.py` →
  `bind_alerting`).
- **`ChannelAlertingStatus`** (`alerting/application/channel_alerting_status.py` →
  `ChannelAlertingStatus`): a channel is carried when it is in the catalog and not disabled.
- **`SendTestMessage`** (`alerting/application/send_test_message.py` → `SendTestMessage`) and
  **`AlertCliHandler`** (`alerting/cli/alert_cli_handler.py` → `AlertCliHandler`): `alert test`, one
  loud `TEST` alert per channel, straight to the channel and never through the outbox (design 036
  §9).

The Options page (`EPIC-036D1`) added:

- **`DiscordWebhookSetup`** (`alerting/application/discord_webhook_setup.py` →
  `DiscordWebhookSetup`), the only write path the app has for a channel's secret: `save` strips and
  validates with `is_discord_webhook_url` (injected through `discord_webhook_setup.py` →
  `WebhookChannelSpec`, so the application layer imports no adapter), writes through `ISecretStore`
  and reads back to catch a store that answers first (`OVERRIDDEN`; `DiscordWebhookSetup.save`);
  `remove` does the same for deletion (`DiscordWebhookSetup.remove`); `state` answers
  `DiscordChannelState`: stored, usable, the last four characters of the token, and whether this run
  has the lane (`discord_webhook_setup.py` → `DiscordWebhookSetup.state`, `DiscordChannelState`). It
  returns enums and a hint, never the URL.
- **`SendTestToConfiguredChannels`** (`alerting/application/send_test_to_configured_channels.py` →
  `SendTestToConfiguredChannels`) is `SendTestMessage` over a catalog built again for each test, by
  **`IChannelCatalogBuilder`** (`alerting/contracts/i_channel_catalog_builder.py`) and its adapter
  **`DescriptorChannelCatalogBuilder`** (`alerting/composition/channel_bindings.py` →
  `DescriptorChannelCatalogBuilder`), which runs `build_channel_catalog` again. The run's own
  catalog is not touched.
- **The page**, in `alerting/ui/options/`: `AlertsSettingsPresenter` (`alerts_settings_presenter.py`
  → `AlertsSettingsPresenter`, an `OptionsSectionPresenter` that is never dirty), its view and view
  model, `AlertsActionRelay` (`alerts_action_relay.py` → `AlertsActionRelay`, a `UiThreadRelay`) and
  the page's sentences (`alerts_words.py`). The module contributes it as the `Deferred`
  `_OPTIONS_PAGE` (`alerting/module.py` → `_OPTIONS_PAGE`, `AlertingModule.contribute`), order 30
  after Trading and Market Data.

Every binding is in `alerting/composition/alerting_bindings.py` → `bind_alerting`, the page's three
among them.

## Planned

| Class | Where | Task |
| :--- | :--- | :--- |
| `StreamAlertSource`, `SystemAlertSource` (replaces `NotificationEventHandler`) | `alerting/application/sources/` | `EPIC-036B` |
| `TelegramChannel` (moved), the token migration, the embed layout, pacing, `RotateSecret` | `alerting/adapters/`, `alerting/application/` | `EPIC-036C` |
| The channels table, routing matrix and schedule of the Options page, the Alerts dock, the status-bar indicator, the per-bot menu item; a persisted `IAlertSettingsSource` | `alerting/ui/`, `alerting/adapters/` | `EPIC-036D` |
| `HeartbeatService`, the dead man's switch pinger | `alerting/application/`, `alerting/adapters/` | `EPIC-036E` |
| `IRemoteCommandSource`, `RemoteCommandGate` | `alerting/` | `EPIC-036F` |
