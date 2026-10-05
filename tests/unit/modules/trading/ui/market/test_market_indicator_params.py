"""Tools → Indicator parameters… (`BOT-063`, moved from the Dev Board before
`EPIC-033P` deletes it): the Dev Board's four tests, ported to the Market
mode's command, and the saved values reaching the charts that draw the
script.

`StrategyParamsDialog` is patched wherever the command would open it: its
`.exec()` is modal and nothing dismisses it under `offscreen` (`BUG-134`,
`BUG-048`); a hanging test is worse than a failing one.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    INDICATOR_PARAMS,
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_params_store import (
    IndicatorScriptParamsStore,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_cross_script import (
    EmaCrossScript,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from sagittarius_engine.infrastructure.config.dict_config import DictConfig

_DIALOG = (
    "Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_view."
    "StrategyParamsDialog"
)
_WITH_INPUTS, _WITHOUT_INPUTS = 0, 1


@pytest.fixture
def scripts():
    """EMA 20 declares a period; EMA cross declares no input."""
    registry = IndicatorScriptRegistry()
    registry.register("ema_20", Ema20Script)
    registry.register("ema_cross", EmaCrossScript)
    return registry


@pytest.fixture
def store():
    return IndicatorScriptParamsStore(DictConfig({}))


@pytest.fixture
def mode(qapp, build, store):
    owner = QObject()

    def _build(**overrides):
        presenter = build(**overrides)
        registry = bound_actions(
            owner, market_commands(MARKET_ROUTE), presenter.bind_commands
        )
        return presenter, registry.action(INDICATOR_PARAMS)

    yield _build
    owner.deleteLater()


def _select(presenter: MarketPresenter, row: int) -> None:
    presenter.view.indicators.setCurrentRow(row)


def test_the_command_is_on_only_for_a_selected_script_with_inputs(mode, store):
    presenter, action = mode(params_store=store)
    assert not action.isEnabled()

    _select(presenter, _WITH_INPUTS)
    assert action.isEnabled()

    _select(presenter, _WITHOUT_INPUTS)
    assert not action.isEnabled()


def test_opening_the_dialog_does_not_crash_and_parents_it_to_a_widget(mode, store):
    """The regression BOT-063 closed: the dialog's parent is a widget, never
    a non-widget `QObject` (`BUG-134`'s shape for the strategy dialog)."""
    presenter, action = mode(params_store=store)
    _select(presenter, _WITH_INPUTS)

    with patch(_DIALOG) as dialog_cls:
        action.trigger()

    dialog_cls.assert_called_once()
    sink, parent = dialog_cls.call_args.args
    assert isinstance(parent, QWidget)
    assert dialog_cls.call_args.kwargs["title"] == "Indicator Parameters"
    assert sink.botParamsGroups


def test_without_a_store_the_command_is_off_and_opens_nothing(mode):
    presenter, action = mode()
    _select(presenter, _WITH_INPUTS)

    with patch(_DIALOG) as dialog_cls:
        presenter._params.open()

    assert not action.isEnabled()
    dialog_cls.assert_not_called()


def test_a_script_without_inputs_opens_nothing(mode, store):
    presenter, _action = mode(params_store=store)
    _select(presenter, _WITHOUT_INPUTS)

    with patch(_DIALOG) as dialog_cls:
        presenter._params.open()

    dialog_cls.assert_not_called()


def test_saved_parameters_redraw_the_charts_drawing_the_script(
    mode, store, threads, monkeypatch
):
    presenter, action = mode(params_store=store)
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()
    chart = presenter.charts["BTCUSDT"]
    chart.show_indicators(("ema_20",))
    before = next(iter(chart._runner.active["ema_20"].series.values()))[1][-1]
    _select(presenter, _WITH_INPUTS)

    def save_period_5(sink) -> None:
        sink.requestBotParamsSave({"period": 5})

    monkeypatch.setattr(presenter.view, "edit_indicator_params", save_period_5)
    action.trigger()

    after = next(iter(chart._runner.active["ema_20"].series.values()))[1][-1]
    assert store.load_all()["ema_20"]["period"] == 5
    assert after != before
