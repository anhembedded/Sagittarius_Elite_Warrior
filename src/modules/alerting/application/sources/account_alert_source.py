"""`EPIC-026L` - the account-level loss cap tripping is one alert about the whole app.

Split from `BotAlertSource`: the cap is about the account, not a bot, so this source reads no bot
status report and keeps no bot's state. It reads one `bots/contracts` event.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    label_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.account_loss_cap_tripped_event import (
    AccountLossCapTrippedEvent,
)

logger = logging.getLogger("App.Alerting")


class AccountAlertSource:
    def __init__(self, publisher: IAlertPublisher, clock: IAlertClock) -> None:
        self._publisher = publisher
        self._clock = clock

    def on_account_loss_cap_tripped(self, event: AccountLossCapTrippedEvent) -> None:
        """`EPIC-026L`: the account-level loss cap tripped; the owner must hear it at once.

        About the whole host, not a bot, so its subject is the app. It has no recovery message: the
        owner's acknowledgement is the end of it, and a cap that trips again is a new alert.
        """
        figure = f" (cap {event.figure})" if event.figure else ""
        detail = (
            f"The account-level loss cap tripped{figure}: {event.detail}.\n"
            f"{event.bots_stopped} bot(s) are being stopped. No bot starts or resumes until you "
            "acknowledge it with `main.py bot loss-cap-ack` on the running host. A Spot bot keeps "
            "the coin it holds; a Futures bot's position is closed at market."
        )
        self._publisher.publish(
            Alert.raised(
                AlertKind.ACCOUNT_LOSS_CAP_TRIPPED,
                AlertSubject.app(),
                label_of(AlertKind.ACCOUNT_LOSS_CAP_TRIPPED),
                detail,
                self._clock.now(),
                reason=event.reason,
            )
        )
        logger.info(
            "[alert-source] account loss cap tripped (%s): alert published",
            event.reason,
        )
