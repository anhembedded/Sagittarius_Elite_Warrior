"""`EPIC-033D` — a desk's commands as the window builds them, for its tests.

The commands come from `desk_commands`, as the module contributes them; the
actions from the Engine's real `ActionRegistry`, through the window's own
`action_descriptor`; the presenter binds them through `bind_commands`, as the
window calls it. Only the confirmation dialog is replaced, by one that records
what it was asked and answers as told.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_commands import (
    desk_commands,
    emergency_stop_id,
    enable_trading_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.futures_desk_screen import (
    FUTURES_DESK_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.spot_desk_screen import (
    SPOT_DESK_ROUTE,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.command_actions import (
    action_descriptor,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    IBindsCommands,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_descriptor import (
    ActionConfirmation,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)

_ROUTE = {
    TradingVenue.FUTURES_TESTNET: FUTURES_DESK_ROUTE,
    TradingVenue.SPOT_TESTNET: SPOT_DESK_ROUTE,
}


@dataclass
class RecordingConfirmer:
    """An `IActionConfirmer` that answers `answer` and keeps every question."""

    answer: bool = True
    asked: list[ActionConfirmation] = field(default_factory=list)

    def confirm(self, parent: QWidget | None, confirmation: ActionConfirmation) -> bool:
        self.asked.append(confirmation)
        return self.answer


@dataclass(frozen=True)
class DeskActions:
    """One desk's two actions and the confirmer they ask."""

    registry: ActionRegistry
    confirmer: RecordingConfirmer
    venue: TradingVenue

    @property
    def enable_trading(self) -> QAction:
        return self.registry.action(enable_trading_id(self.venue))

    @property
    def emergency_stop(self) -> QAction:
        return self.registry.action(emergency_stop_id(self.venue))


def bind_desk_actions(
    owner: QWidget, presenter: IBindsCommands, venue: TradingVenue
) -> DeskActions:
    """`venue`'s commands, contributed and bound to `presenter`."""
    confirmer = RecordingConfirmer()
    registry = ActionRegistry(owner, confirmer)
    for command in desk_commands(_ROUTE[venue], venue):
        registry.contribute(action_descriptor(command))
    presenter.bind_commands(registry)
    return DeskActions(registry, confirmer, venue)
