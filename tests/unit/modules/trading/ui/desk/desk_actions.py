"""`EPIC-033D` — a desk's commands as the window builds them, for its tests (`tests/command_actions.py`)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_commands import (
    desk_commands,
    emergency_stop_id,
    enable_trading_id,
    new_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.futures_desk_screen import (
    FUTURES_DESK_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.spot_desk_screen import (
    SPOT_DESK_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_presenter import (
    CommandPresenter,
)
from Sagittarius_Elite_Warrior.tests.command_actions import (
    RecordingConfirmer,
    bound_actions,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)

_ROUTE = {
    TradingVenue.FUTURES_TESTNET: FUTURES_DESK_ROUTE,
    TradingVenue.SPOT_TESTNET: SPOT_DESK_ROUTE,
}


@dataclass(frozen=True)
class DeskActions:
    """One desk's actions and the confirmer they ask."""

    registry: ActionRegistry
    confirmer: RecordingConfirmer
    venue: TradingVenue

    @property
    def enable_trading(self) -> QAction:
        return self.registry.action(enable_trading_id(self.venue))

    @property
    def emergency_stop(self) -> QAction:
        return self.registry.action(emergency_stop_id(self.venue))

    @property
    def new_order(self) -> QAction:
        return self.registry.action(new_order_id(self.venue))


def bind_desk_actions(
    owner: QWidget, presenter: CommandPresenter, venue: TradingVenue
) -> DeskActions:
    """`venue`'s commands, contributed and bound to `presenter`."""
    confirmer = RecordingConfirmer()
    registry = bound_actions(
        owner, desk_commands(_ROUTE[venue], venue), presenter.bind_commands, confirmer
    )
    return DeskActions(registry, confirmer, venue)
