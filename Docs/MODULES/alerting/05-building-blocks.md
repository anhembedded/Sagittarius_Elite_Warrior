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

- **Pacing** (`EPIC-036C2`): `PacedChannel` (`alerting/adapters/paced_channel.py` → `PacedChannel`,
  `SendWindow`) wraps a channel and keeps a window of its last sends (`PacingPolicy`, `DISCORD_PACING`,
  `TELEGRAM_PACING` in `alerting/domain/alert_policies.py`). A send over the limit is not made: the
  wrapper answers `DeliveryResult.retry_later(wait)`, the answer a 429 gets, so `ChannelDelivery` pauses the
  channel for that long and uses no attempt; a burst is spread and nothing is lost, CRITICAL first. The
  lane sleeps `min(poll, ChannelDelivery.pause_remaining)` (`threaded_delivery_host.py` →
  `ThreadedDeliveryHost._sleep_of`), so a wait of a fraction of a second is not stretched to the 5 s poll.
  `composition/channel_bindings.py` wraps the Discord channel; Telegram's descriptor wraps the same way.

Every binding is in `alerting/composition/alerting_bindings.py` → `bind_alerting`, the page's three
and the switch's among them.

## Planned

| Class | Where | Task |
| :--- | :--- | :--- |
| `TelegramChannel` (moved), the token migration, the embed layout, pacing, `RotateSecret` | `alerting/adapters/`, `alerting/application/` | `EPIC-036C` |
| The channels table, routing matrix and schedule of the Options page, the Alerts dock, the status-bar indicator, the per-bot menu item; the persisted routes, disabled channels and quiet hours of `IAlertSettingsSource` (only the per-bot modes are persisted, `BOT-191`) | `alerting/ui/`, `alerting/adapters/` | `EPIC-036D` |
| `HeartbeatService` and the daily summary (the heartbeat reads `EPIC-035W`'s snapshot) | `alerting/application/` | `EPIC-036E` |
| `IRemoteCommandSource`, `RemoteCommandGate` | `alerting/` | `EPIC-036F` |
