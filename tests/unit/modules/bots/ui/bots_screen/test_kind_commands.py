"""`EPIC-033K` stage 2 — each bot kind's own commands: in the Bots menu,
enabled only while a bot of that kind is selected and its toolbar action is,
and on the kind's toolbar (SPEC-014: "each bot type has its own toolbar").

The commands the bots module really contributes, bound by
`bind_bots_commands` over a real `BotsViewModel`, following a real
`GridPanel`, and on the booted screen through the presenter's selection.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
    SuggestedRange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_command_binding import (
    bind_bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    BOTS_MENU,
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.kind_command_binding import (
    KindCommands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_commands import (
    SUGGEST_FROM_ATR,
    SUGGEST_FROM_BOLLINGER,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_rows import (
    StrategiesPanel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.strategies.strategy_fakes import (
    VenueArming,
    venue_strategies,
)

from .bots_screen_fixtures import BotsScreen, stored

_TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.00001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.001"),
    taker_fee=Decimal("0.001"),
    max_notional_per_order=Decimal(5000),
    max_open_orders=100,
)
_ATR = SuggestedRange(Decimal("61234.567"), Decimal("68765.433"))


def _market(atr: SuggestedRange | None) -> PlannerMarket:
    return PlannerMarket(_TERMS, MarketView(Decimal(65000), Decimal(2500)), atr, None)


def _select(screen: BotsScreen, bot_id: str) -> None:
    screen.view.model.select_requested.emit(bot_id)
    screen.settle()


def test_the_grid_commands_are_in_the_bots_menu_not_on_the_mode_s_toolbar() -> None:
    contributed = {
        command.command_id: command for command in real_contributions(Mock()).commands()
    }

    for command_id in (SUGGEST_FROM_ATR, SUGGEST_FROM_BOLLINGER):
        command = contributed[command_id]
        assert command.mode == BOTS_ROUTE
        assert command.menu_path == BOTS_MENU
        assert not command.on_toolbar


def test_a_kind_command_follows_the_kind_s_toolbar_action(qtbot) -> None:
    view_model = BotsViewModel()
    menu = bound_actions(
        QObject(),
        bots_commands(BOTS_ROUTE),
        lambda binder: bind_bots_commands(
            binder,
            view_model,
            venue_strategies(
                StrategiesPanel(), (VenueArming(TradingVenue.SPOT_TESTNET),)
            ),
        ),
    )
    atr = menu.action(SUGGEST_FROM_ATR)
    bollinger = menu.action(SUGGEST_FROM_BOLLINGER)
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.set_config({"lower": "60000", "upper": "70000"})
    assert not atr.isEnabled()

    KindCommands.follow_panel_of(view_model, panel)
    assert not atr.isEnabled()  # no planner range yet
    panel.set_planner_market(_market(_ATR))

    assert atr.isEnabled() and not bollinger.isEnabled()
    assert panel.suggest_atr in panel.toolbar.actions()
    atr.trigger()
    assert (panel.config()["lower"], panel.config()["upper"]) == (
        "61234.57",
        "68765.43",
    )

    KindCommands.follow_panel_of(view_model, None)
    assert not atr.isEnabled()


def test_a_selected_grid_s_commands_are_live_and_another_selection_ends_them(
    open_bots_screen, qtbot
) -> None:
    """On the screen: the presenter hands each selection's editor over; a
    running Grid's parameters are not editable, so its suggestions are off."""
    screen = open_bots_screen(
        [
            stored("a00001", BotLifecycleState.DRAFT),
            stored("a00002", BotLifecycleState.RUNNING),
        ]
    )
    screen.settle()
    atr = screen.actions.action(SUGGEST_FROM_ATR)
    assert not atr.isEnabled()

    _select(screen, "a00001")
    panel = screen.view._kind_panel
    assert isinstance(panel, GridPanel)
    panel.set_planner_market(_market(_ATR))
    assert atr.isEnabled()

    _select(screen, "a00002")
    assert not atr.isEnabled()
