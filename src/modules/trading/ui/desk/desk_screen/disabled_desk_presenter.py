"""The desk of a venue this run does not serve (`EPIC-028K`, `EPIC-033D`).

Its view says the venue is not enabled and holds nothing that could send an
order. Its commands are still contributed, because which venues are enabled is
read at boot, after the modules contribute. So this presenter binds them
disabled for the whole run: they show, greyed, in the Trade menu and on the
desk's toolbar. That says the same thing as the notice, and the end-of-build
report does not list them as commands nothing performs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_commands import (
    emergency_stop_id,
    enable_trading_id,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget
    from sagittarius_engine.interfaces.i_container import IContainer


class DisabledDeskPresenter(BasePresenter):
    """Drives nothing; keeps its desk's commands disabled."""

    def __init__(
        self, view: QWidget, container: IContainer, venue: TradingVenue
    ) -> None:
        super().__init__(view, container)
        self._venue = venue

    def bind_commands(self, binder: ICommandBinder) -> None:
        for command_id in (
            enable_trading_id(self._venue),
            emergency_stop_id(self._venue),
        ):
            binder.bind(command_id, self._unreachable, initially_enabled=False)

    def _unreachable(self, _checked: bool) -> None:
        """A disabled action never triggers; if this runs, a bind changed."""
        self.logger.error(
            f"A command of the {self._venue.value} desk ran while the venue is "
            "not enabled; nothing was done."
        )
