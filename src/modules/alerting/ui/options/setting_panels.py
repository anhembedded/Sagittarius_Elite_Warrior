"""The setting groups of the Alerts page that are shown from memory (`EPIC-036D9`).

Routing, channel switches, the heartbeat interval and the quiet hours are each kept in the
settings file and read back from memory, so showing one is a `take_state` of its view model from
its use case's `state()`. After an action the page shows what was kept, not what was picked, after
a success and after a failure alike (a combo or a box that kept saying the choice that was never
saved would lie). Split from the page's presenter, which was at the file-size ceiling.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.alerting.application.channels_setup import (
    ChannelsSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_setup import (
    HeartbeatSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.quiet_hours_setup import (
    QuietHoursSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.routing_setup import (
    RoutingSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_action_kind import (
    AlertsActionKind,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view_model import (
    AlertsSettingsViewModel,
)


class SettingPanels:
    def __init__(
        self,
        view_model: AlertsSettingsViewModel,
        routing: RoutingSetup,
        channels: ChannelsSetup,
        heartbeat: HeartbeatSetup,
        quiet: QuietHoursSetup,
    ) -> None:
        self._shows: dict[AlertsActionKind, Callable[[], None]] = {
            AlertsActionKind.ROUTE: lambda: view_model.routing.take_state(
                routing.state()
            ),
            AlertsActionKind.CHANNEL: lambda: view_model.channels.take_state(
                channels.state()
            ),
            AlertsActionKind.HEARTBEAT: lambda: view_model.heartbeat.take_state(
                heartbeat.state()
            ),
            AlertsActionKind.QUIET: lambda: view_model.quiet.take_state(quiet.state()),
        }

    def show_all(self) -> None:
        for show in self._shows.values():
            show()

    def show_kept(self, kind: AlertsActionKind) -> None:
        """The group `kind` edits, as it is kept now; nothing for a kind that edits none."""
        if (show := self._shows.get(kind)) is not None:
            show()
