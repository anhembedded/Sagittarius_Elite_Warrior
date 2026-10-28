"""`EPIC-047E` - the VPS Bots tab: the Bots screen with the host line above it, New bot off and the typed question.

Offline, as the Bots screen's own preview is: the sample bots are that preview's, the line is given by a stub, no link and no
container. Two frames: the host answering (`build_preview`), and the link down, where the line says so with the age of the last
facts (`build_disconnected_preview`). The question a real-money Start asks is `build_typed_venue_preview`.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_line import HostLine
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.preview import (
    build_preview as build_bots_preview,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.typed_venue_dialog import (
    TypedVenueDialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.vps_backend import (
    NO_NEW_BOT_HERE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_LIVE = HostLine(
    "nathan-warrior · Futures Mainnet, Spot Testnet key saved · connected · facts updated 2 s ago",
    True,
)
_DOWN = HostLine(
    "nathan-warrior · disconnected, data as of 12:03:41 UTC; reconnecting (attempt 2) · Futures Mainnet key saved",
    False,
)


def _vps_view(line: HostLine) -> QWidget:
    widget = build_bots_preview()
    if not isinstance(widget, BotsView):
        raise TypeError("the Bots screen's preview builds a BotsView")
    widget.show_host_line(lambda: line)
    widget.model.set_new_bot_unavailable(NO_NEW_BOT_HERE)
    return widget


def build_preview() -> QWidget:
    return _vps_view(_LIVE)


def build_disconnected_preview() -> QWidget:
    return _vps_view(_DOWN)


def build_typed_venue_preview() -> QWidget:
    return TypedVenueDialog(TradingVenue.FUTURES_MAINNET, "Start bot grid-btc")
