"""View → Chart (`BOT-155`): the chart mode and the layers reach the
keyboard through the menu, in step with the chart's own toolbar, whose
buttons take no focus (review of PR #371)."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_commands import (
    CHART_MENU,
    CHART_PREFIX,
    SHOW_CANDLESTICK,
    SHOW_EQUITY,
    SHOW_INDICATORS,
    SHOW_SIDE_BY_SIDE,
    SHOW_TRADE_FLAGS,
    SHOW_VOLUME,
    backtest_commands,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_screen import (
    BACKTEST_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.chart_display_commands import (
    ChartDisplayCommands,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
    ChartDisplayMode,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_controls import (
    BacktestChartControls,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.signal_wiring import (
    connect_chart_controls,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    ZOOM_IN,
    chart_command_id,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry
from Sagittarius_Elite_Warrior.tests.unit.modules.backtesting.ui.test_backtest_presenter import (
    _build_presenter_with_registry,
    _FakeStrategy,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import shell_menus
from sagittarius_engine.extensions.pyside_mvc.workbench.access_key_assignment import (
    assign_access_keys,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    access_keys,
)

_ALL = (
    SHOW_CANDLESTICK,
    SHOW_EQUITY,
    SHOW_SIDE_BY_SIDE,
    SHOW_INDICATORS,
    SHOW_VOLUME,
    SHOW_TRADE_FLAGS,
)


@pytest.fixture
def menu(qapp):
    """The shell's View → Chart actions, bound to commands parented to a
    stand-in view, and the toolbar the view would build."""
    view = QObject()
    commands = ChartDisplayCommands(view)
    chart = [c for c in backtest_commands(BACKTEST_ROUTE) if c.menu_path == CHART_MENU]
    registry = bound_actions(view, chart, commands.bind_commands)
    controls = BacktestChartControls()
    yield view, {cid: registry.action(cid) for cid in _ALL}, controls
    controls.deleteLater()
    view.deleteLater()


def test_every_command_is_off_until_a_chart_is_drawn(menu):
    _view, actions, _controls = menu

    assert not any(a.isEnabled() for a in actions.values())


def test_the_menu_shows_what_the_toolbar_shows(menu):
    view, actions, controls = menu

    ChartDisplayCommands.follow_controls_of(view, controls)

    assert all(a.isEnabled() for a in actions.values())
    assert actions[SHOW_CANDLESTICK].isChecked()
    assert not actions[SHOW_EQUITY].isChecked()
    assert all(
        actions[c].isChecked() for c in (SHOW_INDICATORS, SHOW_VOLUME, SHOW_TRADE_FLAGS)
    )


def test_picking_a_chart_mode_in_the_menu_switches_the_chart(menu):
    view, actions, controls = menu
    ChartDisplayCommands.follow_controls_of(view, controls)
    modes: list[str] = []
    controls.sig_mode_changed.connect(modes.append)

    actions[SHOW_EQUITY].trigger()

    assert modes == [ChartDisplayMode.EQUITY.value]
    assert controls.display_actions()[ChartDisplayMode.EQUITY.value].isChecked()
    assert not actions[SHOW_CANDLESTICK].isChecked()


def test_a_layer_unchecked_in_the_menu_is_hidden_and_the_reverse(menu):
    view, actions, controls = menu
    ChartDisplayCommands.follow_controls_of(view, controls)
    volume: list[bool] = []
    controls.sig_volume_toggled.connect(volume.append)

    actions[SHOW_VOLUME].trigger()
    assert volume == [False]

    controls.display_actions()["indicators"].trigger()
    assert not actions[SHOW_INDICATORS].isChecked()


def test_a_layer_the_chart_mode_turns_off_is_off_in_the_menu(menu):
    view, actions, controls = menu
    ChartDisplayCommands.follow_controls_of(view, controls)

    controls.set_trade_flags_enabled(False)

    assert not actions[SHOW_TRADE_FLAGS].isEnabled()


def test_a_view_with_no_chart_turns_every_command_off(menu):
    view, actions, controls = menu
    ChartDisplayCommands.follow_controls_of(view, controls)

    ChartDisplayCommands.follow_controls_of(view, None)

    assert not any(a.isEnabled() for a in actions.values())


# -- the real presenter's graph (`testing-rule.md` §2: a wiring is asserted
#    against what production builds, not against the subject alone) --------


@pytest.fixture
def presenter_menu(qapp, request):
    strategy_registry = StrategyRegistry()
    strategy_registry.register("fake_strategy", _FakeStrategy)
    config = Mock()
    config.get_all.return_value = {}
    config.get.side_effect = lambda key, default=None: default
    presenter = _build_presenter_with_registry(
        qapp, Mock(), Mock(), config, strategy_registry, request
    )
    owner = QObject()
    request.addfinalizer(owner.deleteLater)
    registry = bound_actions(
        owner, backtest_commands(BACKTEST_ROUTE), presenter.bind_commands
    )
    return presenter, {cid: registry.action(cid) for cid in _ALL}


def test_the_presenter_s_first_chart_is_in_the_menu_at_once(presenter_menu):
    """The first toolbar is drawn before the commands are bound."""
    presenter, actions = presenter_menu

    assert actions[SHOW_CANDLESTICK].isEnabled()
    assert actions[SHOW_CANDLESTICK].isChecked()

    actions[SHOW_EQUITY].trigger()

    mode_action = presenter.view.chart_controls.display_actions()
    assert mode_action[ChartDisplayMode.EQUITY.value].isChecked()


def test_a_chart_drawn_for_a_new_symbol_is_followed_too(presenter_menu):
    presenter, actions = presenter_menu
    first = presenter.view.chart_controls

    presenter.view.render_symbol_cards(["ETHUSDT"])
    connect_chart_controls(presenter)
    actions[SHOW_VOLUME].trigger()

    assert presenter.view.chart_controls is not first
    assert not presenter.view.chart_controls.display_actions()["volume"].isChecked()


def test_view_chart_takes_no_access_key_of_the_view_menu():
    """The submenu sits beside the window's own View items (one per mode,
    keys assigned by the window), T&oolbars and Stat&us bar; the panels'
    toggles take their keys after it. Inside it, each key is its own."""
    own = (shell_menus.TOOLBARS_MENU, "Stat&us bar")
    reserved = [key for text in own for key in access_keys(text)]
    registry = real_screen_registry(Mock())
    titles = [s.nav.title for s in registry.modes() if s.nav is not None]
    taken = {
        key
        for text in (*own, *assign_access_keys(titles, reserved))
        for key in access_keys(text)
    }
    items = [c for c in backtest_commands(BACKTEST_ROUTE) if c.menu_path == CHART_MENU]
    keys = [key for c in items for key in access_keys(c.text)]

    assert set(access_keys(CHART_MENU[-1])) & taken == set()
    assert len(keys) == len(set(keys)) == len(items)


# -- the chart card's own toolbar (`BOT-156`) --------------------------------


@pytest.fixture
def presenter_registry(qapp, request):
    strategy_registry = StrategyRegistry()
    strategy_registry.register("fake_strategy", _FakeStrategy)
    config = Mock()
    config.get_all.return_value = {}
    config.get.side_effect = lambda key, default=None: default
    presenter = _build_presenter_with_registry(
        qapp, Mock(), Mock(), config, strategy_registry, request
    )
    owner = QObject()
    request.addfinalizer(owner.deleteLater)
    registry = bound_actions(
        owner, backtest_commands(BACKTEST_ROUTE), presenter.bind_commands
    )
    return presenter, registry.action(chart_command_id(CHART_PREFIX, ZOOM_IN))


def test_the_chart_s_zoom_is_in_view_chart_for_the_first_chart(presenter_registry):
    presenter, zoom_in = presenter_registry
    zoomed: list[str] = []
    card = presenter.view.chart_cards[0].chart_card
    card.zoom.zoom_in.triggered.connect(lambda: zoomed.append("in"))

    assert zoom_in.isEnabled()
    zoom_in.trigger()

    assert zoomed == ["in"]


def test_the_chart_s_zoom_follows_a_chart_drawn_for_a_new_symbol(presenter_registry):
    presenter, zoom_in = presenter_registry
    first = presenter.view.chart_cards[0].chart_card
    zoomed: list[str] = []
    first.zoom.zoom_in.triggered.connect(lambda: zoomed.append("first"))

    presenter.view.render_symbol_cards(["ETHUSDT"])
    connect_chart_controls(presenter)
    card = presenter.view.chart_cards[0].chart_card
    card.zoom.zoom_in.triggered.connect(lambda: zoomed.append("new"))
    zoom_in.trigger()

    assert zoomed == ["new"]
