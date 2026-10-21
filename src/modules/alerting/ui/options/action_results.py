"""What each Alerts-page action's answer is told as (`EPIC-036D7`).

Split from the page's presenter, which was at the file-size ceiling: this is the words half of
`_show_result` (an outcome becomes a sentence on the status line, and a saved secret clears its
field). The presenter keeps the tracker, the relay and the dispatch; this holds no state of its
own beyond the view model it writes to.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channels_setup import (
    ChannelSwitch,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    WebhookRemoval,
    WebhookSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.quiet_hours_setup import (
    QuietHoursSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.routing_setup import (
    RouteSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_message import (
    ChannelTestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_credentials_setup import (
    TelegramRemoval,
    TelegramSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import (
    alerts_words,
    channels_words,
    quiet_hours_words,
    routing_words,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view_model import (
    AlertsSettingsViewModel,
)
from sagittarius_engine.interfaces.i_logger import ILogger

#: `BOT-169` — the causes of the page's commands, one message each.
_CAUSE = "alerting.settings.{kind}"


class ActionResults:
    def __init__(
        self,
        view_model: AlertsSettingsViewModel,
        notifier: INotifier,
        logger: ILogger,
    ) -> None:
        self._view_model = view_model
        self._notifier = notifier
        self._logger = logger

    def failed(self, kind: str, error_type: str) -> None:
        """A command the user just ran did not do what they asked (`BOT-169`): a message box,
        with only the exception's type behind Details…."""
        self._logger.warning(
            f"AlertsSettingsPresenter: {kind} raised {error_type} [alert-setup]"
        )
        self._notifier.report_failure(
            FailureNotice(
                kind=FailureKind.COMMAND,
                cause=_CAUSE.format(kind=kind),
                headline=alerts_words.UNEXPECTED_HEADLINE.format(
                    doing=alerts_words.DOING_WORDS[kind]
                ),
                detail=error_type,
            )
        )

    def mode_kept(self, mode: BotAlertMode) -> None:
        self._view_model.set_status(alerts_words.MODE_SAVED[mode], False)

    def test_sent(self, outcomes: tuple[ChannelTestOutcome, ...]) -> None:
        self._view_model.set_status(*alerts_words.send_test_words(outcomes))

    def telegram_kept(self, outcome: TelegramSave) -> None:
        if outcome in (TelegramSave.SAVED, TelegramSave.OVERRIDDEN):
            self._view_model.telegram.keep_credentials()
        self._view_model.set_status(*alerts_words.TELEGRAM_SAVE_WORDS[outcome])

    def telegram_forgotten(self, outcome: TelegramRemoval) -> None:
        self._view_model.set_status(*alerts_words.TELEGRAM_REMOVAL_WORDS[outcome])

    def webhook_kept(self, outcome: WebhookSave) -> None:
        if outcome in (WebhookSave.SAVED, WebhookSave.OVERRIDDEN):
            self._view_model.keep_webhook()
        self._view_model.set_status(*alerts_words.SAVE_WORDS[outcome])

    def route_kept(self, outcome: RouteSave) -> None:
        self._view_model.set_status(*routing_words.SAVE_WORDS[outcome])

    def channel_switched(self, outcome: ChannelSwitch) -> None:
        self._view_model.set_status(*channels_words.SAVE_WORDS[outcome])

    def quiet_kept(self, outcome: QuietHoursSave) -> None:
        self._view_model.set_status(*quiet_hours_words.SAVE_WORDS[outcome])

    def webhook_forgotten(self, outcome: WebhookRemoval) -> None:
        self._view_model.set_status(*alerts_words.REMOVAL_WORDS[outcome])
