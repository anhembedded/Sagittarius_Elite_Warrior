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
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_state import (
    BacktestUiState,
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


class _InMemoryMarketDataRepository(IMarketDataRepository):
    def __init__(self, klines: list[MarketData]) -> None:
        self._klines = list(klines)

    def save_klines(self, klines: list[MarketData]) -> None:
        self._klines = list(klines)

    def get_latest_kline_time(self, symbol, interval):
        if not self._klines:
            return None
        return self._klines[-1].open_time

    def get_klines(
        self,
        symbol,
        interval,
        start_time=None,
        end_time=None,
        limit=None,
        order_by_desc=False,
    ):
        rows = [
            k
            for k in self._klines
            if k.symbol == symbol and k.interval == interval.value
        ]
        if start_time is not None:
            rows = [k for k in rows if k.open_time >= start_time]
        if end_time is not None:
            rows = [k for k in rows if k.open_time <= end_time]
        rows.sort(key=lambda k: k.open_time, reverse=order_by_desc)
        if limit is not None:
            rows = rows[:limit]
        return rows

    def get_database_status(self, symbol, interval):
        raise NotImplementedError


def _make_runtime_klines(count: int = 240) -> list[MarketData]:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    return [
        MarketData(
            symbol="BTCUSDT",
            interval="1h",
            open_time=start + timedelta(hours=i),
            open_price=10000.0 + i,
            high_price=10010.0 + i,
            low_price=9990.0 + i,
            close_price=10005.0 + i,
            volume=100.0 + i,
            close_time=start + timedelta(hours=i, minutes=59),
            quote_asset_volume=0.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
        for i in range(count)
    ]


def test_toolbar_popups_and_menus_open_on_the_real_backtest_screen(
    qapp, booted_app, request, qml_item
):
    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    BackTestPresenter(view, booted_app.context.container)
    qapp.processEvents()

    toolbar_root = view.top_widget.rootObject()
    overlay_root = view.overlay_host.content_item
    assert toolbar_root is not None
    assert overlay_root is not None

    capital_input = overlay_root.findChild(object, "txtBacktestCapital")
    assert capital_input is not None
    qml_item(toolbar_root, "btnBacktestCapital").clicked.emit()
    qapp.processEvents()
    qapp.processEvents()
    assert capital_input.property("visible") is True

    bot_params_save = overlay_root.findChild(object, "btnBotParamsSave")
    assert bot_params_save is not None
    qml_item(toolbar_root, "btnBacktestBotParams").clicked.emit()
    qapp.processEvents()
    qapp.processEvents()
    assert bot_params_save.property("visible") is True

    assert view.top_widget.errors() == []
    assert view.bottom_widget.errors() == []
    assert view.overlay_host.quick_widget.errors() == []


def test_backtest_screen_real_container_runtime_run_fetch_render_path_stays_clean(
    qapp, booted_app, request
):
    """Regression harness for the reported runtime path under the REAL app
    container: construct the actual Backtest screen, trigger one backtest run,
    let it fetch chart data, then assert every live QQuickWidget surface stays
    error-free after the render burst.

    This intentionally goes one step beyond the construction-only sanity above,
    but remains narrow: one run, no broad UI suite navigation, no real network.
    It exists because the reported bug only appeared after a real runtime
    sequence, not at parse/load time."""
    booted_app.context.container.singleton(
        IMarketDataRepository, _InMemoryMarketDataRepository(_make_runtime_klines())
    )
    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    presenter = BackTestPresenter(view, booted_app.context.container)
    view_model = presenter._view_model

    view_model.selectedTimeframe = "1h"
    config = presenter._build_run_config()
    assert config is not None

    presenter._on_run_backtest()
    presenter._thread_manager.shutdown(wait=True)
    qapp.processEvents()
    qapp.processEvents()

    assert view.top_widget.errors() == []
    assert view.bottom_widget.errors() == []
    assert view.overlay_host.quick_widget.errors() == []
    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert view_model.needsDataSync is False
    assert view._last_klines
    assert view.chart_cards[0]._raw_history

    view.set_chart_mode(presenter.view._chart_mode.EQUITY)
    qapp.processEvents()
    view.set_chart_mode(presenter.view._chart_mode.BOTH)
    qapp.processEvents()
    view.set_chart_mode(presenter.view._chart_mode.OHLC)
    qapp.processEvents()

    assert view.top_widget.errors() == []
    assert view.bottom_widget.errors() == []
    assert view.overlay_host.quick_widget.errors() == []
