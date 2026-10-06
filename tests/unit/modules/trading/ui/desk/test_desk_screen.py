"""`EPIC-028K` — one desk: what it shows when it opens, and its Enable,
Emergency Stop and symbol for its own venue only.

@details The whole desk over verified fakes (`desk_screen_fixtures.py`):
the real `DeskView`, the real `DeskPresenter` and every part it composes,
driven through the view's own controls by their `objectName`, and through
its commands' real actions (`desk_actions.py`, `EPIC-033D`).
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QComboBox, QLabel
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

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
    toggle = desk.actions.enable_trading

    toggle.trigger()

    assert desk.session.enables == 1
    assert toggle.isChecked()
    assert toggle.isEnabled()
    held = world.stream.held_by("desk.futures_testnet")
    assert held is not None
    assert held.market_type is market_of(FUTURES)
    assert world.sync.was_asked_for("BTCUSDT")


def test_a_desk_opened_with_its_venues_trading_on_goes_live(qtbot) -> None:
    """The PR #308 review: trading turned on before the desk opened left its
    chart on local history, so the order panel valued orders at the last
    stored candle. Opening with trading off stays local (`BUG-107`, above)."""
    world = DeskWorld()

    build_desk(qtbot, SPOT, world, trading_on=True)

    held = world.stream.held_by("desk.spot_testnet")
    assert held is not None
    assert held.market_type is market_of(SPOT)
    assert held.symbols == ("BTCUSDT",)
    # The re-review of PR 308: going live before a symbol was shown started a
    # sync and a stream for "" — a request the user never made.
    assert [request.symbols for request in world.sync.requests] == [("BTCUSDT",)]
    assert [owner for call, owner in world.stream.calls if call == "start"] == [
        "desk.spot_testnet"
    ]


def test_a_refused_enable_reads_as_an_error_and_leaves_the_chart_local(
    qtbot,
) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, SPOT, world)
    desk.session.enable_raises(RuntimeError("keys rejected"))

    desk.actions.enable_trading.trigger()

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

    desk.actions.emergency_stop.trigger()

    assert [asked.title for asked in desk.actions.confirmer.asked] == ["Emergency Stop"]
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


def test_a_desk_refuses_another_venues_strategy(qtbot) -> None:
    """`BOT-158` — a Futures desk arming Spot's strategy would show Spot's
    armed state on a screen titled Futures."""
    with pytest.raises(
        ValueError, match="Futures desk was given spot_testnet's strategy"
    ):
        build_desk(qtbot, FUTURES, strategy_venue=SPOT)


@pytest.mark.parametrize("venue", [FUTURES, SPOT])
def test_a_desks_lines_go_to_the_log_it_was_given_naming_its_venue(
    qtbot, venue
) -> None:
    """`EPIC-033F`, `EPIC-033I`: no log card of its own; its lines are the
    Trade mode's one channel, each saying which venue it is about."""
    desk = build_desk(qtbot, venue)

    desk.actions.enable_trading.trigger()

    assert desk.presenter.desk.log_model is desk.view.log_model
    lines = [entry.message for entry in desk.view.log_model.entries]
    assert lines
    assert all(line.startswith(f"{desk_profile_for(venue).title}: ") for line in lines)
