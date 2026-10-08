"""`ITradingAccountReader`'s venue-branching bind (`EPIC-027H`), locked
against a real container — the same doctrine `test_module_trading_client_per_venue.py`
keeps for `ITradingClient`: a docstring is not what breaks
when reality changes, a test is (`architecture-rule.md` §7.3).

Real components throughout (`test_no_foreign_port_is_mocked.py`'s own
doctrine): `StdLibContainer` is the Engine's real `IContainer`, `DictConfig`
its real in-memory `IConfig`, and `bind_adapters()` is the same production
wiring `TradingModule.register()` calls.

`EPIC-028B` — the single-venue binding is gone. The port is read from the
primary venue's `VenueContext` (`IVenueContexts.primary()`), which the
legacy scalar `exchange.trading_venue` still selects; the venue shape each
configuration gets is what stays locked.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
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
    container.singleton(IInstanceAccess, InstanceAccess.unguarded())
    config = (
        DictConfig()
        if venue is None
        else DictConfig({ConfigKeys.EXCHANGE_TRADING_VENUE.value: venue.value})
    )
    container.singleton(IConfig, config)
    # `EPIC-028B` — the venue's whole context is built together, its
    # user-data stream included; the task manager is only stored.
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)
    return container


def test_account_reader_is_futures_by_default():
    """No config value at all — the same shape a fresh install boots
    with. Unconditional bind (`ITradingAccountReader` is read-only and does
    not require trading to be "enabled"), so this must still resolve."""
    container = _container_with_venue(None)

    reader = container.resolve(IVenueContexts).primary().account_reader

    assert isinstance(reader, FuturesAccountReader)


def test_account_reader_is_futures_when_venue_is_explicitly_disabled():
    container = _container_with_venue(TradingVenue.DISABLED)

    reader = container.resolve(IVenueContexts).primary().account_reader

    assert isinstance(reader, FuturesAccountReader)


def test_account_reader_is_futures_when_venue_is_futures_testnet():
    container = _container_with_venue(TradingVenue.FUTURES_TESTNET)

    reader = container.resolve(IVenueContexts).primary().account_reader

    assert isinstance(reader, FuturesAccountReader)


def test_account_reader_is_spot_when_venue_is_spot_testnet():
    """`EPIC-027H` — before this bind existed, every venue silently
    resolved `FuturesAccountReader`, which would have signed a Futures
    Testnet request with Spot Testnet credentials for `SPOT_TESTNET`."""
    container = _container_with_venue(None)

    reader = (
        container.resolve(IVenueContexts).get(TradingVenue.SPOT_TESTNET).account_reader
    )

    assert isinstance(reader, SpotAccountReader)
