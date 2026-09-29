"""`ITradingClientFactory`'s venue-branching bind (`EPIC-027K`), locked
against a real container — the same doctrine
`test_module_metadata_provider_binding.py`/`test_module_account_reader_binding.py`
already established for their own venue-branched ports
(`architecture-rule.md` §7.3: a docstring is not what breaks when reality
changes, a test is).

Distinct from `test_module_trading_client_per_venue.py`: that file locks
which venue may get a trading client at all (none while
`TradingVenue.DISABLED`). This file locks the always-constructible
`ITradingClientFactory` itself — built for every venue context, whether or
not trading is enabled.

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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client_factory import (
    SpotTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
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
    # `EPIC-028B` — the venue's whole context is built together, its
    # user-data stream included; the task manager is only stored.
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)
    return container


def test_factory_is_futures_by_default():
    """No config value at all — the same shape a fresh install boots
    with. Registered unconditionally, unlike `ITradingClient` itself, so
    this must resolve even though trading is not enabled."""
    container = _container_with_venue(None)

    factory = container.resolve(IVenueContexts).primary().client_factory

    assert isinstance(factory, FuturesTradingClientFactory)


def test_factory_is_futures_when_venue_is_explicitly_disabled():
    container = _container_with_venue(TradingVenue.DISABLED)

    factory = container.resolve(IVenueContexts).primary().client_factory

    assert isinstance(factory, FuturesTradingClientFactory)


def test_factory_is_spot_when_venue_is_spot_testnet():
    """`EPIC-027K` — before this bind existed, every venue silently
    resolved `FuturesTradingClientFactory`, which would sign a Spot Testnet
    request with Futures-only fields (`positionSide`/`reduceOnly`)."""
    container = _container_with_venue(TradingVenue.SPOT_TESTNET)

    factory = container.resolve(IVenueContexts).primary().client_factory

    assert isinstance(factory, SpotTradingClientFactory)


def test_spot_factory_produces_a_spot_trading_client():
    """The factory's own job, not just its type: `create()` must hand back
    an actual `SpotTradingClient`, the concrete adapter this task built."""
    container = _container_with_venue(TradingVenue.SPOT_TESTNET)
    factory = container.resolve(IVenueContexts).primary().client_factory

    client = factory.create(OrderSubmissionMode.VALIDATE_ONLY)

    assert isinstance(client, SpotTradingClient)
