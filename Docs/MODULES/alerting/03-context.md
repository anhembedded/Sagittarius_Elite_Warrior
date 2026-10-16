Status: Current

# `alerting` — 3. Context

*What does the module depend on, who depends on it, and which commands, queries and events cross its
edge?*

**Built.** `alerting/module.py:83` declares `dependencies = ["bots"]`: the module reads
`bots/contracts` only — `BotChangedEvent` (`src/modules/bots/contracts/events/bot_changed_event.py:11-29`),
`BotStopGaveUpEvent` (`src/modules/bots/contracts/events/bot_stop_gave_up_event.py:17`, published by
`grid_stop_retry.py:117-132`) and the one-bot read `GetBotStatusReportQuery(bot_id)`
(`src/modules/bots/contracts/bot_status_report.py:51-69`) — and no context imports its insides, so a
new kind of bot changes nothing here (N1). The shell lists `AlertingModule` with the other modules
(`src/shell/modules.py:41,55`). What crosses its edge:

- in: `IAlertPublisher` (`publish`, `condition_cleared`, `alerting/contracts/i_alert_publisher.py:11-24`),
  called by the module's own bot source today and by every source `EPIC-036B` adds;
- out: one `IAlertChannel.deliver(alert, loudness) -> DeliveryResult` per configured channel
  (`alerting/contracts/i_alert_channel.py:34-42`); the one channel is Discord, over
  `IWebhookTransport` (`alerting/contracts/i_webhook_transport.py:59`), with its webhook read by name
  through `ISecretStore` (`src/core/contracts/i_secret_store.py:24-38`);
- asked: `IAlertingStatus.carries_bot_events()` (`alerting/contracts/i_alerting_status.py:14`).
  `operations` binds `AlertingAlertChannels` over it (`src/modules/operations/adapters/alerting_alert_channels.py:19`,
  `src/modules/operations/module.py:150,163`), so `run` warns "nothing will tell you if a bot halts"
  (`src/modules/operations/application/host_steps.py:64-77`) only when no channel is configured;
- the `alert` command-line command (`alerting/module.py:90-96`) and the `alerting` section of the
  health snapshot (`alerting/module.py:98-109`).

The boundary guards under `tests/unit/architecture/boundaries/` hold the direction: `bots` and
`trading` never import `alerting`. A module's `composition/` may import `support/secrets`, where the
secret stores live (`tests/unit/architecture/boundaries/rules.py`, `_SECRETS_SUPPORT_ZONES`).

Two pictures: [`diagrams/03-context-in.puml`](diagrams/03-context-in.puml) (*what reaches into the
module, and through which port?*) and [`diagrams/03-context-out.puml`](diagrams/03-context-out.puml)
(*how does an alert leave the module, and where does its secret come from?*).

**Planned.** `EPIC-036B` adds `trading/contracts` (`UserStreamHealthEvent`) and the system
failures; `EPIC-036F` adds the receive side, `IRemoteCommandSource`, which is not an `IAlertChannel`.
