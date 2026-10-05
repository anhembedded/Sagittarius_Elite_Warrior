"""`MarketView` (`EPIC-033H`): HLD §11.2.1's layout, and what the user does
reported as the view's signals."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_view import (
    MARKET_SURFACE,
    IndicatorChoice,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_source import IStatusSource


@pytest.fixture
def view(qapp):
    made = MarketView()
    made.watchlist.set_symbols(["BTCUSDT", "ETHUSDT"])
    yield made
    made.deleteLater()


def _record(signal) -> list:
    seen: list = []
    signal.connect(seen.append)
    return seen


def test_the_view_renders_the_surface_the_shell_declares() -> None:
    """The view declares its `Surface` because a module may not import
    `shell/`; this keeps that one declaration, not two."""
    assert surfaces_by_id()["market"] == MARKET_SURFACE


def test_the_watchlist_and_the_indicators_are_tabbed_on_the_right(view):
    surface = view.findChild(QMainWindow)
    docks = {dock.windowTitle(): dock for dock in view.findChildren(QDockWidget)}

    assert set(docks) == {"Watchlist", "Indicators"}
    for dock in docks.values():
        assert surface.dockWidgetArea(dock) is Qt.DockWidgetArea.RightDockWidgetArea
    assert surface.tabifiedDockWidgets(docks["Watchlist"]) == [docks["Indicators"]]


def test_an_instruction_shows_until_a_chart_opens(view):
    view.resize(1024, 700)
    view.show()

    assert view.findChild(type(view._no_chart), "lblNoChart").isVisible()
    assert not view.tabs.isVisible()

    view.add_chart("BTCUSDT", ChartCard("BTCUSDT"))
    assert view.tabs.isVisible()

    view.remove_chart("BTCUSDT")
    assert not view.tabs.isVisible()


def test_activating_a_watchlist_row_asks_for_its_chart(view):
    opened = _record(view.symbol_opened)
    table = view._watchlist.view

    table.activated.emit(table.model().index(1, 0))

    assert opened == ["ETHUSDT"]


def test_tabs_are_named_by_symbol_and_closing_one_is_reported(view):
    closed = _record(view.chart_closed)
    view.add_chart("BTCUSDT", ChartCard("BTCUSDT"))
    view.add_chart("ETHUSDT", ChartCard("ETHUSDT"))

    view.tabs.tabCloseRequested.emit(0)

    assert view.open_symbols == ("BTCUSDT", "ETHUSDT")
    assert view.current_symbol == "ETHUSDT"
    assert closed == ["BTCUSDT"]


def test_checking_an_indicator_reports_every_checked_key(view):
    view.set_indicator_choices(
        (
            IndicatorChoice("ema_20", "EMA 20", True),
            IndicatorChoice("rsi_14", "RSI 14", False),
        )
    )
    changed = _record(view.indicators_changed)

    view.indicators.item(1).setCheckState(Qt.CheckState.Checked)

    assert changed == [("ema_20", "rsi_14")]


def test_filling_the_checklist_is_not_the_users_choice(view):
    changed = _record(view.indicators_changed)

    view.set_indicator_choices((IndicatorChoice("ema_20", "EMA 20", True),))

    assert changed == []


def test_the_status_bar_words_are_offered_to_the_window(view):
    view.set_connection_text("Exchange: not checked")
    view.set_stream_text("Market data: live")

    assert isinstance(view, IStatusSource)
    assert [label.text() for label in view.status_widgets()] == [
        "Exchange: not checked",
        "Market data: live",
    ]


def test_the_modes_log_is_a_channel_of_the_output_pane(view):
    channel = view.output_channel()

    assert channel is not None
    assert (channel.channel_id, channel.title) == ("market", "Market")
