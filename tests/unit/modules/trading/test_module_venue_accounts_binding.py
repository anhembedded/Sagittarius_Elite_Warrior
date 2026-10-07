"""`EPIC-034D` — `IVenueAccounts` against the real production wiring.

The Engine's real container and the same `bind_*` calls `TradingModule`
makes: one reader per enabled venue, each reading its own venue's ports, and
no reader for a venue the configuration does not enable.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.port_bindings import (
    bind_published_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
    UnknownAccountSourceError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
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


def _accounts(*venues: TradingVenue) -> IVenueAccounts:
    container = StdLibContainer()
    container.singleton(
        IConfig,
        DictConfig(
            {ConfigKeys.EXCHANGE_TRADING_VENUES.value: [v.value for v in venues]}
        ),
    )
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    container.singleton(ICommandDispatcher, Mock(spec=ICommandDispatcher))
    bind_adapters(container)
    bind_state(container)
    bind_published_ports(container)
    return container.resolve(IVenueAccounts)


def test_every_enabled_venue_is_a_source_in_configuration_order() -> None:
    accounts = _accounts(TradingVenue.SPOT_TESTNET, TradingVenue.FUTURES_TESTNET)

    assert accounts.sources() == (
        AccountSource.SPOT_TESTNET,
        AccountSource.FUTURES_TESTNET,
    )


def test_a_reader_reads_its_own_source_and_is_the_same_instance() -> None:
    accounts = _accounts(TradingVenue.SPOT_TESTNET)

    reader = accounts.reader(AccountSource.SPOT_TESTNET)

    assert reader.source is AccountSource.SPOT_TESTNET
    assert accounts.reader(AccountSource.SPOT_TESTNET) is reader


def test_a_source_that_is_not_enabled_has_no_reader() -> None:
    accounts = _accounts(TradingVenue.SPOT_TESTNET)

    with pytest.raises(UnknownAccountSourceError):
        accounts.reader(AccountSource.FUTURES_TESTNET)
