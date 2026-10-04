"""`EPIC-028C`/`028L` — at boot, each enabled venue re-arms its own saved
strategy (`EPIC-028L` widened this from the primary venue once each venue had
a desk that shows and stops it).

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
from Sagittarius_Elite_Warrior.tests.unit.modules.strategy.live_config_ports import (
    bind_config_ports,
    in_memory_config_store,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET

_FUTURES_CONFIG = LiveStrategyConfig(
    strategy_key="ema_crossover", symbol="BTCUSDT", interval="5m", leverage=3.0
)
_SPOT_CONFIG = LiveStrategyConfig(
    strategy_key="rsi_reversion", symbol="ETHUSDT", interval="1h"
)


class _RecordingDispatcher(ICommandDispatcher):
    """Answers every arm with success, except for `refused`'s, which it
    refuses the way `ArmStrategyCommandHandler` refuses a config that no
    longer validates."""

    def __init__(self, refused: TradingVenue | None = None) -> None:
        self.armed: list[ArmStrategyCommand] = []
        self.accepted: list[TradingVenue] = []
        self._refused = refused

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert isinstance(input_dto, ArmStrategyCommand)
        self.armed.append(input_dto)
        if input_dto.venue is self._refused:
            return ArmStrategyResult(armed=False, error_message="no longer valid")
        self.accepted.append(input_dto.venue)
        return ArmStrategyResult(armed=True)


def _boot(config: DictConfig, *venues: TradingVenue) -> _RecordingDispatcher:
    return _boot_with(_RecordingDispatcher(), config, venues)


def _boot_refusing(
    config: DictConfig, refused: TradingVenue, *venues: TradingVenue
) -> _RecordingDispatcher:
    return _boot_with(_RecordingDispatcher(refused), config, venues)


def _boot_with(
    dispatcher: _RecordingDispatcher,
    config: DictConfig,
    venues: tuple[TradingVenue, ...],
) -> _RecordingDispatcher:
    container = StdLibContainer()
    bind_config_ports(container, config)
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
    """Both venues saved a strategy and both have a desk (`EPIC-028L`): each
    comes back armed with its own, addressed to its own venue — Spot's never
    lands on Futures, nor the other way round."""
    config = DictConfig()
    store = in_memory_config_store(config)
    store.save(_FUTURES, _FUTURES_CONFIG)
    store.save(_SPOT, _SPOT_CONFIG)

    dispatcher = _boot(config, _FUTURES, _SPOT)

    assert _armed(dispatcher) == {_FUTURES: _FUTURES_CONFIG, _SPOT: _SPOT_CONFIG}


def test_one_venues_bad_saved_config_leaves_the_other_venue_armed() -> None:
    """A strategy Spot saved that no longer validates is logged and left
    disarmed; it must not keep Futures from coming back."""
    config = DictConfig()
    store = in_memory_config_store(config)
    store.save(_FUTURES, _FUTURES_CONFIG)
    store.save(_SPOT, _SPOT_CONFIG)
    dispatcher = _boot_refusing(config, _SPOT, _FUTURES, _SPOT)

    assert _armed(dispatcher) == {_FUTURES: _FUTURES_CONFIG, _SPOT: _SPOT_CONFIG}
    assert dispatcher.accepted == [_FUTURES]


def test_a_spot_only_app_rearms_spots_own_strategy() -> None:
    config = DictConfig()
    store = in_memory_config_store(config)
    store.save(_FUTURES, _FUTURES_CONFIG)
    store.save(_SPOT, _SPOT_CONFIG)

    dispatcher = _boot(config, _SPOT)

    assert _armed(dispatcher) == {_SPOT: _SPOT_CONFIG}


def test_a_single_venue_apps_strategy_comes_back_on_that_venue() -> None:
    """The unscoped keys an older version saved belong to the one venue it
    ran on."""
    config = DictConfig(
        {
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value: "ema_crossover",
            ConfigKeys.TRADING_LIVE_SYMBOL.value: "BTCUSDT",
            ConfigKeys.TRADING_LIVE_INTERVAL.value: "5m",
            ConfigKeys.TRADING_LIVE_LEVERAGE.value: 3.0,
        }
    )

    dispatcher = _boot(config, _FUTURES)

    assert list(_armed(dispatcher)) == [_FUTURES]
    assert _armed(dispatcher)[_FUTURES].strategy_key == "ema_crossover"


def test_with_two_venues_enabled_a_legacy_strategy_is_not_guessed_onto_one() -> None:
    config = DictConfig(
        {
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value: "ema_crossover",
            ConfigKeys.TRADING_LIVE_SYMBOL.value: "BTCUSDT",
            ConfigKeys.TRADING_LIVE_INTERVAL.value: "5m",
        }
    )

    dispatcher = _boot(config, _FUTURES, _SPOT)

    assert dispatcher.armed == []
