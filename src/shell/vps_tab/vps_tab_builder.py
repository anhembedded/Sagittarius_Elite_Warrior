"""`EPIC-047E` - builds the VPS Bots tab's presenter: the Bots presenter, over a container that carries the tab's session.

@details The container is the application's with four answers of its own (`VpsContainer`): the tab's private bus, so the
host's events reach this tab and no other; the tab's session (`IVpsTab`), which the Bots screen's backend reads to put the
link behind its doors; and no venue served on this computer, so nothing here can reach an exchange. The session is built
here, once, at the first build and not connected: it connects when the tab is first shown (`IVpsTab.opened`).
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_tab import IVpsTab
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.no_local_venues import NoLocalVenues
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_container import VpsContainer
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_tab_session import VpsTabSession
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profiles import (
    LinkProfiles,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_event_bus import IEventBus

logger = logging.getLogger("App.VpsTab")

_BOTS_PRESENTER: Deferred[BasePresenter] = Deferred(
    "Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_presenter:BotsPresenter"
)


def build_vps_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    session = VpsTabSession(
        container.resolve(LinkProfiles),
        container.resolve(TransportRegistry),
        container.resolve(ICommandDispatcher),
        container.resolve(IBotKindCatalog),
    )
    app = QApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(session.stop)
    overlay = VpsContainer(container)
    overlay.singleton(IEventBus, session.events)
    overlay.singleton(IVpsTab, session)
    overlay.singleton(IVenueTradingPorts, NoLocalVenues())
    logger.info(
        "[vps-tab] presenter built; the link starts when the tab is first shown"
    )
    return _BOTS_PRESENTER(view, overlay)
