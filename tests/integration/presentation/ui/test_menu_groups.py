"""Related commands sit together in their menu, a separator between groups
(`BOT-157`, MS `cmd-menus`): read from the booted window's menus as each
mode fills them, so a lost `group` on a contribution, or on its way into the
Engine's descriptor, turns this red."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QMenu
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_screen import (
    BACKTEST_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    plain_text,
    top_menus,
)


def _groups(menu: QMenu) -> list[list[str]]:
    """The menu's items, split where a separator stands."""
    groups: list[list[str]] = [[]]
    for action in menu.actions():
        if action.isSeparator():
            groups.append([])
        elif action.isVisible():
            groups[-1].append(plain_text(action.text()))
    return groups


def _view_groups(window: QMainWindow, submenu: str | None = None) -> list[list[str]]:
    """View's groups, or those of its `submenu`, read while the menus the
    window filled for the showing mode are held."""
    menus = top_menus(window)
    view = dict(menus)["View"]
    if submenu is None:
        return _groups(view)
    for action in view.actions():
        menu = action.menu()
        if menu is not None and plain_text(action.text()) == submenu:
            return _groups(menu)
    raise KeyError(submenu)


def test_backtest_view_chart_shows_its_mode_its_layers_and_its_navigation(
    main_window, navigate
):
    navigate(BACKTEST_ROUTE)

    groups = _view_groups(main_window, "Chart")
    assert groups[:2] == [
        ["Candlestick", "Equity curve", "Side by side"],
        ["Strategy indicators", "Volume", "Buy/sell flags"],
    ]
    assert groups[2][0] == "More timeframes…"
    assert groups[2][-1] == "Go live"
    assert len(groups) == 3


def test_market_view_sets_the_market_choice_apart_from_the_chart_commands(
    main_window, navigate
):
    navigate(MARKET_ROUTE)

    groups = _view_groups(main_window)

    assert ["Spot market", "Futures market"] in groups
    loads = next(group for group in groups if "Load older candles" in group)
    assert loads[:3] == ["Load older candles", "Load range…", "Back to live"]
