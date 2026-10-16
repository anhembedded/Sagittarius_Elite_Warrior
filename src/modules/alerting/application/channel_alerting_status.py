"""`IAlertingStatus` from the channels this run has and the owner's settings (`EPIC-036G`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_settings_source import (
    IAlertSettingsSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alerting_status import (
    IAlertingStatus,
)


class ChannelAlertingStatus(IAlertingStatus):
    """A channel is in the catalog only when it is configured here
    (`composition/channel_bindings.py`), so "configured and enabled" is "in the
    catalog and not disabled". The bot source is subscribed by every writable
    boot (`module.py`), so a channel is all a bot's alert needs."""

    def __init__(
        self, catalog: IAlertChannelCatalog, settings: IAlertSettingsSource
    ) -> None:
        self._catalog = catalog
        self._settings = settings

    def carries_bot_events(self) -> bool:
        disabled = self._settings.current().disabled_channels
        return any(
            channel_id not in disabled for channel_id in self._catalog.channel_ids()
        )
