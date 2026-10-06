"""`market_dependencies_for` (`EPIC-033Q`): the production wiring of the
Market mode's ports, built from a container as `build_market_presenter`
builds it. The presenter tests construct `MarketDependencies` by hand, so
this is the one place a feed bound to the wrong market, or a lost UI state
coordinator, turns a test red (the review of PR #359)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_dependencies import (
    MARKETS,
    market_dependencies_for,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from Sagittarius_Elite_Warrior.tests.conftest import fake_container
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.market.market_fixtures import (
    QueuedThreads,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


def _container(
    history: FakeHistoricalKlines, stream: FakeMarketStream, extra: dict | None = None
):
    bindings = {
        IConfig: DictConfig({}),
        IMarketStream: stream,
        IMarketDataSync: FakeMarketDataSync(),
        IHistoricalKlines: history,
        IThreadManager: QueuedThreads(),
        IndicatorScriptRegistry: IndicatorScriptRegistry(),
        IAccountSnapshot: FakeAccountSnapshot(),
        **(extra or {}),
    }
    container = fake_container(bindings)
    container.registrations.return_value = dict.fromkeys(bindings)
    return container


def test_each_market_gets_a_feed_of_that_market(qapp):
    history = FakeHistoricalKlines()
    stream = FakeMarketStream()
    dependencies = market_dependencies_for(_container(history, stream))

    for market in MARKETS:
        feed = dependencies.candles[market]
        feed.load_history("BTCUSDT", TimeFrame.ONE_MINUTE, 10)
        feed.start_stream(f"probe.{market.value}", "BTCUSDT", TimeFrame.ONE_MINUTE)
        held = stream.held_by(f"probe.{market.value}")

        assert history.reads[-1].market is market
        assert held is not None
        assert held.market_type is market
    assert set(dependencies.candles) == {MarketType.SPOT, MarketType.FUTURES_USD_M}


def test_the_registered_ui_state_coordinator_remembers_the_choice(qapp):
    coordinator = UiStateCoordinator(InMemoryStateStore())

    dependencies = market_dependencies_for(
        _container(
            FakeHistoricalKlines(),
            FakeMarketStream(),
            {UiStateCoordinator: coordinator},
        )
    )

    assert dependencies.state is coordinator


def test_without_a_coordinator_the_choice_is_not_remembered(qapp):
    dependencies = market_dependencies_for(
        _container(FakeHistoricalKlines(), FakeMarketStream())
    )

    assert dependencies.state is None


def test_the_parameters_command_saves_where_the_charts_read(qapp):
    """Tools → Indicator parameters… saves through `params_store`; the
    charts read `script_params`. They must be the one store, or an edit
    never reaches a chart (`BOT-063`, moved from the Dev Board)."""
    dependencies = market_dependencies_for(
        _container(FakeHistoricalKlines(), FakeMarketStream())
    )

    assert dependencies.params_store is not None
    dependencies.params_store.save("ema_20", {"period": 5})

    assert dependencies.script_params("ema_20") == {"period": 5}
