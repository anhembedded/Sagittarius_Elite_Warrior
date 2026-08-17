"""
Layer 1 sanity test (mirrors test_bootstrapper_di_sanity.py / BOT-058's own
test_backtest_screen_di_sanity.py): boots the app for real, then constructs
the REAL BackTestView + BackTestPresenter against the REAL DI container —
not a mocked dispatcher/thread manager like test_backtest_presenter.py's
unit tests use. Catches a class of bug those structurally cannot: what the
real container actually hands back (a real StrategyRegistry instance, a
real IThreadManager) not matching what BackTestPresenter.__init__ calls on
it, or a QML document that fails to parse against the app's real theme/icon
wiring.

Deliberately construction-only: no button clicks, no requestRun(), no
background thread submitted, no network. Real actions belong in
tests/unit/ (mocked dispatch) or tests/integration/ (fully real, but that's
where BOT-038 lives — an intermittent native Qt/PySide6 segfault that only
shows up running tests/integration/presentation/ui/ as one full block, not
in any individual file). Staying construction-only here keeps this tier
nowhere near that territory while still proving the screen actually boots.
"""

import os
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


@pytest.fixture
def booted_app():
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )

    app = create_app(config_manager)

    # Boot for real (no dispatch mocking) — only the WebSocket client/socket
    # manager are patched, since HostedService.start() would otherwise try
    # to touch the network (same as the other sanity fixtures).
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


def test_backtest_screen_constructs_against_the_real_container(
    qapp, booted_app, request
):
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    presenter = BackTestPresenter(view, booted_app.context.container)

    assert presenter._view_model is not None
    assert view.chart_controls is not None
    assert len(view.chart_cards) == 1


def test_backtest_screen_qml_parses_clean_against_real_theme_and_icons(
    qapp, booted_app, request
):
    """Separate from the construction assertions above — QML parsing errors
    (a typo'd Theme.* property, a missing icon binding) don't raise a Python
    exception, they only show up in QQuickWidget.errors(), so they need
    their own explicit check."""
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    BackTestPresenter(view, booted_app.context.container)
    qapp.processEvents()

    assert view.top_widget.errors() == []
    assert view.bottom_widget.errors() == []
    assert view.overlay_host.quick_widget.errors() == []
    assert view.top_widget.rootObject() is not None
    assert view.bottom_widget.rootObject() is not None
    assert view.overlay_host.quick_widget.rootObject() is not None
