"""`EPIC-028C` — at boot, each enabled venue re-arms its own saved strategy.

@details Driven through `StrategyModule.boot()` itself, so removing the
per-venue restore from it fails here (`CS-002`: a test that built its own
arming service could not tell). `ICommandDispatcher` is a `core/` port: the
recording double below answers every arm with success and keeps the command,
which carries both the configuration and the venue it was addressed to.
"""

from __future__ import annotations

from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_config_store import (
    LiveStrategyConfigStore,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyCommand,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.module import StrategyModule
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET

_FUTURES_CONFIG = LiveStrategyConfig(
    strategy_key="ema_crossover", symbol="BTCUSDT", interval="5m", leverage=3.0
)
_SPOT_CONFIG = LiveStrategyConfig(
    strategy_key="rsi_reversion", symbol="ETHUSDT", interval="1h"
)


class _RecordingDispatcher(ICommandDispatcher):
    def __init__(self) -> None:
        self.armed: list[ArmStrategyCommand] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert isinstance(input_dto, ArmStrategyCommand)
        self.armed.append(input_dto)
        return ArmStrategyResult(armed=True)


def _boot(config: DictConfig, *venues: TradingVenue) -> _RecordingDispatcher:
    dispatcher = _RecordingDispatcher()
    container = StdLibContainer()
    container.singleton(IConfig, config)
    container.singleton(ICommandDispatcher, dispatcher)
    container.singleton(TradingVenue, venues[0])
    container.singleton(
        IVenueContexts,
        FakeVenueContexts(*(fake_venue_context(venue) for venue in venues)),
    )
    container.singleton(VenueStrategySessions, VenueStrategySessions(lambda _v: None))
    StrategyModule().boot(
        SimpleNamespace(container=container, event_bus=MemoryEventBus())
    )
    return dispatcher


def _armed(dispatcher: _RecordingDispatcher) -> dict[TradingVenue, LiveStrategyConfig]:
    return {command.venue: command.config for command in dispatcher.armed}


def test_each_enabled_venue_rearms_its_own_saved_strategy() -> None:
    config = DictConfig()
    store = LiveStrategyConfigStore(config)
    store.save(_FUTURES, _FUTURES_CONFIG)
    store.save(_SPOT, _SPOT_CONFIG)

    dispatcher = _boot(config, _FUTURES, _SPOT)

    assert _armed(dispatcher) == {_FUTURES: _FUTURES_CONFIG, _SPOT: _SPOT_CONFIG}


def test_a_disabled_venue_is_not_rearmed() -> None:
    """Spot was unticked in Settings: its saved strategy stays saved and
    Futures comes back alone."""
    config = DictConfig()
    store = LiveStrategyConfigStore(config)
    store.save(_FUTURES, _FUTURES_CONFIG)
    store.save(_SPOT, _SPOT_CONFIG)

    dispatcher = _boot(config, _FUTURES)

    assert _armed(dispatcher) == {_FUTURES: _FUTURES_CONFIG}


def test_a_single_venue_apps_strategy_comes_back_on_the_primary_venue_only() -> None:
    """The unscoped keys an older version saved belong to the venue it ran
    on, the primary one; the second venue has nothing to restore."""
    config = DictConfig(
        {
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value: "ema_crossover",
            ConfigKeys.TRADING_LIVE_SYMBOL.value: "BTCUSDT",
            ConfigKeys.TRADING_LIVE_INTERVAL.value: "5m",
            ConfigKeys.TRADING_LIVE_LEVERAGE.value: 3.0,
        }
    )

    dispatcher = _boot(config, _FUTURES, _SPOT)

    assert list(_armed(dispatcher)) == [_FUTURES]
    assert _armed(dispatcher)[_FUTURES].strategy_key == "ema_crossover"
