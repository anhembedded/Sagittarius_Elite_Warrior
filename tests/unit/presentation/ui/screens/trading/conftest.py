"""Shared fixtures for the Trading screen's presenter tests.

`EPIC-022D` added two collaborators every one of those tests now resolves
(`LiveStrategySession`, `StrategyRegistry`), and the three test modules
each had their own hand-rolled `container` fixture. Rather than paste the
same two branches into all three, the pieces that must be REAL objects
live here.

They have to be real, not `MagicMock()`: `StrategyArmingCoordinator` reads
`session.config` and formats it into the card's summary line, and a
`MagicMock` config formats into `<MagicMock id=...>` — a test suite that
green-lights that would be asserting on nonsense.
"""

from __future__ import annotations

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
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_presenter import (
    TradingPresenter,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

#: One real registered strategy is enough for every assertion these tests
#: make, and keeps them independent of how many strategies the app ships.
TEST_STRATEGY_KEY = "ema_crossover"


@pytest.fixture
def strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(TEST_STRATEGY_KEY, EmaCrossoverStrategy)
    return registry


@pytest.fixture
def strategy_session(strategy_registry: StrategyRegistry) -> LiveStrategySession:
    """A real session over a real registry, with only the network-facing
    collaborators mocked — so arming really validates parameters against
    the real strategy."""
    factory = LiveStrategyFactory(
        strategy_registry,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    return LiveStrategySession(factory)


# --------------------------------------------------------------------- #
# Collaborators the three Presenter modules each declared identically
#
# `test-health` C7: the same four fixtures were byte-identical in
# `test_trading_presenter_toggle.py`, `..._emergency_stop.py` and
# `..._equity.py`. Not four opinions about a session state — one, copied
# three times, with nothing keeping the copies in step.
# --------------------------------------------------------------------- #


@pytest.fixture
def trading_session() -> FakeTradingSession:
    """`EPIC-025` PR 1.3c-1 — the screen reads the session through
    `ITradingSession`, so the container hands out that port's verified fake
    instead of the real mutable session service. A test says what the session
    looks like (`set_enabled`, `answer_with`, `enable_answers`) and reads back
    how many times each call was made, instead of asserting that a command was
    dispatched.
    """
    return FakeTradingSession()


@pytest.fixture
def order_submission() -> FakeOrderSubmission:
    """`EPIC-025` PR 1.3c-2 — every order this screen can place or cancel goes
    through `IOrderSubmission`, so the container hands out that port's
    verified fake. It keeps live submissions, dry runs and venue validations
    in three separate lists, which is the one thing a `Mock` cannot do: a
    caller that dropped `live=False` would still look right to a mock."""
    return FakeOrderSubmission()


@pytest.fixture
def equity_recorder() -> EquityCurveRecorder:
    return EquityCurveRecorder()


@pytest.fixture
def mock_thread_manager() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_dispatcher() -> MagicMock:
    return MagicMock()


# --------------------------------------------------------------------- #
# `mock_config`/`container`/`view`/`presenter` — the same construction of
# a full `TradingPresenter` was hand-rolled identically in
# `test_trading_presenter_toggle.py` and `..._emergency_stop.py` (same
# reasoning as the four fixtures above: one opinion, not two copies with
# nothing keeping them in step). `..._equity.py` needs its own `container`
# (it also resolves `IEventBus`) and keeps its local override — a fixture
# defined in a test module always wins over this file's, so nothing here
# changes its behaviour.
# --------------------------------------------------------------------- #


@pytest.fixture
def mock_config() -> MagicMock:
    config = MagicMock()
    config.get_all.return_value = {
        "DEFAULT_SYMBOLS": ["BTCUSDT"],
        "DEFAULT_INTERVAL": "1m",
    }
    config.get.side_effect = lambda key, default=None, cast=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    return config


@pytest.fixture
def market_stream() -> FakeMarketStream:
    """`EPIC-025` PR 1.1b — the chart opens and releases the live stream
    through `IMarketStream`, so the container hands out the port's verified
    fake and a test reads what this screen holds."""
    return FakeMarketStream()


@pytest.fixture
def historical_klines() -> FakeHistoricalKlines:
    return FakeHistoricalKlines()


@pytest.fixture
def market_data_sync() -> FakeMarketDataSync:
    return FakeMarketDataSync()


@pytest.fixture
def container(
    mock_config,
    mock_dispatcher,
    mock_thread_manager,
    trading_session,
    order_submission,
    equity_recorder,
    strategy_session,
    strategy_registry,
    market_stream,
    historical_klines,
    market_data_sync,
    make_container,
):
    # `BOT-125` review — one shared fake, so adding a Presenter dependency
    # stops costing one edit per test module.
    #
    # `EPIC-025` PR 1.1b binds market_data's three published ports to their
    # verified fakes. Unbound interfaces become a `MagicMock`, which for a
    # *foreign port* is the substitution HLD §10.3 rule 4 forbids — and until
    # this, every Presenter test here ran with a mock standing in for the
    # sync and the history read, agreeing with whatever it was asked.
    return make_container(
        {
            IConfig: mock_config,
            IDispatcher: mock_dispatcher,
            IThreadManager: mock_thread_manager,
            ITradingSession: trading_session,
            IOrderSubmission: order_submission,
            EquityCurveRecorder: equity_recorder,
            LiveStrategySession: strategy_session,
            StrategyRegistry: strategy_registry,
            IMarketStream: market_stream,
            IHistoricalKlines: historical_klines,
            IMarketDataSync: market_data_sync,
        }
    )


@pytest.fixture
def view() -> MagicMock:
    return MagicMock()


@pytest.fixture
def presenter(qapp, view, container, mock_thread_manager) -> TradingPresenter:
    """Construction itself submits `ChartCoordinator.start()`'s background
    work (loading history for the default symbol) — reset the mock
    afterward so each test's own `assert_called_once()` on the toggle
    reflects only what that test triggered, same reasoning
    `test_dashboard_presenter.py`'s own `presenter` fixture documents."""
    p = TradingPresenter(view, container)
    mock_thread_manager.submit.reset_mock()
    return p
