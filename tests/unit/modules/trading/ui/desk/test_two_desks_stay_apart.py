"""`EPIC-028L` — the Futures and the Spot desk open together, and nothing on
one reaches the other: not an order, not a signal, not a chart stream, not
an Enable.

@details Both desks are built on one `DeskWorld`, so they share the bus and
the market stream exactly as the two routes do in the running app; each has
its own venue's fakes behind its ports (`desk_screen_fixtures.py`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .account_tabs_fixtures import order
from .desk_screen_fixtures import STRATEGY_KEY, Desk, DeskWorld, build_desk, market_of

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


def _two_desks(qtbot) -> tuple[DeskWorld, Desk, Desk]:
    world = DeskWorld()
    return world, build_desk(qtbot, FUTURES, world), build_desk(qtbot, SPOT, world)


def _open_order_ids(desk: Desk) -> list[str]:
    model = desk.view.account_tabs.open_orders_panel.table.model().sourceModel()
    return sorted(row.client_order_id for row in model.rows)


def _signal(symbol: str, venue: TradingVenue | None) -> SignalGeneratedEvent:
    return SignalGeneratedEvent(
        signal=Signal(
            symbol=symbol,
            action=SignalAction.BUY,
            reason=f"cross on {venue.value if venue else 'a backtest'}",
            price=100.0,
            time=datetime(2026, 10, 2, 9, 30, tzinfo=UTC),
        ),
        venue=venue,
    )


def test_an_order_on_one_venue_is_listed_on_that_desk_only(qtbot, qapp) -> None:
    world, futures, spot = _two_desks(qtbot)

    world.bus.emit(
        OrderFilledEvent(
            order=order("BTCUSDT", "SEW-spot"),
            fill_price=Decimal(0),
            fill_quantity=Decimal(0),
            venue=SPOT,
        )
    )
    qapp.processEvents()

    assert _open_order_ids(spot) == ["SEW-spot"]
    assert _open_order_ids(futures) == []


def test_a_signal_reaches_its_own_venues_strategy_card_only(qtbot, qapp) -> None:
    """Both desks armed the same symbol; a backtest's signal (`venue=None`)
    reaches neither."""
    world = DeskWorld()
    desks = {}
    for venue in (FUTURES, SPOT):
        desk = build_desk(qtbot, venue, world)
        desk.armed.seed(
            LiveStrategyConfig(
                strategy_key=STRATEGY_KEY, symbol="BTCUSDT", interval="1m"
            )
        )
        desk.presenter.strategy.refresh()
        desks[venue] = desk

    world.bus.emit(_signal("BTCUSDT", None))
    world.bus.emit(_signal("BTCUSDT", SPOT))
    qapp.processEvents()

    spot_text = desks[SPOT].presenter.desk.strategy_card.lastSignalText
    assert "cross on" in spot_text
    assert "spot_testnet" in spot_text
    assert desks[FUTURES].presenter.desk.strategy_card.lastSignalText == ""


def test_each_desk_streams_its_own_market_and_enabling_one_leaves_the_other(
    qtbot,
) -> None:
    world, futures, spot = _two_desks(qtbot)

    qtbot.mouseClick(
        futures.view.findChild(QPushButton, "btnToggleTrading"),
        Qt.MouseButton.LeftButton,
    )

    assert futures.session.enables == 1
    assert spot.session.enables == 0
    assert world.stream.held_by("desk.spot_testnet") is None

    qtbot.mouseClick(
        spot.view.findChild(QPushButton, "btnToggleTrading"), Qt.MouseButton.LeftButton
    )

    held_futures = world.stream.held_by("desk.futures_testnet")
    held_spot = world.stream.held_by("desk.spot_testnet")
    assert held_futures is not None
    assert held_spot is not None
    assert held_futures.market_type is market_of(FUTURES)
    assert held_spot.market_type is market_of(SPOT)


def test_an_emergency_stop_on_one_desk_stops_that_venue_only(qtbot) -> None:
    _, futures, spot = _two_desks(qtbot)
    futures.session.set_enabled(enabled=True)
    spot.session.set_enabled(enabled=True)

    qtbot.mouseClick(
        spot.view.findChild(QPushButton, "btnEmergencyStop"), Qt.MouseButton.LeftButton
    )

    assert spot.session.emergency_stops == 1
    assert futures.session.emergency_stops == 0
    assert futures.session.snapshot().enabled is True
