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

- **`AlertHub`** (`alerting/application/alert_hub.py:80`) is the publisher. `publish` runs on the
  caller's thread and only writes the outbox (`:108-110`, `:205-246`): in order it **inhibits**
  through `ConditionBook` (`condition_book.py:95-109`), **deduplicates** through `AlertDeduplicator`
  (`alert_deduplicator.py:38-46`), **holds** INFO and WARNING in quiet hours through `QuietHoursHold`
  (`quiet_hours_hold.py:29-40`), **groups** one kind and venue through `AlertCoalescer`
  (`alert_coalescer.py:49-65`), then **routes** through `AlertRouter` (`alert_router.py:32-71`) and
  **admits** each target to its channel's bounded queue through `DeliveryAdmission`
  (`delivery_admission.py:26-45`). It is also the worker's one door back, `IDeliveryFollowUp`
  (`channel_failing`, `fail_over`, `alert_hub.py:160-201`).
- **`SqliteOutbox`** (`alerting/adapters/sqlite_outbox.py:92`) implements `IOutbox`
  (`alerting/contracts/i_outbox.py:30-97`): the transactional outbox, at-least-once.
- **`ChannelDelivery`** (`alerting/application/channel_delivery.py:48`) is one worker pass over one
  channel, with no thread of its own (`run_due`, `:68-90`); **`ThreadedDeliveryHost`**
  (`alerting/adapters/threaded_delivery_host.py:37`) runs it on a lane per channel.
- **`RegisteredChannelCatalog`** (`alerting/adapters/registered_channel_catalog.py:15`), built from
  `CHANNEL_DESCRIPTORS` (`alerting/composition/channel_bindings.py:91-93`), is the one list a channel
  is added to. The test double is `FakeAlertChannel` (`alerting/contracts/testing/fake_alert_channel.py:35`).
- **`InMemoryAlertSettings`** (`alerting/adapters/memory_alert_settings.py:21`) holds N4's defaults
  behind `IAlertSettingsSource`; `NullAlertPublisher` stands in on a read-only copy
  (`alerting/composition/alerting_bindings.py:132-139`); `AlertingHealthContributor`
  (`alerting/application/alerting_health_contributor.py:31`) reports the backlog.

The walking skeleton (`EPIC-036G`) added:

- **`BotAlertSource`** (`alerting/application/sources/bot_alert_source.py:95`), the anti-corruption
  layer at the edge: `on_bot_changed` reads the bot and alerts on the *entry* into a state of
  `ALERT_ON_ENTRY` (`:82-84`); `on_stop_gave_up` raises `STOP_FAILED` even when the bot cannot be
  read (`:140-153`); the entry into a state of `CLEARED_ON_ENTRY` (`:86-92`) calls
  `condition_cleared` with the key `Alert.condition_key` gives (`alerting/domain/alert.py:67-71`).
- **`DiscordWebhookChannel`** (`alerting/adapters/discord_webhook_channel.py:46`) joins
  `discord_payload` (`alerting/adapters/discord_message.py:54`) and `result_of`
  (`alerting/adapters/discord_answer.py:41`); it reads `alerting_discord_webhook` at each send
  (`discord_webhook_channel.py:43`, `:51-71`). The transport is **`UrllibWebhookTransport`**
  (`alerting/adapters/urllib_webhook_transport.py:41`); its test double is
  **`FakeWebhookTransport`** (`alerting/contracts/testing/fake_webhook_transport.py:36`), and both pass
  one contract suite (`alerting/contracts/testing/contract_webhook_transport.py`).
- **`discord_channel`** (`alerting/composition/channel_bindings.py:65-88`), the descriptor's factory:
  it answers `None` when no webhook, or no Discord webhook URL, is stored, so an unconfigured
  channel is not in the catalog and starts no lane (`:96-112`). Its secrets come from
  `ChannelSecrets` (`:58-62`), bound to `build_secret_stores()` of `support/secrets`
  (`alerting_bindings.py:105-107`).
- **`ChannelAlertingStatus`** (`alerting/application/channel_alerting_status.py:16`): a channel is
  carried when it is in the catalog and not disabled.
- **`SendTestMessage`** (`alerting/application/send_test_message.py:47`) and **`AlertCliHandler`**
  (`alerting/cli/alert_cli_handler.py:59`): `alert test`, one loud `TEST` alert per channel, straight
  to the channel and never through the outbox (design 036 §9).

The Options page (`EPIC-036D1`) added:

- **`DiscordWebhookSetup`** (`alerting/application/discord_webhook_setup.py:82`), the only write path
  the app has for a channel's secret: `save` strips and validates with `is_discord_webhook_url`
  (injected through `WebhookChannelSpec`, `:44`, so the application layer imports no adapter), writes
  through `ISecretStore` and reads back to catch a store that answers first (`OVERRIDDEN`, `:103-117`);
  `remove` does the same for deletion (`:119-128`); `state` answers `DiscordChannelState` (`:71`):
  stored, usable, the last four characters of the token, and whether this run has the lane
  (`:93-101`). It returns enums and a hint, never the URL.
- **`SendTestToConfiguredChannels`** (`alerting/application/send_test_to_configured_channels.py:26`)
  is `SendTestMessage` over a catalog built again for each test, by **`IChannelCatalogBuilder`**
  (`alerting/contracts/i_channel_catalog_builder.py`) and its adapter
  **`DescriptorChannelCatalogBuilder`** (`alerting/composition/channel_bindings.py:122`), which runs
  `build_channel_catalog` again. The run's own catalog is not touched.
- **The page**, in `alerting/ui/options/`: `AlertsSettingsPresenter`
  (`alerts_settings_presenter.py:93`, an `OptionsSectionPresenter` that is never dirty), its view and
  view model, `AlertsActionRelay` (`alerts_action_relay.py:15`, a `UiThreadRelay`) and the page's
  sentences (`alerts_words.py`). The module contributes it as the `Deferred` `_OPTIONS_PAGE`
  (`alerting/module.py:89`, `:108-115`), order 30 after Trading and Market Data.

Every binding is in `alerting/composition/alerting_bindings.py:98-168` (the page's three at `:136-158`).

## Planned

| Class | Where | Task |
| :--- | :--- | :--- |
| `StreamAlertSource`, `SystemAlertSource` (replaces `NotificationEventHandler`) | `alerting/application/sources/` | `EPIC-036B` |
| `TelegramChannel` (moved), the token migration, the embed layout, pacing, `RotateSecret` | `alerting/adapters/`, `alerting/application/` | `EPIC-036C` |
| The channels table, routing matrix and schedule of the Options page, the Alerts dock, the status-bar indicator, the per-bot menu item; a persisted `IAlertSettingsSource` | `alerting/ui/`, `alerting/adapters/` | `EPIC-036D` |
| `HeartbeatService`, the dead man's switch pinger | `alerting/application/`, `alerting/adapters/` | `EPIC-036E` |
| `IRemoteCommandSource`, `RemoteCommandGate` | `alerting/` | `EPIC-036F` |
