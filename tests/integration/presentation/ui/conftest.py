import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

# Force offscreen rendering for headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.main import create_app
from Binace_Bot.src.presentation.ui.main_window import MainWindow

# Shared with any test module in this directory that needs a real, unmocked
# thread pool (e.g. async/race-condition reproductions) — kept in one place
# so `_MOCK_KLINE_COUNT` never silently drifts between files.
MOCK_KLINE_COUNT = 5


def build_mock_klines(symbol: str, interval: str = "1m") -> list[MarketData]:
    """Newest-first MarketData list, matching what the real repository
    returns (DashboardPresenter reverses it before rendering)."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    klines = []
    for i in range(MOCK_KLINE_COUNT):
        open_time = base_time + timedelta(minutes=i)
        close_time = open_time + timedelta(minutes=1)
        klines.append(
            MarketData(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                open_price=100.0 + i,
                high_price=101.0 + i,
                low_price=99.0 + i,
                close_price=100.5 + i,
                volume=10.0,
                close_time=close_time,
                quote_asset_volume=1000.0,
                number_of_trades=5,
                taker_buy_base_asset_volume=5.0,
                taker_buy_quote_asset_volume=500.0,
            )
        )
    klines.reverse()
    return klines


@pytest.fixture
def app_engine(request, monkeypatch):
    """
    Boot the Sagittarius Engine with all configurations but mock the
    dispatcher backend. Defaults to dev.mode=False; parametrize indirectly
    with `True` to boot with dev mode on.

    Deliberately keeps the REAL `IThreadManager` (a genuine
    `ThreadPoolExecutor`, see `sagittarius_engine/infrastructure/thread_manager.py`)
    unmocked — several tests in this directory exist specifically to
    reproduce race conditions that only manifest with real background
    threads, not a synchronous `submit()` stub.
    """
    dev_mode = getattr(request, "param", False)
    config_manager = ConfigManager()

    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    app_json = os.path.join(base_dir, "src", "config", "app_config.json")
    user_json = os.path.join(base_dir, "src", "config", "user_config.json")

    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    if dev_mode:
        config_manager.load_dict({"dev.mode": True})

    engine = create_app(config_manager)

    def mock_dispatch(command_type, command_obj):
        response = MagicMock()
        response.success = True
        if command_type is GetHistoricalKlinesQuery:
            response.data = build_mock_klines(command_obj.symbol)
        else:
            response.data = []
        return response

    monkeypatch.setattr(engine, "dispatch", mock_dispatch)

    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher

    container_dispatcher = engine.context.container.resolve(IDispatcher)
    monkeypatch.setattr(container_dispatcher, "dispatch", mock_dispatch)

    engine.boot()
    yield engine
    engine.stop()


@pytest.fixture
def main_window(qapp, app_engine):
    """Instantiate the MainWindow with the mocked engine."""
    window = MainWindow(app_engine)
    window.show()
    return window


@pytest.fixture
def navigate(qapp, main_window, qml_item):
    """
    Clicks a sidebar entry the way a user would and returns that route's
    router registry entry (which holds the lazily-created view/presenter).

    The sidebar is QML (BOT-030 Phase 1), so navigation goes through the
    QML button's `clicked` signal rather than `qtbot.mouseClick` on a
    QPushButton. Centralized here so every screen test shares one
    implementation instead of repeating the item lookup.
    """

    def _navigate(route: str) -> dict:
        root = main_window._sidebar.quick_widget.rootObject()
        button = qml_item(root, f"navButton_{route}")
        assert button is not None, f"No sidebar nav button for route {route!r}"
        button.clicked.emit()
        qapp.processEvents()
        return main_window._router._registry[route]

    return _navigate
