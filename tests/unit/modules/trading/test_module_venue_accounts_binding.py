"""`EPIC-034D` — `IVenueAccounts` against the real production wiring.

The Engine's real container and the same `bind_*` calls `TradingModule`
makes: one reader per enabled venue, each reading its own venue's ports, and
no reader for a venue the configuration does not enable.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
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
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_accounts import (
    VenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
    UnknownAccountSourceError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_accounts import (
    FakeVenueAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
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


def _accounts() -> IVenueAccounts:
    """The production wiring; every venue is assembled whatever the config says
    (`EPIC-034B`), so there is nothing to enable."""
    container = StdLibContainer()
    container.singleton(IConfig, DictConfig({}))
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    container.singleton(ICommandDispatcher, Mock(spec=ICommandDispatcher))
    bind_adapters(container)
    bind_state(container)
    bind_published_ports(container)
    return container.resolve(IVenueAccounts)


def test_every_venue_is_a_source_then_the_mainnet_one() -> None:
    accounts = _accounts()

    assert accounts.sources() == (
        AccountSource.FUTURES_TESTNET,
        AccountSource.SPOT_TESTNET,
        AccountSource.SPOT_MAINNET_READONLY,
    )


@pytest.mark.parametrize("source", list(AccountSource))
def test_each_source_has_its_own_reader_and_the_same_instance_every_time(
    source: AccountSource,
) -> None:
    accounts = _accounts()

    reader = accounts.reader(source)

    assert reader.source is source
    assert accounts.reader(source) is reader


def test_the_readers_are_distinct() -> None:
    accounts = _accounts()

    readers = [accounts.reader(source) for source in accounts.sources()]

    assert len({id(reader) for reader in readers}) == len(readers)


def test_the_mainnet_reader_is_not_a_venues_reader() -> None:
    accounts = _accounts()

    mainnet = accounts.reader(AccountSource.SPOT_MAINNET_READONLY)

    assert mainnet.source.trading_venue is None


def test_a_source_the_configuration_does_not_enable_has_no_reader() -> None:
    """A testnet venue left out of `IVenueContexts` is no source: asking for it
    is an error, not a reader that fails on every read."""
    mainnet = FakeVenueAccountReader(
        AccountSource.SPOT_MAINNET_READONLY,
        ConnectFailure(
            AccountSource.SPOT_MAINNET_READONLY, ConnectionFailureKind.NOT_CONFIGURED
        ),
    )
    accounts = VenueAccounts(
        FakeVenueContexts(fake_venue_context(TradingVenue.FUTURES_TESTNET)), mainnet
    )

    assert accounts.sources() == (
        AccountSource.FUTURES_TESTNET,
        AccountSource.SPOT_MAINNET_READONLY,
    )
    with pytest.raises(UnknownAccountSourceError):
        accounts.reader(AccountSource.SPOT_TESTNET)
