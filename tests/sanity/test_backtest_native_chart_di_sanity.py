"""BOT-098F6D sanity: proves the real `backtest.chart.backend` config
reaches the real, DI-resolved `BacktestChartHostFactory` and produces a
real `NativeBacktestChartHostAdapter` — through the exact same
`BackTestPresenter.render_symbol_cards()` path production uses, not a
mocked container/factory like the unit tests in
`test_backtest_chart_host.py` use. Mirrors the `booted_app` fixture from
`test_backtest_screen_ui_sanity.py` / `test_native_backtest_chart_host_sanity.py`
so the app's real theme/import bootstrap and DI wiring
(`binance_bot_module.py`'s `BacktestChartHostFactory` binding) are what's
under test, not a hand-rolled shortcut.

This is the acceptance-criteria evidence that native opt-in actually wires
the way to the rendered host in the real app, closing the gap left by the
mocked-container unit tests.
"""

import os
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
    NativeBacktestChartHostAdapter,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


@pytest.fixture
def booted_app_with_native_chart_backend():
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )
    # Added last so it overrides whatever the two JSON sources above say —
    # this is the exact config key BackTestPresenter reads
    # (backtest_presenter.py, ConfigKeys.BACKTEST_CHART_BACKEND).
    config_manager.load_dict({ConfigKeys.BACKTEST_CHART_BACKEND.value: "native"})

    app = create_app(config_manager)
    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        app.boot()
        yield app
        app.stop()


def test_native_backend_config_reaches_the_real_presenter_and_produces_the_native_adapter(
    qapp, booted_app_with_native_chart_backend, request
):
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    BackTestPresenter(view, booted_app_with_native_chart_backend.context.container)
    qapp.processEvents()

    assert len(view.chart_cards) == 1
    assert isinstance(view.chart_cards[0], NativeBacktestChartHostAdapter)
