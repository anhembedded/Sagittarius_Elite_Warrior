"""The Trade mode's presenter (`EPIC-033I`; SPEC-004, 005, 012, 013).

@par What it does
- builds one desk per venue enabled in this run, each on its own page of
  the view (`DeskPresenter`, unchanged in what it does for its venue: the
  chart, the order entry, the account, the session and the strategy);
- shows the page of the venue chosen in Trade → Venue, remembered between
  runs (`VenueChoice`);
- binds the mode's commands to the chosen venue's desk, and Emergency stop
  to every venue's (`TradeCommandBinding`).

Nothing passes between the desks: each one's ports, feeds, chart stream and
strategy are its own venue's (`EPIC-028L`), so choosing a venue only changes
which page shows and which desk the commands reach.

@par What it replaces
The Futures and the Spot desks' screens (`trading.futures`, `trading.spot`),
two modes for one job (HLD §11.2.1).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_presenter import (
    DeskPresenter,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_presenter import (
    CommandPresenter,
    ICommandBinder,
)
from sagittarius_engine.interfaces.i_container import IContainer

from .trade_command_binding import TradeCommandBinding
from .trade_dependencies import TradeDependencies, trade_dependencies_for
from .trade_view import TradeView
from .venue_choice import VenueChoice

logger = logging.getLogger("App.Trading.Trade")


class TradePresenter(CommandPresenter):
    """@brief One desk per enabled venue, the chosen one shown."""

    def __init__(
        self, view: TradeView, container: IContainer, dependencies: TradeDependencies
    ) -> None:
        super().__init__(view, container)
        self.view: TradeView = view
        self.choice = VenueChoice(dependencies.venues, dependencies.state, self)
        self.desks: dict[TradingVenue, DeskPresenter] = {}
        for venue in dependencies.venues:
            profile = desk_profile_for(venue)
            page = view.add_venue(profile, dependencies.confirmations)
            self.desks[venue] = DeskPresenter(
                page, container, profile, dependencies.desk(venue)
            )
        self.commands = TradeCommandBinding(self.desks, self.choice, self)
        self.choice.changed.connect(self._show)
        if self.choice.current is not None:
            view.show_venue(self.choice.current)
        logger.info(
            "[trade] venues %s; showing %s",
            [venue.value for venue in dependencies.venues] or "none",
            self.choice.current.value if self.choice.current else "none",
        )

    def bind_commands(self, binder: ICommandBinder) -> None:
        self.choice.bind_commands(binder)
        self.commands.bind_commands(binder)

    def shutdown(self) -> None:
        for desk in self.desks.values():
            desk.dispose()
        super().shutdown()

    def _show(self, venue: TradingVenue) -> None:
        self.view.show_venue(venue)


def build_trade_presenter(view: TradeView, container: IContainer) -> TradePresenter:
    """The screen's presenter factory: the app's own dependencies."""
    return TradePresenter(view, container, trade_dependencies_for(container))
