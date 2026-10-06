"""`EPIC-033D`, `EPIC-033I` — the Trade mode's commands as the window builds
them, bound to one desk as the mode binds them to the venue chosen, for the
desks' tests (`tests/command_actions.py`)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_presenter import (
    DeskPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_command_binding import (
    TradeCommandBinding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_commands import (
    EMERGENCY_STOP,
    ENABLE_TRADING,
    NEW_ORDER,
    trade_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.venue_choice import (
    VenueChoice,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.tests.command_actions import (
    RecordingConfirmer,
    bound_actions,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)


@dataclass(frozen=True)
class DeskActions:
    """One desk's actions and the confirmer they ask."""

    registry: ActionRegistry
    confirmer: RecordingConfirmer
    venue: TradingVenue

    @property
    def enable_trading(self) -> QAction:
        return self.registry.action(ENABLE_TRADING)

    @property
    def emergency_stop(self) -> QAction:
        return self.registry.action(EMERGENCY_STOP)

    @property
    def new_order(self) -> QAction:
        return self.registry.action(NEW_ORDER)


def bind_desk_actions(owner: QWidget, presenter: DeskPresenter) -> DeskActions:
    """The Trade mode's commands for `presenter`'s venue alone, bound as the
    mode binds them."""
    venue = presenter.venue
    confirmer = RecordingConfirmer()
    binding_owner = QObject(owner)
    choice = VenueChoice((venue,), None, binding_owner)
    binding = TradeCommandBinding(
        {venue: presenter}, choice, lambda _title: True, binding_owner
    )

    def bind(binder: ICommandBinder) -> None:
        choice.bind_commands(binder)
        binding.bind_commands(binder)

    registry = bound_actions(
        owner, trade_commands(TRADE_ROUTE, (venue,)), bind, confirmer
    )
    return DeskActions(registry, confirmer, venue)
