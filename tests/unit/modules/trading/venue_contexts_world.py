"""The trading module registered on the Engine's real container, for the venue-contexts tests.

@details The same `bind_adapters()`/`bind_state()` `TradingModule.register()`
calls, with a `DictConfig`, a `MemoryEventBus`, an `ITaskManager` `Mock()` (an
Engine interface, only stored) and an unguarded `IInstanceAccess` (`EPIC-035H`:
a test run holds no data root against another copy of the app).
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.infrastructure.instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager

BOTH = [TradingVenue.FUTURES_TESTNET.value, TradingVenue.SPOT_TESTNET.value]


def container_of(values: dict[str, object]) -> StdLibContainer:
    container = StdLibContainer()
    container.singleton(IInstanceAccess, InstanceAccess.unguarded())
    container.singleton(IConfig, DictConfig(values))
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)
    bind_state(container)
    return container


def both_venues() -> StdLibContainer:
    return container_of({ConfigKeys.EXCHANGE_TRADING_VENUES.value: BOTH})
