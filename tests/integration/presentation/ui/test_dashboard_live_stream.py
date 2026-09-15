from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.application.services.live_strategy_factory import (
    LiveStrategyFactory,
)
from Sagittarius_Elite_Warrior.src.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.mock_klines import (
    build_mock_klines,
)


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.event_bus = MagicMock()
    app.container = MagicMock()

    from sagittarius_engine.interfaces.i_config import IConfig

    mock_config = MagicMock()
    matrix = {
        "IDLE": {"start_stream_button": True, "stop_stream_button": False},
        "LIVE": {"start_stream_button": False, "stop_stream_button": True},
        "LOCKED": {"start_stream_button": False, "stop_stream_button": False},
        "ERROR": {"start_stream_button": True, "stop_stream_button": False},
    }
    mock_config.get_all.return_value = matrix
    # Key-aware, not a blanket stub: BasePresenter reads the UI matrix via
    # get_all() (above), but also reads individual keys via get() (e.g.
    # dev.mode, BOT-034's CHART_CARD_MIN_FETCH_CANDLES) — those must fall
    # through to the caller's own `default`, not receive the matrix dict.
    mock_config.get.side_effect = lambda key, default=None, cast=None: default

    # Mock IThreadManager - execute immediately instead of thread
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    mock_thread_mgr = MagicMock()

    def submit_sync(task, *args, **kwargs):
        # Must return a real Future, not None: ExclusiveAction.submit()
        # (BOT-069, landed after this fixture was first written) calls
        # `future.add_done_callback(...)` on whatever IThreadManager.submit()
        # returns, to release its exclusive-action slot once the task
        # settles. Returning None here used to work because nothing read
        # the return value — now it crashes with AttributeError, which
        # @safe_ui_action (BOT-066, also later) catches and logs instead of
        # raising, so the crash was invisible and just left the
        # "load_history" slot stuck forever, silently rejecting every
        # subsequent _on_start_stream() call via its own try_start() guard.
        future: Future = Future()
        try:
            future.set_result(task(*args, **kwargs))  # Execute synchronously
        except Exception as exc:  # noqa: BLE001 - mirror the real thread pool's contract
            future.set_exception(exc)
        return future

    mock_thread_mgr.submit.side_effect = submit_sync

    # `EPIC-023C` — must be real, not `MagicMock()`, same reasoning
    # `test_dashboard_presenter.py`'s own fixtures document.
    strategy_registry = StrategyRegistry()
    strategy_registry.register("ema_crossover", EmaCrossoverStrategy)
    strategy_session = LiveStrategySession(
        LiveStrategyFactory(
            strategy_registry, MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
    )
    equity_recorder = EquityCurveRecorder()

    history = FakeHistoricalKlines()
    stream = FakeMarketStream()

    def resolve_side_effect(interface):
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher

        if interface == IHistoricalKlines:
            return history
        if interface == IMarketStream:
            return stream
        if interface == IConfig:
            return mock_config
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return app
        if interface == StrategyRegistry:
            return strategy_registry
        if interface == LiveStrategySession:
            return strategy_session
        if interface == EquityCurveRecorder:
            return equity_recorder
        return MagicMock()

    app.container.resolve.side_effect = resolve_side_effect
    return app


def test_dashboard_integration_start_stream_chart_rendering(qapp, mock_app):
    """
    Simulates clicking Start Stream, and verifies that the history data is properly
    rendered and repainted on the ChartCard.
    """
    mock_app.resolve.return_value = mock_app
    view = DashboardView()
    presenter = DashboardPresenter(view, mock_app.container)
    view.presenter = presenter

    # `EPIC-025` PR 1.1 — the history is seeded into the port's store instead
    # of returned by a dispatch branch. `BUG-047`'s trap, which the deleted
    # comment here described at length, cannot recur: it was a flat list
    # reaching `_run_load_history`'s `isinstance(results, dict)` guard, which
    # logged "Unexpected response format" and returned before touching the
    # candlestick — never raising, so it stayed invisible. `load_many()` has
    # one return type, and that guard is gone with it.
    history = presenter._stream_controller._historical_klines
    # One candle, because this test's assertion is that exactly one history
    # row reaches the candlestick and is repainted — the old dispatch branch
    # returned a single mock kline for the same reason.
    history.seed(build_mock_klines(presenter._active_symbol)[:1])

    # `EPIC-025` PR 1.1b — the stream is a port too, so the branch that used
    # to answer `StartLiveStreamCommand` with a `MagicMock` whose `.success`
    # was `True` is gone. `FakeMarketStream` answers a real `StreamOutcome`,
    # which is what the screen now reads.
    mock_app.dispatch.side_effect = lambda *_args, **_kwargs: MagicMock()

    # Track update() calls on the candlestick item
    from unittest.mock import patch

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.FastCandlestickItem.update"
    ):
        # Trigger Load History first
        presenter._on_load_history()

        # Trigger Start Stream
        presenter._on_start_stream()

        # Check if the chart was created
        assert len(presenter.active_charts) == 1
        # Keyed by whatever symbol the screen loaded — EPIC-010H made that come
        # from Settings rather than a module constant.
        card = presenter.active_charts[presenter._active_symbol]

        # Assert history was added to the candlestick
        assert len(card.candlestick.history_data) == 1
