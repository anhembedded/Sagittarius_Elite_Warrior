"""`EPIC-033I` — the Trade mode laid out as HLD §11.2.1 lists it, one page and
one saved layout per venue, and its host's View and Reset layout following
the venue that shows.

The pages are filled as the presenter fills them (`desk_screen/preview.py`'s
`fill_page`), without an exchange.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QTabBar
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
    ACCOUNT_SUMMARY_TITLE,
    ACCOUNT_TITLE,
    EQUITY_CHART_TITLE,
    ORDER_ENTRY_TITLE,
    STRATEGY_TITLE,
    TRADE_SURFACE,
    DeskView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.preview import (
    fill_page,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_view import (
    TradeView,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.mode_host import ModeHost
from Sagittarius_Elite_Warrior.src.support.ui_kit.surface_stack import ISurfaceStack

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


def _trade(qtbot) -> TradeView:
    view = TradeView()
    qtbot.addWidget(view)
    for venue in (FUTURES, SPOT):
        fill_page(view.add_venue(desk_profile_for(venue)))
    return view


def _dock(page: DeskView, title: str) -> QDockWidget:
    docks = [
        d for d in page.surface.findChildren(QDockWidget) if d.windowTitle() == title
    ]
    assert len(docks) == 1, title
    return docks[0]


def test_the_trade_surface_is_the_one_the_shell_declares() -> None:
    assert surfaces_by_id()["trade"] == TRADE_SURFACE


def test_each_venue_has_its_own_surface_so_its_own_saved_layout(qtbot) -> None:
    view = _trade(qtbot)

    assert isinstance(view, ISurfaceStack)
    assert [s.surface_id for s in view.surfaces()] == [
        "trade.futures_testnet",
        "trade.spot_testnet",
    ]


def test_a_page_is_laid_out_as_the_mode_lists_it(qtbot) -> None:
    view = _trade(qtbot)
    page = view.venue_page(FUTURES)
    surface = page.surface

    assert surface.centralWidget() is page.chart
    right = Qt.DockWidgetArea.RightDockWidgetArea
    bottom = Qt.DockWidgetArea.BottomDockWidgetArea
    for title in (ORDER_ENTRY_TITLE, ACCOUNT_SUMMARY_TITLE):
        assert surface.dockWidgetArea(_dock(page, title)) == right, title
    for title in (ACCOUNT_TITLE, EQUITY_CHART_TITLE, STRATEGY_TITLE):
        assert surface.dockWidgetArea(_dock(page, title)) == bottom, title


def test_order_entry_stands_above_the_summary_and_the_bottom_is_tabbed(
    qtbot,
) -> None:
    """Both right panels in view, the entry on top; one tabbed side only,
    because tabbed panels on two sides made before the window shows leave a
    stale tab bar drawn over the panels (`DeskView._place_right`)."""
    view = _trade(qtbot)
    page = view.venue_page(FUTURES)
    surface = page.surface
    entry = _dock(page, ORDER_ENTRY_TITLE)
    summary = _dock(page, ACCOUNT_SUMMARY_TITLE)
    account = _dock(page, ACCOUNT_TITLE)
    view.resize(1200, 700)
    view.show()
    qtbot.waitExposed(view)

    assert surface.tabifiedDockWidgets(entry) == []
    assert surface.tabifiedDockWidgets(summary) == []
    assert entry.geometry().bottom() < summary.geometry().top()
    assert set(surface.tabifiedDockWidgets(account)) == {
        _dock(page, EQUITY_CHART_TITLE),
        _dock(page, STRATEGY_TITLE),
    }
    assert not account.visibleRegion().isEmpty()


def test_a_page_draws_one_tab_bar_for_its_tabbed_panels(qtbot) -> None:
    view = _trade(qtbot)
    view.resize(1200, 700)
    view.show()
    qtbot.waitExposed(view)

    for venue in (FUTURES, SPOT):
        view.show_venue(venue)
        QApplication.processEvents()
        surface = view.venue_page(venue).surface
        dock_bars = [
            bar
            for bar in surface.findChildren(
                QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly
            )
            if bar.isVisible()
        ]
        assert len(dock_bars) == 1, venue


def test_the_host_lists_the_shown_venues_panels_and_follows_the_choice(qtbot) -> None:
    view = _trade(qtbot)
    host = ModeHost("trade", view)

    futures_toggles = set(host.dock_toggle_actions())
    assert futures_toggles == set(
        view.venue_page(FUTURES).surface.dock_toggle_actions()
    )

    view.show_venue(SPOT)

    assert set(host.dock_toggle_actions()) == set(
        view.venue_page(SPOT).surface.dock_toggle_actions()
    )
    assert futures_toggles.isdisjoint(host.dock_toggle_actions())


def test_the_host_remembers_every_venue_and_resets_the_one_shown(qtbot) -> None:
    """Each venue keeps its own layout: Reset layout puts back the default of
    the venue shown and leaves the other's as the person left it."""
    view = _trade(qtbot)
    host = ModeHost("trade", view)
    host.capture_default_perspective()
    futures, spot = view.venue_page(FUTURES), view.venue_page(SPOT)
    left = Qt.DockWidgetArea.LeftDockWidgetArea
    right = Qt.DockWidgetArea.RightDockWidgetArea
    for page in (futures, spot):
        page.surface.addDockWidget(left, _dock(page, ORDER_ENTRY_TITLE))

    assert host.remembered_hosts() == (host, *view.surfaces())

    view.show_venue(SPOT)
    assert host.reset_perspective()

    assert spot.surface.dockWidgetArea(_dock(spot, ORDER_ENTRY_TITLE)) == right
    assert futures.surface.dockWidgetArea(_dock(futures, ORDER_ENTRY_TITLE)) == left


def test_with_no_venue_the_host_lists_no_panel(qtbot) -> None:
    view = TradeView()
    qtbot.addWidget(view)
    host = ModeHost("trade", view)

    assert view.shown_surface() is None
    assert host.dock_toggle_actions() == ()
    assert host.remembered_hosts() == (host,)


def test_the_log_is_a_channel_of_the_output_pane_once_a_venue_writes_to_it(
    qtbot,
) -> None:
    """`EPIC-033F`: one channel for the mode, every venue's lines in it; a
    run with no venue enabled offers none, as a disabled desk offered none."""
    idle = TradeView()
    qtbot.addWidget(idle)
    view = _trade(qtbot)

    channel = view.output_channel()

    assert idle.output_channel() is None
    assert channel is not None
    assert (channel.channel_id, channel.title) == ("trade", "Trade")
    assert channel.model is view.log
    assert all(view.venue_page(v).log_model is view.log for v in (FUTURES, SPOT))
