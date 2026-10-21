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
- **The routing matrix** (`EPIC-036D7`): `RoutingSetup` (`alerting/application/routing_setup.py` →
  `RoutingSetup`, `RoutingState`) sets one `(AlertGroup, channel)` cell through `IAlertRouting`
  (`alerting/contracts/i_alert_routing.py` → `IAlertRouting`), served by `JsonAlertSettings`; a cell
  not set is its default and `None` puts it back. Only a channel the catalog has can be set. The hub
  reads the cells as `AlertSettings.routes` (`loudness_for`), and `AlertRouter.route` keeps the N8
  cover for a Critical whatever the matrix says: two channels when two are set up, and one loud
  delivery among them. The file's shape and how it is read are
  `alerting/adapters/settings_document.py` → `SettingsDocument`, `read_document`. The page group is
  `RoutingMatrixGroup` (`alerting/ui/options/routing_matrix_group.py` → `RoutingMatrixGroup`) over
  `RoutingMatrixViewModel`; what each outcome is told as is `action_results.py` → `ActionResults`,
  split from the presenter at the file-size ceiling.
- **The channel switches** (`EPIC-036D8`): `ChannelsSetup` (`alerting/application/channels_setup.py` →
  `ChannelsSetup`, `ChannelsState`, `ChannelSwitch`) turns a channel on or off through
  `IChannelEnabling` (`alerting/contracts/i_channel_enabling.py` → `IChannelEnabling`), served by
  `JsonAlertSettings` (`disable`, `enable`, `disabled`); only a channel the catalog has can be
  switched. The hub and the router read the result as `AlertSettings.disabled_channels`: a disabled
  channel keeps its secret and its lane, gets no delivery even for a Critical, and
  `ChannelAlertingStatus` counts it as not carrying alerts. The status bar and the Alerts mode see it as `ChannelHealth.enabled`
  (`alerting/contracts/alert_history_report.py` → `ChannelHealth`). The switch belongs to the channel
  id: removing a secret does not clear it. The file key is `disabled_channels`
  (`alerting/adapters/settings_document.py` → `SettingsDocument`). The page group is `ChannelsGroup`
  (`alerting/ui/options/channels_group.py` → `ChannelsGroup`) over `ChannelsViewModel`; the kinds of
  action the page runs are `alerts_action_kind.py` → `AlertsActionKind`, split from the presenter at
  the file-size ceiling.
- **The heartbeat interval** (`EPIC-036D9`): `HeartbeatSetup` (`alerting/application/heartbeat_setup.py` →
  `HeartbeatSetup`, `HeartbeatState`, `HeartbeatSave`) chooses among `HEARTBEAT_HOURS_CHOICES`
  (`alerting/domain/alert_policies.py` → `HEARTBEAT_HOURS_CHOICES`) through `IHeartbeatSetting`
  (`alerting/contracts/i_heartbeat_setting.py` → `IHeartbeatSetting`), served by `JsonAlertSettings`;
  choosing the default keeps no value. `HeartbeatService` reads `AlertSettings.heartbeat_every` on every
  pass, else `HeartbeatPolicy.heartbeat_every` (N4). The page group is `HeartbeatGroup`
  (`alerting/ui/options/heartbeat_group.py` → `HeartbeatGroup`) over `HeartbeatViewModel`; showing the
  kept state of a group after an action is `setting_panels.py` → `SettingPanels`.
- **Quiet hours** (`EPIC-036D6`): `QuietHoursSetup` (`alerting/application/quiet_hours_setup.py` →
  `QuietHoursSetup`) keeps a period through `IQuietHoursSetting`
  (`alerting/contracts/i_quiet_hours_setting.py` → `IQuietHoursSetting`, `QuietHoursChoice`), served by
  `JsonAlertSettings`; the hub reads it as `AlertSettings.quiet_hours` and `QuietHoursHold` does the
  holding. The Options page group is `QuietHoursGroup` (`alerting/ui/options/quiet_hours_group.py` →
  `QuietHoursGroup`) over `QuietHoursViewModel`; the zone is the display zone's own name (`UTC`, an IANA key, or `SYSTEM` for
  the machine's clock, read with `zone=None` in `quiet_hours.py` → `QuietHours.contains`), from
  `display_zone_key.py` → `display_zone_key_of`. The Bots list of the page is `BotModeList`
  (`bot_mode_list.py` → `BotModeList`), split from the presenter at the file-size ceiling.
- **`JsonAlertSettings`** (`alerting/adapters/json_alert_settings.py` → `JsonAlertSettings`) serves
  `IAlertSettingsSource` for the hub and `IBotAlertModes` (`alerting/contracts/i_bot_alert_modes.py` →
  `IBotAlertModes`) for the Options page, over one file ([`08-concepts.md`](08-concepts.md));
  `InMemoryAlertSettings` (`alerting/adapters/memory_alert_settings.py` → `InMemoryAlertSettings`)
  holds N4's defaults for tests; `NullAlertPublisher`
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
  `Alert.condition_key` gives (`alerting/domain/alert.py` → `Alert.condition_key`);
  `on_account_loss_cap_tripped` (`EPIC-026L`) raises one CRITICAL `ACCOUNT_LOSS_CAP_TRIPPED` about the
  whole app (`AlertSubject.app`, `BOT_EVENTS` group) with the figure, the loss, the count of bots being
  stopped and how to acknowledge; it has no recovery message, because the owner's acknowledgement ends it
  and a second trip is a new alert.
- **The reason table** (`alerting/application/sources/bot_reason_routes.py` → `REASON_ROUTES`, `ReasonRoute`,
  `own_route_on_entry`, `stalled_route`; `EPIC-036B2`): one row for every reason code of the bots' grid
  (`GridReason.value`), saying whether it reaches the owner as its own kind on entry (`KEY_REJECTED` on `HALTED` or
  `ERROR`, `STORAGE_FAILURE` on `PAUSED`), as its own kind when the wait stalls (`PRICE_FEED_STALE` and
  `RATE_LIMITED`, in place of `BOT_RECOVERY_STALLED`; a rate limit that is a plain `HALTED` is the
  generic halt, because a person must resume it), through the stop path
  (`EXIT_ON_STOP`, the protective-stop event), as the state's generic kind, or never. `BotAlertSource`
  asks it before `ALERT_ON_ENTRY` (`bot_alert_source.py` → `BotAlertSource._alert_on_entry`,
  `BotAlertSource.on_recovery_stalled`); a reason it does not list is the generic halt, so a new bot kind
  changes nothing here. The own kinds say a fixed sentence and the reason code and copy no detail of
  the bot, which holds the failure text of a request or the disk; a return to `RUNNING` ends each
  (`bot_alert_source.py` → `CLEARED_ON_ENTRY`).
- **`LiquidationAlertSource`** (`alerting/application/sources/liquidation_alert_source.py` →
  `LiquidationAlertSource`; `EPIC-036B1`), the early warning of a Futures bot: `on_risk_changed` raises
  one `LIQUIDATION_RISK` WARNING when the guard's level becomes `WARN`, with the mark price, the
  exchange's liquidation price and the distance, and ends it on `SAFE`; `on_bot_changed` ends it when
  the bot reaches `STOPPED` or is removed (with "Recovered"), and forgets it quietly in any state the
  guard does not judge, where the guard resets to `SAFE` without an event. `CRITICAL` and `UNKNOWN` raise nothing here: the bot halts
  and the halt is the alert. The distances are the bot's (`FuturesGridThresholds`); this source holds
  none.
- **`StreamAlertSource`** (`alerting/application/sources/stream_alert_source.py` →
  `StreamAlertSource`; `EPIC-036B1`), the user-data stream: `on_user_stream_health` raises one
  `USER_STREAM_DOWN` for the venue (`AlertSubject.venue_wide`) when a `CONNECTING` or `RECONNECTING`
  event says the outage is older than the grace, and ends it on `CONNECTED`; `STOPPED` is not an
  outage. One alert for the venue, not one per bot halted by the same cause.
- **`WarningLatch`** (`alerting/application/warning_latch.py` → `WarningLatch`) and
  **`EarlyWarningPolicy`** (`alerting/domain/alert_policies.py` → `EarlyWarningPolicy`): one open
  warning per key and a cool-down between two raises, so a condition that flips between raised and
  cleared (the hub forgets its dedup window on a clear) sends one pair per cool-down and not one per
  flap. Both early sources hold one; the liquidation source's defers a clear that comes inside the
  cool-down (`defer_clear`), so no "Recovered" is sent that a re-cross would make false.
- **`BotFillAlertSource`** (`alerting/application/sources/bot_fill_alert_source.py` →
  `BotFillAlertSource`; BOT-189), the second source at the edge: `on_order_filled` words one INFO
  `ORDER_FILLED` alert per `BotOrderFilledEvent` (`bot_fill_alert_source.py` → `fill_line`: symbol,
  side, quantity, price, level, and on the fill that closes a cycle the cycle's net profit, the run's
  **grid profit** (completed cycles only, never the Total PnL; `BotOrderFilledEvent.grid_profit`) and the
  number of cycles). Its dedup key is the order with the bot (`Alert.raised`'s `reason`),
  so a repeat of one fill is one message and two fills are two. The exits live in `BotAlertSource`: the
  entry into `STOPPING` with the reason `stop_loss`, `take_profit` or `range_exit` is one alert at once
  (`bot_exit_words.py` → `EXIT_ON_STOP`; `bot_alert_source.py` → `BotAlertSource._alert_on_exit`); `on_range_changed` tells a
  price outside the range of a bot that only holds (a bot that closes there is told by its stop) and
  is not told on the return (a price that flaps at the edge is bounded by the hub's 15 minute window, one message per side); `on_protective_stop` tells the exchange-side stop having run.
- **`BotExitAlertSource`** (`alerting/application/sources/bot_exit_alert_source.py` →
  `BotExitAlertSource`; BOT-190), the third source at the edge: `on_exit_closed` turns one
  `BotExitClosedEvent` into one INFO `EXIT_CLOSED` alert with the run's result, worded by
  `bot_exit_words.py` → `closed_detail` (the exit's name, the run's result, the profit of its completed
  cycles and their number; a result the bot cannot judge reads `no price yet`, never zero). It tells
  only the reasons in `EXIT_ON_STOP` (`stop_loss`, `take_profit`, `range_exit`), so a stop the owner
  asked for sends none. Its dedup key is the run (`BotExitClosedEvent.run_id` as `Alert.raised`'s
  `reason`): each run's result is its own message.
- **`FillBacklog`** (`alerting/application/fill_backlog.py` → `FillBacklog`; BOT-189) bounds the fill
  messages waiting on one channel: after each is stored, `FillBacklog.trim` asks the outbox to drop the
  oldest past `DeliveryPolicy.fill_backlog` (`IOutbox.shed_surplus`, kept as `DROPPED`), and the
  housekeeping tick turns what was dropped into one INFO line, "N fill messages skipped"
  (`FillBacklog.take_summary`, sent by `AlertHub.flush_due`). The worker's order, CRITICAL first
  (`IOutbox.due`), is what keeps a CRITICAL from waiting behind fills.
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
- **The Telegram part of the page** (`EPIC-036D4`): `TelegramCredentialsSetup`
  (`alerting/application/telegram_credentials_setup.py` → `TelegramCredentialsSetup.save`,
  `TelegramCredentialsSetup.remove`, `TelegramCredentialsSetup.state`), the sibling of
  `DiscordWebhookSetup` for two values: both are checked against the shapes Telegram issues
  (injected through `TelegramChannelSpec`), written, and read back (`OVERRIDDEN`); the state
  carries four characters of the token and the chat id, never the token. Saving over a stored pair
  is the rotation. The page's `TelegramSettingsGroup` (`telegram_settings_group.py`) has its own
  `TelegramSettingsViewModel`; `ChannelStates` (`channel_states.py`) carries both channels' state
  from the pool. Send test stays one button for every channel set up.

- **The dead man's switch** (`EPIC-036E1`): `DeadMansSwitch` (`alerting/application/dead_mans_switch.py`
  → `DeadMansSwitch`, `DeadMansSwitch.tick`) is not an `IAlertChannel`, because it carries liveness and
  no alert. It reads the check-in URL by name from the channels' `ISecretStore`
  (`DEAD_MANS_SWITCH_SECRET`), posts through `IWebhookTransport`, asks `IWorkerLiveness`
  (`alerting/contracts/i_worker_liveness.py`) whether the worker makes progress, and reports a monitor
  that stays down through `IDeliveryFollowUp.channel_failing`. `WorkerLiveness`
  (`alerting/adapters/worker_liveness.py` → `WorkerLiveness`, `STALL_AFTER`) is the one stamp per
  worker thread that `ThreadedDeliveryHost` touches after each pass.

- **The app's own failures** (`EPIC-036B`): `SystemAlertSource`
  (`alerting/application/sources/system_alert_source.py` → `SystemAlertSource`,
  `SystemAlertSource.report_failure`) implements `ISystemFailureReporter`
  (`alerting/contracts/i_system_failure_reporter.py`). It does not subscribe: a task failure, a
  failed sync and a UI slot's error are no module's contract event, and their text is
  normalised once in the shell (`shell/system_error_report.py`), so the shell's `SystemFailureRelay`
  (`shell/system_failure_relay.py` → `SystemFailureRelay`) hears them and calls the port. One
  `APP_FAILURE` alert, CRITICAL, subject `app`, deduped by the failing source's name so a loop is
  one record with a counter. The in-app toast is a second consumer of the relay, not an
  `IAlertChannel`: a notice inside the app, with no use for an outbox that holds 24 h.
- **The heartbeat and the daily summary** (`EPIC-036E`): `HeartbeatService`
  (`alerting/application/heartbeat_service.py` → `HeartbeatService`, `HeartbeatService.tick`) runs on the
  housekeeping thread, before the hub's flush (`alerting_bindings.py` → `_housekeeping_of`). It asks
  the bots' status report (`GetBotStatusReportQuery`, `EPIC-038C`) through `ICommandDispatcher`, the
  model the Bots tab and `status` read, and publishes a `HEARTBEAT` every
  `HeartbeatPolicy.heartbeat_every` and a `DAILY_SUMMARY` once a day after `HeartbeatPolicy.summary_at`
  (`alerting/domain/alert_policies.py` → `HeartbeatPolicy`). The texts are pure functions
  (`alerting/application/heartbeat_text.py` → `heartbeat_text`, `summary_text`); the report's `health`
  slot is printed verbatim and is empty until `EPIC-035W`. What was last sent is read back from the
  outbox (`IOutbox.latest_alert_at`, `has_alert_keyed`, `alert_counts_since`, exact and not bounded
  by a history window), so a restart repeats neither. The counts, the unreadable files and the
  alert counts are written before the per-bot lines, which are added while they fit
  `MAX_DETAIL`; the summary is the one INFO alert quiet hours do not hold
  (`quiet_hours_hold.py` → `QuietHoursHold.holds`).

- **Telegram** (`EPIC-036C1`): `TelegramChannel` (`alerting/adapters/telegram_channel.py` →
  `TelegramChannel`, `TelegramChannel.deliver`) reads the bot token and chat id by name from the
  channels' `ISecretStore` (`TELEGRAM_TOKEN_SECRET`, `TELEGRAM_CHAT_SECRET`) at each send and posts
  `sendMessage` through `IWebhookTransport` (the token is in the URL path, so both values are checked
  against the shapes Telegram issues before use). The body is HTML-escaped text with one bold head
  (`telegram_message.py` → `telegram_payload`; HTML and not MarkdownV2 because one missed escape makes
  Telegram refuse the whole message); a silent cell sets `disable_notification`. Its answers map to
  `DeliveryResult` in `telegram_answer.py` → `result_of`: a 429 waits the `parameters.retry_after`
  Telegram names, "chat not found", a blocked bot and a rejected token are permanent refusals whose
  reason says what to do. A platform's wait, Discord's and Telegram's alike, is capped at the alert's
  24 h life (`adapters/retry_wait.py` → `wait_of`, `MAX_RETRY_AFTER`), so a huge number cannot raise out of a
  channel; the text is measured in UTF-16 units against Telegram's 4096. `TelegramConfigMigration`
  (`alerting/application/telegram_config_migration.py` → `TelegramConfigMigration.run`) runs at
  `AlertingModule.boot` before the channels are built: it writes each of the old config keys to the
  store and clears the key only after the store reads the value back equal. The words shared with
  Discord are in `adapters/alert_text.py`.
- **Pacing** (`EPIC-036C2`): `PacedChannel` (`alerting/adapters/paced_channel.py` → `PacedChannel`,
  `SendWindow`) wraps a channel and keeps a window of its last sends (`PacingPolicy`, `DISCORD_PACING`,
  `TELEGRAM_PACING` in `alerting/domain/alert_policies.py`). A send over the limit is not made: the
  wrapper answers `DeliveryResult.retry_later(wait)`, the answer a 429 gets, so `ChannelDelivery` pauses the
  channel for that long and uses no attempt; a burst is spread and nothing is lost, CRITICAL first. The
  lane sleeps `min(poll, ChannelDelivery.pause_remaining)` (`threaded_delivery_host.py` →
  `ThreadedDeliveryHost._sleep_of`), so a wait of a fraction of a second is not stretched to the 5 s poll.
  `composition/channel_bindings.py` wraps the Discord channel. Telegram's descriptor wraps its channel the same way (`TELEGRAM_PACING`).

Every binding is in `alerting/composition/alerting_bindings.py` → `bind_alerting`, the page's three
and the switch's among them.

The Alerts screen (`EPIC-036D2`) added:

- **The read model**: `IAlertHistory` (`alerting/contracts/i_alert_history.py` → `IAlertHistory.read`)
  answers `AlertHistoryReport` (`alert_history_report.py` → `AlertHistoryRow`, `ChannelOutcome`,
  `ChannelHealth`); `OutboxAlertHistory` (`alerting/application/outbox_alert_history.py` →
  `OutboxAlertHistory.read`) builds it from `IOutbox.history` and `IAlertChannelCatalog`. Each channel's health comes from `IOutbox.latest_real_delivery`, so it does not depend on the window of alerts read. A
  channel is failing when its newest delivery in the window is retrying, failed or expired; a
  pending or dropped one says nothing about whether it works.
- **The screen**, in `alerting/ui/history/`: `AlertsView` over `AlertHistoryTableModel` (one row
  per alert; the severity filter narrows the rows already read), `AlertsPresenter`
  (`alerts_presenter.py` → `AlertsPresenter`), the words in `history_words.py`, a `preview.py`.
  The surface `alerts` is declared by the shell (`shell/surfaces.py` → `ALERTS_SURFACE_ID`) and
  by the view (`alerts_view.py` → `ALERTS_SURFACE`), a test holding the two equal; the mode is
  contributed by `AlertingModule.contribute` (`alerts_screen.py` → `alerts_screen`).
- **Retry failed** (`EPIC-036D5`): `RetryFailedDeliveries`
  (`alerting/application/retry_failed_deliveries.py` → `RetryFailedDeliveries.run`) asks
  `IDeliveryRequeue` (`alerting/contracts/i_delivery_requeue.py` → `IDeliveryRequeue`, a port of its
  own so the already wide `IOutbox` stays the hub's and the lanes') to put every `FAILED` delivery of
  an alert inside `DeliveryPolicy.expiry` back to `PENDING`, attempts counted afresh;
  `SqliteDeliveryRequeue` (`alerting/adapters/sqlite_delivery_requeue.py` → `SqliteDeliveryRequeue`) does
  it on a connection opened for the one call. The screen's button runs it on the pool
  (`alerts_presenter.py` → `AlertsPresenter.retry_failed`). The severity cell's tone is
  `history_table_model.py` → `AlertHistoryTableModel._tone`.
- **The status-bar indicator** (`EPIC-036D3`): `AlertsView.status_widgets` offers one
  `QToolButton` (`IStatusSource`), which the window places in its status bar once, for every
  mode. `history_words.indicator_text` says `Alerts: ok`, `Alerts: no channel` or
  `Alerts: <channel> failing`; a failing channel also shows a warning icon, so colour never
  carries it. It is hidden until the first read; `AlertsView.indicator_clicked` → the presenter
  shows the mode.

## Planned

| Class | Where | Task |
| :--- | :--- | :--- |
| The Discord embed layout, pacing under the platform limit, `RotateSecret`, the Telegram fields of the Options page (built, `EPIC-036D4`) | `alerting/adapters/`, `alerting/application/`, `alerting/ui/` | `EPIC-036C` |
| A channels table with Add, Edit and Rotate once a third channel type exists (the disabled channels, `EPIC-036D8`, the per-bot modes, `BOT-191`, the quiet hours, `EPIC-036D6`, and the routes, `EPIC-036D7`, are persisted). The per-bot menu item in the bots list is decided against: the Options page covers it (the coordinator for the owner, 2026-10-21) | `alerting/ui/`, `alerting/adapters/` | `EPIC-036D` |
| `IRemoteCommandSource`, `RemoteCommandGate` | `alerting/` | `EPIC-036F` |
