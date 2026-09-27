"""`IUserDataStream`'s venue-branching bind (`EPIC-027L`), locked against a
real container — the same doctrine `test_module_account_reader_binding.py`/
`test_module_trading_client_factory_binding.py` already established for
their own venue-branched ports (`architecture-rule.md` §7.3: a docstring is
not what breaks when reality changes, a test is).

Before this bind branched, every venue silently resolved
`FuturesUserDataStream` — for `SPOT_TESTNET` that would have opened
`bsm.futures_user_socket()` against Spot Testnet credentials instead of the
real `bsm.user_socket()` Spot entry point, the same class of regression
`test_module_account_reader_binding.py`/`test_module_trading_client_factory_binding.py`
each guard against for their own port.

Real components throughout (`test_no_foreign_port_is_mocked.py`'s own
doctrine): `StdLibContainer` is the Engine's real `IContainer`, `DictConfig`
its real in-memory `IConfig`, `MemoryEventBus` its real in-memory
`IEventBus`, and `bind_adapters()`/`bind_state()` are the same production
wiring `TradingModule.register()` calls. `ITaskManager` is a `Mock()`: an
Engine interface (`test_no_foreign_port_is_mocked.py`'s own exemption list),
never invoked here since `IUserDataStream` construction only stores it —
`.spawn()` is called from `.start()`, which this test never calls.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
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


def _container_with_venue(venue: TradingVenue | None) -> StdLibContainer:
    container = StdLibContainer()
    config = (
        DictConfig()
        if venue is None
        else DictConfig({ConfigKeys.EXCHANGE_TRADING_VENUE.value: venue.value})
    )
    container.singleton(IConfig, config)
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)
    # `FuturesUserDataStream` depends on `TradingSessionState`
    # (`bind_state()`'s own binding) — `SpotUserDataStream` does not, but
    # binding it unconditionally here matches `TradingModule.register()`'s
    # own call order and keeps every venue branch resolvable from the same
    # container.
    bind_state(container)
    return container


def test_user_data_stream_is_futures_by_default():
    """No config value at all — the same shape a fresh install boots
    with. Registered unconditionally (like `ITradingAccountReader`/
    `ITradingClientFactory` above it in the same file), so this must
    resolve even though trading is not enabled."""
    container = _container_with_venue(None)

    stream = container.resolve(IUserDataStream)

    assert isinstance(stream, FuturesUserDataStream)


def test_user_data_stream_is_futures_when_venue_is_explicitly_disabled():
    container = _container_with_venue(TradingVenue.DISABLED)

    stream = container.resolve(IUserDataStream)

    assert isinstance(stream, FuturesUserDataStream)


def test_user_data_stream_is_futures_when_venue_is_futures_testnet():
    container = _container_with_venue(TradingVenue.FUTURES_TESTNET)

    stream = container.resolve(IUserDataStream)

    assert isinstance(stream, FuturesUserDataStream)


def test_user_data_stream_is_spot_when_venue_is_spot_testnet():
    """`EPIC-027L` — before this bind existed, `SPOT_TESTNET` silently
    resolved `FuturesUserDataStream`, which would have opened Futures'
    `bsm.futures_user_socket()` against Spot Testnet credentials instead of
    the real Spot entry point (`bsm.user_socket()`)."""
    container = _container_with_venue(TradingVenue.SPOT_TESTNET)

    stream = container.resolve(IUserDataStream)

    assert isinstance(stream, SpotUserDataStream)
