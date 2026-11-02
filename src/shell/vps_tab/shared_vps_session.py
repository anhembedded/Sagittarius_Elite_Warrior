"""`EPIC-047E` — the one VPS link session, shared by the VPS tab and by Add to VPS.

@details The session (`VpsTabSession`) holds the supervised link to the host. The VPS tab stands on it and so does Add to VPS,
which is a command of the Bots tab: both must reach the same link, or a bot sent from the Bots tab would be sent over a second
connection the VPS tab never shows. The session is built at the first use and not before, because it resolves the connection
profiles and the local dispatcher, which exist only after the composition root is done; building it connects nothing
(`VpsTabSession.start` does, and only when the tab is first shown or a bot is sent).

@par Extension cases
  · a second host - another holder keyed by profile; this one holds the profile in use at the first use.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_tab_session import VpsTabSession
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profiles import (
    LinkProfiles,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from sagittarius_engine.interfaces.i_container import IContainer


class SharedVpsSession:
    def __init__(self, container: IContainer) -> None:
        self._container = container
        self._session: VpsTabSession | None = None

    def session(self) -> VpsTabSession:
        if self._session is None:
            container = self._container
            self._session = VpsTabSession(
                container.resolve(LinkProfiles),
                container.resolve(TransportRegistry),
                container.resolve(ICommandDispatcher),
                container.resolve(IBotKindCatalog),
                container.resolve(INotifier).notify,
            )
        return self._session
