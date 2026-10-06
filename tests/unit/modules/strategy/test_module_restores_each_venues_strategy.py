"""`BOT-166` — a start arms nothing: each enabled venue's saved strategy stays
saved, for the Bots mode to show as not armed (it superseded `EPIC-028C`/
`028L`'s boot-time re-arm).

@details Driven through `StrategyModule.boot()` itself, so putting an arm back
into it fails here (`CS-002`: a test that built its own arming service could
not tell). `ICommandDispatcher` is a `core/` port: the recording double below
keeps every command it is asked to dispatch, and the claim is that boot asks
for none. The composed-app proof, with the UI and the tick path, is
`tests/integration/presentation/ui/test_saved_strategy_restores_disarmed.py`.
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


def test_boot_arms_no_enabled_venues_saved_strategy() -> None:
    config = DictConfig()
    store = in_memory_config_store(config)
    store.save(_FUTURES, _FUTURES_CONFIG)
    store.save(_SPOT, _SPOT_CONFIG)

    dispatcher = _boot(config, _FUTURES, _SPOT)

    assert dispatcher.armed == []


def test_boot_keeps_what_was_saved_for_the_user_to_arm() -> None:
    config = DictConfig()
    store = in_memory_config_store(config)
    store.save(_FUTURES, _FUTURES_CONFIG)
    store.save(_SPOT, _SPOT_CONFIG)

    _boot(config, _FUTURES, _SPOT)

    assert store.load(_FUTURES) == _FUTURES_CONFIG
    assert store.load(_SPOT) == _SPOT_CONFIG


def test_a_single_venue_apps_legacy_keys_still_move_to_that_venue() -> None:
    """Adopting the unscoped keys is bookkeeping, not arming: the selection
    comes back on its venue, and still nothing is armed."""
    config = DictConfig(
        {
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value: "ema_crossover",
            ConfigKeys.TRADING_LIVE_SYMBOL.value: "BTCUSDT",
            ConfigKeys.TRADING_LIVE_INTERVAL.value: "5m",
            ConfigKeys.TRADING_LIVE_LEVERAGE.value: 3.0,
        }
    )

    dispatcher = _boot(config, _FUTURES)

    assert dispatcher.armed == []
    moved = in_memory_config_store(config).load(_FUTURES)
    assert (moved.strategy_key, moved.symbol, moved.interval) == (
        "ema_crossover",
        "BTCUSDT",
        "5m",
    )


def test_with_two_venues_enabled_a_legacy_strategy_is_not_guessed_onto_one() -> None:
    config = DictConfig(
        {
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value: "ema_crossover",
            ConfigKeys.TRADING_LIVE_SYMBOL.value: "BTCUSDT",
            ConfigKeys.TRADING_LIVE_INTERVAL.value: "5m",
        }
    )

    _boot(config, _FUTURES, _SPOT)

    assert in_memory_config_store(config).load(_FUTURES).strategy_key == ""
    assert in_memory_config_store(config).load(_SPOT).strategy_key == ""
