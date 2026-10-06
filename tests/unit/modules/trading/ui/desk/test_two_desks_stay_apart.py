"""`EPIC-028L` — the Futures and the Spot desk open together, and nothing on
one reaches the other: not an order, not an armed strategy, not a chart
stream, not an Enable.

@details Both desks are built on one `DeskWorld`, so they share the bus and
the market stream exactly as the two routes do in the running app; each has
its own venue's fakes behind its ports (`desk_screen_fixtures.py`).
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.armed_strategy_changed_event import (
    ArmedStrategyChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
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


def test_a_strategy_armed_on_one_venue_is_drawn_on_that_desk_only(qtbot, qapp) -> None:
    """`EPIC-033K` stage 3 — the Bots mode arms a venue's strategy and says
    so on the bus; the desk of that venue draws it, re-read from its own
    venue's session, and the other desk draws nothing."""
    world, futures, spot = _two_desks(qtbot)
    armed = LiveStrategyConfig(
        strategy_key=STRATEGY_KEY, symbol="BTCUSDT", interval="1m"
    )
    # What both venues' sessions hold: only Spot armed.
    spot.armed.seed(armed)

    world.bus.emit(ArmedStrategyChangedEvent(True, venue=SPOT))
    qapp.processEvents()

    spot_drawn = spot.presenter.chart.drawn_strategy
    assert spot_drawn is not None and spot_drawn.symbol == "BTCUSDT"
    assert futures.presenter.chart.armed_config is None
    assert futures.presenter.chart.drawn_strategy is None


def test_a_disarm_on_the_bus_clears_that_desks_strategy_lines(qtbot, qapp) -> None:
    world, _futures, spot = _two_desks(qtbot)
    spot.armed.seed(
        LiveStrategyConfig(strategy_key=STRATEGY_KEY, symbol="BTCUSDT", interval="1m")
    )
    world.bus.emit(ArmedStrategyChangedEvent(True, venue=SPOT))
    qapp.processEvents()

    spot.armed.seed(None)
    world.bus.emit(ArmedStrategyChangedEvent(False, venue=SPOT))
    qapp.processEvents()

    assert spot.presenter.chart.armed_config is None
    assert spot.presenter.chart.drawn_strategy is None


def test_an_armed_strategy_is_drawn_only_over_its_own_symbol(qtbot, qapp) -> None:
    """PR #376 review: the strategy's lines replayed over another pair's
    candles would show signals it never computes. The desk shows BTCUSDT
    1m; the venue arms ETHUSDT 1m from the Bots mode."""
    world, _futures, spot = _two_desks(qtbot)
    spot.armed.seed(
        LiveStrategyConfig(strategy_key=STRATEGY_KEY, symbol="ETHUSDT", interval="1m")
    )
    world.bus.emit(ArmedStrategyChangedEvent(True, venue=SPOT))
    qapp.processEvents()
    chart = spot.presenter.chart

    assert chart.armed_config is not None and chart.drawn_strategy is None

    spot.presenter.show_symbol("ETHUSDT")

    drawn = chart.drawn_strategy
    assert drawn is not None and drawn.symbol == "ETHUSDT"


def test_each_desk_streams_its_own_market_and_enabling_one_leaves_the_other(
    qtbot,
) -> None:
    world, futures, spot = _two_desks(qtbot)

    futures.actions.enable_trading.trigger()

    assert futures.session.enables == 1
    assert spot.session.enables == 0
    assert world.stream.held_by("desk.spot_testnet") is None

    spot.actions.enable_trading.trigger()

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

    spot.actions.emergency_stop.trigger()

    assert spot.session.emergency_stops == 1
    assert futures.session.emergency_stops == 0
    assert futures.session.snapshot().enabled is True
