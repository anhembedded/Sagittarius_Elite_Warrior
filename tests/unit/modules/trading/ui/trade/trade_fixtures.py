"""`EPIC-033I` — the whole Trade mode over verified fakes, for its tests.

The real `TradeView`, the real `TradePresenter` and, under it, one real
`DeskPresenter` per venue over the desks' own fakes (`desk_screen_fixtures`);
the mode's commands are the window's actions, bound as `MainWindow` binds
them (`tests/command_actions.py`), with the confirmation recorded.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_commands import (
    EMERGENCY_STOP,
    NEW_ORDER,
    trade_commands,
    venue_choice_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_dependencies import (
    TradeDependencies,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_presenter import (
    TradePresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_view import (
    TradeView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.command_actions import (
    RecordingConfirmer,
    bound_actions,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)

from ..desk.desk_screen_fixtures import (
    YES_TO_EVERY_TABLE_QUESTION,
    DeskFakes,
    DeskSetup,
    DeskWorld,
    desk_fakes,
    world_container,
)


@dataclass
class Trade:
    """The mode, its venues' fakes and its actions."""

    view: TradeView
    presenter: TradePresenter
    fakes: dict[TradingVenue, DeskFakes]
    registry: ActionRegistry
    confirmer: RecordingConfirmer

    def action(self, command_id: str) -> QAction:
        return self.registry.action(command_id)

    @property
    def new_order(self) -> QAction:
        return self.action(NEW_ORDER)

    @property
    def emergency_stop(self) -> QAction:
        return self.action(EMERGENCY_STOP)

    def choose(self, venue: TradingVenue) -> None:
        """Trade → Venue › `venue`, as a click on it."""
        self.action(venue_choice_id(venue)).trigger()


def build_trade(
    qtbot,
    venues: tuple[TradingVenue, ...],
    setups: Mapping[TradingVenue, DeskSetup] | None = None,
) -> Trade:
    """The mode with `venues` enabled, both sharing one bus and stream as in
    the running app; `setups` shapes a venue's fakes."""
    world = DeskWorld()
    fakes = {
        venue: desk_fakes(world, venue, (setups or {}).get(venue)) for venue in venues
    }
    view = TradeView()
    qtbot.addWidget(view)
    presenter = TradePresenter(
        view,
        world_container(world),
        TradeDependencies(
            venues=venues,
            desk=lambda venue: fakes[venue].deps,
            confirmations=YES_TO_EVERY_TABLE_QUESTION,
        ),
    )
    confirmer = RecordingConfirmer()
    registry = bound_actions(
        view, trade_commands(TRADE_ROUTE, venues), presenter.bind_commands, confirmer
    )
    return Trade(view, presenter, fakes, registry, confirmer)
