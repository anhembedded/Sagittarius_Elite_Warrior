"""The selected bot's orders and fills are written in its symbol's filters
(`EPIC-033N`): a price in the tick size, a quantity in the step size, read
from the bot's own venue's metadata cache, as the desk and the Watchlist
write theirs. A column of something else (a grid level) is not quoted, and
a bot on a venue this run does not serve keeps the magnitude rule."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtWidgets import QTableView
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    BotFill,
    BotFills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotOrderLine,
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import displayed_text
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    PRECISION_ROLE,
    Precision,
)

from .bots_screen_fixtures import BotsScreen, stored

_TICK = Precision(Decimal("0.01"))
_STEP = Precision(Decimal("0.00001"))


def _progress() -> BotProgress:
    return BotProgress(
        realised_profit=Decimal("1.5"),
        completed_cycles=1,
        open_orders=1,
        inventory=Decimal(0),
        average_cost=None,
        reason="",
        reason_detail="",
        orders=(
            BotOrderLine(
                level=3,
                side="BUY",
                price=Decimal("64250.123"),
                quantity=Decimal("0.0012345"),
                executed=Decimal(0),
                client_order_id="gbot-a00001-3",
            ),
        ),
    )


def _fills() -> BotFills:
    return BotFills(
        fills=(
            BotFill(
                time=datetime(2026, 10, 4, 12, tzinfo=UTC),
                side="SELL",
                price=Decimal("64300.456"),
                quantity=Decimal("0.0012345"),
                client_order_id="gbot-a00001-4",
            ),
        )
    )


def _select(screen: BotsScreen, venue: TradingVenue | None = None) -> None:
    screen.settle()
    bot: BotSnapshot = dataclasses.replace(
        screen.view.model.bots[0], progress=_progress()
    )
    if venue is not None:
        bot = dataclasses.replace(bot, venue=venue)
    screen.view.model.set_selected(bot)
    screen.view.model.set_fills(_fills())


def _precision(model: RowTableModel, key: str) -> object:
    return model.data(model.index(0, model.column(key)), PRECISION_ROLE)


def _text(screen: BotsScreen, name: str, model: RowTableModel, key: str) -> str:
    view = screen.view.findChild(QTableView, name)
    return displayed_text(view, 0, model.column(key))


def test_the_orders_are_quoted_in_the_bots_symbol_filters(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    _select(screen)
    orders = screen.view.orders.orders

    assert _precision(orders, "price") == _TICK
    assert _precision(orders, "quantity") == _STEP
    assert _precision(orders, "executed") == _STEP
    assert _precision(orders, "level") is None
    assert _text(screen, "tblBotOrders", orders, "quantity") == "0.00123"


def test_the_fills_are_quoted_in_the_bots_symbol_filters(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    _select(screen)
    fills = screen.view.fills.fills

    assert _precision(fills, "price") == _TICK
    assert _precision(fills, "quantity") == _STEP
    assert _text(screen, "tblBotFills", fills, "quantity") == "0.00123"


def test_a_bot_on_a_venue_this_run_does_not_serve_keeps_the_magnitude_rule(
    open_bots_screen,
) -> None:
    """A bot file may name a venue the configuration no longer enables; its
    tables still show, written by magnitude, and nothing raises."""
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    _select(screen, TradingVenue.FUTURES_TESTNET)
    orders = screen.view.orders.orders

    assert _precision(orders, "price") is None
    assert _text(screen, "tblBotOrders", orders, "quantity") == "0.0012345"


def test_with_no_bot_selected_nothing_is_quoted(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    _select(screen)
    screen.view.model.set_selected(None)

    assert screen.view.orders.orders.rows == ()
    assert screen.view.fills.fills.rows == ()
