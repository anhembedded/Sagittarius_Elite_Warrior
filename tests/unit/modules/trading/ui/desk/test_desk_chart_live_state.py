"""`EPIC-034G` — a desk's chart says whether it is live. Going live no
longer needs trading to be enabled: the chip's Go live is the desk's own
view-only price stream."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    LiveChartCommand,
    LiveChartState,
)

from .desk_screen_fixtures import DeskWorld, build_desk

S = LiveChartState
SPOT = TradingVenue.SPOT_TESTNET


def test_a_desk_with_trading_off_shows_history_and_can_go_live(qtbot) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, SPOT, world)
    chart = desk.presenter.chart
    assert chart.live_state is S.HISTORY
    assert world.stream.calls == []

    chart.run_command(LiveChartCommand.GO_LIVE)

    assert chart.live_state is S.LIVE
    assert world.stream.held_by("desk.spot_testnet") is not None


def test_a_desk_opened_with_trading_on_is_live(qtbot) -> None:
    desk = build_desk(qtbot, SPOT, trading_on=True)

    assert desk.presenter.chart.live_state is S.LIVE


def test_stop_live_releases_the_desks_stream(qtbot) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, SPOT, world, trading_on=True)

    desk.presenter.chart.run_command(LiveChartCommand.STOP_LIVE)

    assert desk.presenter.chart.live_state is S.HISTORY
    assert world.stream.held_by("desk.spot_testnet") is None


def test_stopping_the_live_price_with_trading_on_says_orders_are_stale(qtbot) -> None:
    desk = build_desk(qtbot, SPOT, trading_on=True)
    statuses: list[str] = []
    desk.presenter.desk.set_status = lambda text, _error=False: statuses.append(text)  # type: ignore[method-assign]

    desk.presenter.chart.run_command(LiveChartCommand.STOP_LIVE)

    assert any("not live" in text and "last stored close" in text for text in statuses)


def test_stopping_the_live_price_with_trading_off_says_nothing(qtbot) -> None:
    desk = build_desk(qtbot, SPOT)
    desk.presenter.chart.run_command(LiveChartCommand.GO_LIVE)
    statuses: list[str] = []
    desk.presenter.desk.set_status = lambda text, _error=False: statuses.append(text)  # type: ignore[method-assign]

    desk.presenter.chart.run_command(LiveChartCommand.STOP_LIVE)

    assert statuses == []
