"""`EPIC-028K` — one desk: what it shows when it opens, and its Enable,
Emergency Stop and symbol for its own venue only.

@details The whole desk over verified fakes (`desk_screen_fixtures.py`):
the real `DeskView`, the real `DeskPresenter` and every part it composes,
driven through the view's own controls by their `objectName`.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
    DeskView,
    disabled_text,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.futures_desk_screen import (
    futures_desk_screen,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.conftest import fake_container

from .desk_screen_fixtures import DeskWorld, build_desk, market_of

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


@pytest.mark.parametrize("venue", [FUTURES, SPOT])
def test_opening_a_desk_reads_its_own_markets_history_and_streams_nothing(
    qtbot, venue
) -> None:
    """`BUG-107`: opening a screen is not a request to go on the network."""
    world = DeskWorld()

    build_desk(qtbot, venue, world)

    assert world.history.reads, "the chart reads local history on open"
    assert {read.market for read in world.history.reads} == {market_of(venue)}
    assert world.sync.requests == []
    assert world.stream.calls == []


def test_enabling_trading_puts_this_desks_chart_live_under_its_own_owner(
    qtbot,
) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, FUTURES, world)
    toggle = desk.view.findChild(QPushButton, "btnToggleTrading")

    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)

    assert desk.session.enables == 1
    assert toggle.text() == "Disable Trading"
    held = world.stream.held_by("desk.futures_testnet")
    assert held is not None
    assert held.market_type is market_of(FUTURES)
    assert world.sync.was_asked_for("BTCUSDT")


def test_a_refused_enable_reads_as_an_error_and_leaves_the_chart_local(
    qtbot,
) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, SPOT, world)
    desk.session.enable_raises(RuntimeError("keys rejected"))

    qtbot.mouseClick(
        desk.view.findChild(QPushButton, "btnToggleTrading"), Qt.MouseButton.LeftButton
    )

    status = desk.view.findChild(QLabel, "lblDeskStatus").text()
    assert status.startswith("Error: ")
    assert "keys rejected" in status
    assert world.stream.calls == []


def test_emergency_stop_reaches_this_desks_session_and_rereads_its_account(
    qtbot,
) -> None:
    desk = build_desk(qtbot, FUTURES)
    desk.session.set_enabled(enabled=True)
    reads_before = desk.activity.open_order_reads

    qtbot.mouseClick(
        desk.view.findChild(QPushButton, "btnEmergencyStop"), Qt.MouseButton.LeftButton
    )

    assert desk.session.emergency_stops == 1
    assert desk.activity.open_order_reads > reads_before


def test_picking_a_symbol_points_the_chart_at_it(qtbot) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, SPOT, world)
    combo = desk.view.findChild(QComboBox, "cboDeskSymbol")

    combo.setCurrentText("ETHUSDT")

    assert desk.presenter.chart.shown_symbol == "ETHUSDT"
    assert world.history.reads[-1].symbols == ("ETHUSDT",)


def test_a_desk_refuses_another_venues_ports(qtbot) -> None:
    """A Futures desk driving Spot's ports would place Spot orders from a
    screen titled Futures."""
    with pytest.raises(ValueError, match="Futures desk was given spot_testnet"):
        build_desk(qtbot, FUTURES, ports_venue=SPOT)


@pytest.mark.parametrize("venue", [FUTURES, SPOT])
def test_a_desk_whose_venue_is_off_says_so_and_holds_nothing_that_sends(
    qtbot, venue
) -> None:
    profile = desk_profile_for(venue)
    view = DeskView(profile)
    qtbot.addWidget(view)
    view.show_venue_disabled()

    notice = view.findChild(QLabel, "lblDeskDisabled")
    assert notice is not None
    assert notice.text() == disabled_text(profile)
    assert view.findChild(QPushButton, "btnToggleTrading") is None
    assert view.findChild(QPushButton, "btnEmergencyStop") is None


def test_the_futures_route_opens_the_notice_when_only_spot_is_served(qtbot) -> None:
    """The view reads no service (every screen's view builds on a bare
    container); the presenter side, which has the container, decides."""
    container = fake_container(
        {IVenueTradingPorts: FakeVenueTradingPorts(fake_venue_ports(SPOT))}
    )
    screen = futures_desk_screen(container)
    view = screen.view_factory()
    qtbot.addWidget(view)
    assert view.findChild(QLabel, "lblDeskDisabled") is None

    screen.presenter_factory(view, container)

    notice = view.findChild(QLabel, "lblDeskDisabled")
    assert notice is not None
    assert notice.text() == disabled_text(desk_profile_for(FUTURES))
    assert view.findChild(QPushButton, "btnEmergencyStop") is None
