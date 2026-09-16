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
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_equity_curve import (
    FakeEquityCurve,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.mock_klines import (
    build_mock_klines,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.event_bus = MagicMock()
    app.container = MagicMock()

    # Mock IConfig
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

    # Mock IThreadManager

    mock_thread_mgr = MagicMock()

    def submit_sync(task, *args, **kwargs):
        task(*args, **kwargs)

    mock_thread_mgr.submit.side_effect = submit_sync

    # `EPIC-023C` — must be real, not `MagicMock()`: `StrategyArmingCoordinator`
    # reads `strategy_session.config` and formats it into the card's
    # summary, and `restore_into_view_model()` calls
    # `sorted(available_strategies())` — same reasoning
    # `test_dashboard_presenter.py`'s own fixtures document. Built once,
    # outside the closure below, and reused for every resolve() call.
    strategy_registry = StrategyRegistry()
    strategy_registry.register("ema_crossover", EmaCrossoverStrategy)
    strategy_session = LiveStrategySession(
        LiveStrategyFactory(
            strategy_registry, MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
    )
    equity_curve = FakeEquityCurve()
    # `EPIC-025` PR 1.1 — the history read is a port. Seeded with candles
    # anchored to now, because a store honours `start_time`/`end_time` and the
    # Data Range picker's default window is a recent one (see
    # `conftest.build_mock_klines` for the same note).
    history = FakeHistoricalKlines()
    history.seed(list(reversed(build_mock_klines("ETHUSDT"))))

    def resolve_side_effect(interface):
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher

        if interface == IHistoricalKlines:
            return history
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
        if interface == IAccountSnapshot:
            return FakeAccountSnapshot()
        if interface == IEquityCurve:
            return equity_curve
        return MagicMock()

    app.container.resolve.side_effect = resolve_side_effect
    return app


def test_dashboard_integration_load_history(qapp, mock_app):
    mock_app.resolve.return_value = mock_app
    # 1. Setup View and Presenter
    view = DashboardView()
    presenter = DashboardPresenter(view, mock_app.container)
    view.presenter = presenter

    # 2. Simulate User clicking "Load History" on the ControlCard
    # Bypass signal queue by calling the presenter directly
    presenter._on_load_history()

    # 3. Assert the Presenter caught it and read the history through the port.
    # `EPIC-025` PR 1.1 — the same guarantee, one level more specific: the old
    # assertion proved *a* dispatch happened and that its type was the klines
    # query; this proves the screen asked for the symbol it is showing.
    history = presenter._stream_controller._historical_klines
    assert history.was_read_for("ETHUSDT")


class _AStoreThatCannotBeRead(IHistoricalKlines):
    """An `IHistoricalKlines` whose reads raise, for the fallback tests.

    A whole implementation rather than a patched method, and it inherits the
    port so the day `IHistoricalKlines` gains a member this class fails to
    instantiate — which is the reminder `Mock(spec=...)` cannot give
    (`test_no_foreign_port_is_mocked.py` is the rule; this is the shape that
    obeys it while still failing on purpose).
    """

    _MESSAGE = "Engine died"

    def load(self, *_args, **_kwargs):
        raise RuntimeError(self._MESSAGE)

    def load_many(self, *_args, **_kwargs):
        raise RuntimeError(self._MESSAGE)


def test_dashboard_integration_exception_fallback(qapp, mock_app):
    mock_app.resolve.return_value = mock_app
    view = DashboardView()
    presenter = DashboardPresenter(view, mock_app.container)
    view.presenter = presenter

    # Force an exception inside the slot logic. `EPIC-025` PR 1.1a — on the
    # port, because that is what `_run_load_history` reaches first; a
    # dispatcher that raises is no longer reached before the read. Given as a
    # real `IHistoricalKlines` whose every method raises, rather than a
    # function patched onto the verified fake: a fake with one method
    # replaced is neither the fake nor the failure, and the next reader
    # cannot tell which promises still hold.
    presenter._stream_controller._historical_klines = _AStoreThatCannotBeRead()
    mock_app.dispatch.side_effect = RuntimeError("Engine died")

    # Track logs
    logs = []
    presenter.ui_log_signal.connect(lambda msg: logs.append(msg))

    # BOT-034 auto-started Start Live on construction; BOT-062 later
    # changed DEV_BOARD_AUTOSTART_ENABLED's default to False (opening the
    # Dev Board must not silently start a live connection unless the user
    # opted in), and this fixture's mock_config.get() always returns
    # whatever default the caller passed, so it now takes that off switch.
    # Construction therefore leaves the FSM at IDLE — not this test's
    # concern (it's about _on_load_history's exception handling, not FSM
    # state) — just documenting why this isn't LIVE the way it used to be.
    assert presenter.fsm.current_state == UIMode.IDLE

    # Emit load history, which will hit the exception in mock_app.dispatch
    presenter._on_load_history()

    # The @safe_ui_action should catch it and log it
    assert any("Engine died" in log for log in logs)

    # _on_load_history never locks the FSM (only _on_start_stream does), so
    # an exception here must leave it exactly where it started (IDLE) — not
    # stuck mid-load in some other state.
    assert presenter.fsm.current_state == UIMode.IDLE
