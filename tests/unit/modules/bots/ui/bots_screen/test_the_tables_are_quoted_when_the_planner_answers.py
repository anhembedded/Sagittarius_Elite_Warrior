"""`EPIC-048B` — the selected bot's orders, fills and ladder take the tick and step sizes the
planner read (`PlannerMarket.terms`), not a venue's cache the screen reached into.

Until the planner answers for a venue and symbol, the tables keep the formatter's magnitude rule;
when it does, the three tables are shown again so the rows on screen are repainted in the new
sizes. An answer that changes nothing shows nothing again. The sizes are kept per venue and
symbol, so another bot on the same symbol is quoted at once.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import Precision

from .bots_screen_fixtures import BotsScreen, stored

_TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.00001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.001"),
    taker_fee=Decimal("0.001"),
    max_notional_per_order=Decimal(500),
    max_open_orders=150,
)
_MARKET = PlannerMarket(_TERMS, None, None, None)


def _resets(model: RowTableModel) -> list[None]:
    shown: list[None] = []
    model.modelReset.connect(lambda: shown.append(None))
    return shown


def _selected(screen: BotsScreen) -> BotsView:
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    return screen.view


def test_an_answer_with_new_sizes_shows_the_three_tables_again(
    open_bots_screen,
) -> None:
    view = _selected(open_bots_screen([stored("a00001", S.RUNNING)]))
    bot = view.model.selected
    assert bot is not None
    view.model.set_selected(None)
    view.model.set_selected(dataclasses.replace(bot, symbol="ETHUSDT"))
    shown = {
        "orders": _resets(view.orders.orders),
        "fills": _resets(view.fills.fills),
        "ladder": _resets(view.ladder.grids),
    }

    view.model.learn_market(_MARKET)

    assert {name: bool(resets) for name, resets in shown.items()} == {
        "orders": True,
        "fills": True,
        "ladder": True,
    }
    assert view.model.precisions.tick("ETHUSDT") == Precision(Decimal("0.01"))


def test_an_answer_that_changes_nothing_shows_nothing_again(open_bots_screen) -> None:
    view = _selected(open_bots_screen([stored("a00001", S.RUNNING)]))
    shown = _resets(view.orders.orders)

    view.model.learn_market(_MARKET)

    assert shown == []


def test_the_sizes_are_kept_per_venue_and_symbol(open_bots_screen) -> None:
    view = _selected(open_bots_screen([stored("a00001", S.RUNNING)]))
    bot = view.model.selected
    assert bot is not None
    precisions = view.model.precisions

    assert precisions.tick(bot.symbol) == Precision(Decimal("0.01"))
    assert precisions.step(bot.symbol) == Precision(Decimal("0.00001"))

    view.model.set_selected(dataclasses.replace(bot, bot_id="b00002"))
    assert precisions.tick(bot.symbol) == Precision(Decimal("0.01"))

    view.model.set_selected(
        dataclasses.replace(bot, bot_id="c00003", venue=TradingVenue.SPOT_MAINNET)
    )
    assert precisions.tick(bot.symbol) is None
