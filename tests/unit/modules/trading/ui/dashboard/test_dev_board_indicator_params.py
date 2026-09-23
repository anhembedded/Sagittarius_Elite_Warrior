"""`BOT-063` — the Dev Board's per-indicator-script params button/dialog.

`StrategyParamsDialog` is patched everywhere below — its real `.exec()` is
modal, and this suite runs under `QT_QPA_PLATFORM=offscreen` with no human
to dismiss it (`BUG-134`/`BUG-048` warn about the exact same hazard); a
hanging test is worse than a failing one.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_panel import (
    DevBoardPanel,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_catalog import (
    IndicatorScriptCatalog,
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

_DIALOG_PATH = (
    "Sagittarius_Elite_Warrior.src.support.ui_kit.param_form.StrategyParamsDialog"
)


class _FakeConfig:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, key: str, default: str = "") -> str:
        return self._values.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._values[key] = value


@pytest.fixture
def view_model(qapp):
    return DashboardQmlViewModel()


@pytest.fixture
def panel(qapp, view_model, request):
    controls = DevBoardPanel(view_model)
    host = QWidget()
    layout = QVBoxLayout(host)
    for _title, card in controls.dock_panels:
        layout.addWidget(card)
    host.resize(380, 700)
    host.show()
    qapp.processEvents()
    request.addfinalizer(host.deleteLater)
    return controls


def test_a_script_with_declared_inputs_gets_a_params_button(qapp, panel, view_model):
    view_model.script_model.set_available({"ema_20": Ema20Script})
    qapp.processEvents()

    assert "ema_20" in panel._script_param_buttons
    assert (
        panel._script_param_buttons["ema_20"].objectName() == "btnScriptParams_ema_20"
    )


def test_a_script_with_no_declared_inputs_gets_no_params_button(
    qapp, panel, view_model
):
    view_model.script_model.set_available({"ema_cross": EmaCrossScript})
    qapp.processEvents()

    assert "ema_cross" not in panel._script_param_buttons


def test_clicking_the_params_button_opens_without_crashing(qapp, panel, view_model):
    """The regression BOT-063 exists to close: opening a script's own
    params dialog must not hit the same `QDialog(non-widget parent)` shape
    `BUG-134` did for the strategy dialog."""
    registry = IndicatorScriptRegistry()
    registry.register("ema_20", Ema20Script)
    catalog = IndicatorScriptCatalog(registry)
    store = IndicatorScriptParamsStore(_FakeConfig())
    panel.set_indicator_script_dependencies(catalog, store)
    view_model.script_model.set_available({"ema_20": Ema20Script})
    qapp.processEvents()

    with patch(_DIALOG_PATH) as dialog_cls:
        panel._open_script_params_dialog("ema_20")  # must not raise

    dialog_cls.assert_called_once()
    parent = dialog_cls.call_args[0][1]
    assert parent is not panel


def test_opening_script_params_before_dependencies_are_injected_is_a_no_op(
    qapp, panel, view_model
):
    view_model.script_model.set_available({"ema_20": Ema20Script})
    qapp.processEvents()

    with patch(_DIALOG_PATH) as dialog_cls:
        panel._open_script_params_dialog("ema_20")  # no dependencies yet

    dialog_cls.assert_not_called()
