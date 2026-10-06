"""View → Chart (`BOT-156`): the Market chart toolbar's actions reach the
keyboard through the menu and act on the chart in front, which changes as
tabs are opened, brought forward and closed."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    CHART_PREFIX,
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    ZOOM_IN,
    chart_command_id,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions


@pytest.fixture
def opened(build, threads, request):
    """The Market presenter with BTCUSDT and ETHUSDT open, ETHUSDT in front,
    and the shell's Zoom in bound to it."""
    presenter = build()
    owner = QObject()
    request.addfinalizer(owner.deleteLater)
    registry = bound_actions(
        owner, market_commands(MARKET_ROUTE), presenter.bind_commands
    )
    presenter.on_mode_shown(NavigationSource.RESTORE)
    presenter.view.symbol_opened.emit("ETHUSDT")
    threads.run_all()
    return presenter, registry.action(chart_command_id(CHART_PREFIX, ZOOM_IN))


def _zooms(presenter) -> list[str]:
    zoomed: list[str] = []
    for symbol, chart in presenter.charts.items():
        chart.chart.zoom.zoom_in.triggered.connect(
            lambda _checked=False, symbol=symbol: zoomed.append(symbol)
        )
    return zoomed


def test_zoom_in_acts_on_the_chart_in_front(opened):
    presenter, zoom_in = opened
    zoomed = _zooms(presenter)

    zoom_in.trigger()

    assert zoomed == ["ETHUSDT"]


def test_zoom_in_follows_the_tab_brought_forward(opened):
    presenter, zoom_in = opened
    zoomed = _zooms(presenter)

    presenter.view.symbol_opened.emit("BTCUSDT")
    zoom_in.trigger()

    assert zoomed == ["BTCUSDT"]


def test_the_chart_commands_are_off_once_no_chart_is_open(opened):
    presenter, zoom_in = opened

    presenter.view.chart_closed.emit("ETHUSDT")
    presenter.view.chart_closed.emit("BTCUSDT")

    assert not zoom_in.isEnabled()
