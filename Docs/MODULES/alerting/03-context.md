Status: Current

# `alerting` — 3. Context

*What does the module depend on, who depends on it, and which commands, queries and events cross its
edge?*

**Built.** `alerting/module.py` → `AlertingModule.dependencies` declares `["bots", "trading"]`: the module
reads `bots/contracts` and one `trading/contracts` event only — `BotChangedEvent`
(`src/modules/bots/contracts/events/bot_changed_event.py` → `BotChangedEvent`), `BotStopGaveUpEvent`
(`src/modules/bots/contracts/events/bot_stop_gave_up_event.py` → `BotStopGaveUpEvent`, published by
`grid_stop_retry.py` → `GridStopRetry._exhausted`), `BotRecoveryStalledEvent`
(`src/modules/bots/contracts/events/bot_recovery_stalled_event.py` → `BotRecoveryStalledEvent`,
published once per wait by `grid_halt_recovery.py` → `GridHaltRecovery._tell_if_stalled`),
`BotAutoRecoveredEvent` (`src/modules/bots/contracts/events/bot_auto_recovered_event.py` →
`BotAutoRecoveredEvent`, published after each automatic recovery by `grid_halt_recovery.py` →
`GridHaltRecovery._after`) and the one-bot read
`GetBotStatusReportQuery(bot_id)` (`src/modules/bots/contracts/bot_status_report.py` →
`GetBotStatusReportQuery`, `BotStatusEntry`) — and, since `BOT-189`, `BotOrderFilledEvent`
(`src/modules/bots/contracts/events/bot_order_filled_event.py` → `BotOrderFilledEvent`, published once
per order that filled whole by `grid_fill_announcer.py` → `GridFillAnnouncer.announce`),
`BotExitClosedEvent` (`src/modules/bots/contracts/events/bot_exit_closed_event.py` → `BotExitClosedEvent`,
published once per exit after its last closing slice is booked, by `grid_exit_report.py` →
`GridExitReport.after_exit_fill`; `BOT-190`),
`BotRangeChangedEvent` (`src/modules/bots/contracts/events/bot_range_changed_event.py` →
`BotRangeChangedEvent`) and `BotProtectiveStopEvent`
(`src/modules/bots/contracts/events/bot_protective_stop_event.py` → `BotProtectiveStopEvent`) and, since `EPIC-026L`,
`AccountLossCapTrippedEvent` (`src/modules/bots/contracts/events/account_loss_cap_tripped_event.py` →
`AccountLossCapTrippedEvent`, published once per trip by `account_loss_cap.py` →
`AccountLossCap._announce`) and, since `EPIC-036B1`, `BotRiskChangedEvent`
(`src/modules/bots/contracts/events/bot_risk_changed_event.py` → `BotRiskChangedEvent`, published once per
change of a Futures bot's liquidation level by `grid_risk_watch.py` → `GridRiskWatch._announce`) and
trading's `UserStreamHealthEvent` (`src/modules/trading/contracts/events/user_stream_health_event.py` →
`UserStreamHealthEvent`, published by `venue_event_emitter.py` → `VenueEventEmitter.user_stream_health`)
— and no context imports its insides, so a new kind of
bot changes nothing here (N1). The shell lists `AlertingModule` with the other modules
(`src/shell/modules.py` → `MODULES`). What crosses its edge:

- in: `IAlertPublisher` (`publish`, `condition_cleared`, `alerting/contracts/i_alert_publisher.py` →
  `IAlertPublisher`), called by the module's own sources (`BotAlertSource`, `BotFillAlertSource`,
  `LiquidationAlertSource`, `StreamAlertSource`) and by every source `EPIC-036B` adds;
- out: one `IAlertChannel.deliver(alert, loudness) -> DeliveryResult` per configured channel
  (`alerting/contracts/i_alert_channel.py` → `IAlertChannel.deliver`); the one channel is Discord,
  over `IWebhookTransport` (`alerting/contracts/i_webhook_transport.py` → `IWebhookTransport`), with
  its webhook read by name through `ISecretStore` (`src/core/contracts/i_secret_store.py` →
  `ISecretStore`);
- asked: `IAlertingStatus.carries_bot_events()` (`alerting/contracts/i_alerting_status.py` →
  `IAlertingStatus`). `operations` binds `AlertingAlertChannels` over it
  (`src/modules/operations/adapters/alerting_alert_channels.py` → `AlertingAlertChannels`;
  `src/modules/operations/module.py` → `OperationsModule.register`), so `run` warns "nothing will
  tell you if a bot halts" (`src/modules/operations/application/host_steps.py` →
  `WarnWhenNoAlertChannel`) only when no channel is configured;
- the `alert` command-line command (`alerting/module.py` → `AlertingModule.declare_cli`) and the
  `alerting` section of the health snapshot (`alerting/module.py` →
  `AlertingModule.declare_operations`).

The boundary guards under `tests/unit/architecture/boundaries/` hold the direction: `bots` and
`trading` never import `alerting`. A module's `composition/` may import `support/secrets`, where the
secret stores live (`tests/unit/architecture/boundaries/rules.py` → `_SECRETS_SUPPORT_ZONES`).

Two pictures: [`diagrams/03-context-in.puml`](diagrams/03-context-in.puml) (*what reaches into the
module, and through which port?*) and [`diagrams/03-context-out.puml`](diagrams/03-context-out.puml)
(*how does an alert leave the module, and where does its secret come from?*).

**Planned.** `EPIC-036F` adds the receive side, `IRemoteCommandSource`, which is not an `IAlertChannel`.
