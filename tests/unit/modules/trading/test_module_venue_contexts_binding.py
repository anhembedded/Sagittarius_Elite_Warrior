"""`EPIC-028A` — `IVenueContexts` against the real production wiring.

@details Same doctrine as `test_module_user_data_stream_binding.py`: the
Engine's real `StdLibContainer`, `DictConfig` and `MemoryEventBus`, the same
`bind_adapters()`/`bind_state()` `TradingModule.register()` calls, and an
`ITaskManager` `Mock()` (an Engine interface, only stored — nothing here
calls `.start()`).

Locks what ADR D2/D4 promise: two venues live at once, each with its own
adapters, its own metadata cache and its own session state; one instance
per venue whichever door a caller comes in by; and, since `EPIC-028B`, no
per-venue port bound on its own, so no caller can reach one without naming
its venue.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_commission_rate_reader import (
    FuturesCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_commission_rate_reader import (
    SpotCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_reader import (
    SpotHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client_factory import (
    SpotTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_contexts import (
    VenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_symbol_order_metadata_cache import (
    ISymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.exceptions import DependencyResolutionError
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager

_BOTH = [TradingVenue.FUTURES_TESTNET.value, TradingVenue.SPOT_TESTNET.value]


def _container(values: dict[str, object]) -> StdLibContainer:
    container = StdLibContainer()
    container.singleton(IConfig, DictConfig(values))
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)
    bind_state(container)
    return container


def _both_venues() -> StdLibContainer:
    return _container({ConfigKeys.EXCHANGE_TRADING_VENUES.value: _BOTH})


def test_both_venues_are_enabled_in_configuration_order() -> None:
    contexts = _both_venues().resolve(IVenueContexts)

    assert contexts.enabled() == (
        TradingVenue.FUTURES_TESTNET,
        TradingVenue.SPOT_TESTNET,
    )


def test_each_venue_gets_its_own_venue_shaped_adapters() -> None:
    contexts = _both_venues().resolve(IVenueContexts)

    futures = contexts.get(TradingVenue.FUTURES_TESTNET)
    spot = contexts.get(TradingVenue.SPOT_TESTNET)

    assert futures.venue is TradingVenue.FUTURES_TESTNET
    assert isinstance(futures.metadata_provider, FuturesMetadataProvider)
    assert isinstance(futures.client_factory, FuturesTradingClientFactory)
    assert isinstance(futures.account_reader, FuturesAccountReader)
    assert isinstance(futures.user_data_stream, FuturesUserDataStream)
    assert isinstance(futures.history_reader, FuturesHistoryReader)
    assert isinstance(futures.commission_reader, FuturesCommissionRateReader)
    assert isinstance(futures.account_control, FuturesAccountControl)
    assert spot.venue is TradingVenue.SPOT_TESTNET
    assert isinstance(spot.metadata_provider, SpotMetadataProvider)
    assert isinstance(spot.client_factory, SpotTradingClientFactory)
    assert isinstance(spot.account_reader, SpotAccountReader)
    assert isinstance(spot.user_data_stream, SpotUserDataStream)
    assert isinstance(spot.history_reader, SpotHistoryReader)
    assert isinstance(spot.commission_reader, SpotCommissionRateReader)
    # `EPIC-028F` — Spot has no leverage or margin mode, so no control.
    assert spot.account_control is None


def test_venues_share_no_credentials_and_no_metadata_cache() -> None:
    """A Futures `BTCUSDT` and a Spot `BTCUSDT` have different rounding
    rules; one shared cache would hand one venue the other's lot size."""
    contexts = _both_venues().resolve(IVenueContexts)

    futures = contexts.get(TradingVenue.FUTURES_TESTNET)
    spot = contexts.get(TradingVenue.SPOT_TESTNET)

    assert futures.metadata_cache is not spot.metadata_cache
    assert futures.credentials_provider is not spot.credentials_provider


def test_a_venue_context_is_one_instance_per_venue() -> None:
    contexts = _both_venues().resolve(IVenueContexts)

    first = contexts.get(TradingVenue.SPOT_TESTNET)

    assert contexts.get(TradingVenue.SPOT_TESTNET) is first
    assert _both_venues().resolve(IVenueContexts) is not contexts


def test_a_venue_that_is_not_enabled_raises() -> None:
    contexts = _container(
        {ConfigKeys.EXCHANGE_TRADING_VENUES.value: ["futures_testnet"]}
    ).resolve(IVenueContexts)

    with pytest.raises(VenueNotEnabledError, match="spot_testnet"):
        contexts.get(TradingVenue.SPOT_TESTNET)


def test_disabled_is_served_only_while_it_is_the_primary_venue() -> None:
    """`EPIC-028B`: with nothing enabled, a command addressed to the
    process's own read-only venue still gets that venue's adapters (its
    handler refuses it itself). Once a real venue is enabled, `DISABLED` is
    not a venue anything may address."""
    nothing_enabled = _container({}).resolve(IVenueContexts)
    one_enabled = _container(
        {ConfigKeys.EXCHANGE_TRADING_VENUES.value: ["futures_testnet"]}
    ).resolve(IVenueContexts)

    assert nothing_enabled.enabled() == ()
    assert nothing_enabled.get(TradingVenue.DISABLED) is nothing_enabled.primary()
    with pytest.raises(VenueNotEnabledError):
        one_enabled.get(TradingVenue.DISABLED)


def test_with_nothing_enabled_primary_is_the_read_only_futures_shape() -> None:
    """The process has always bound Futures-shaped adapters while trading
    is off; `primary()` keeps that, so nothing that resolves a single-venue
    port at boot starts failing."""
    container = _container({})

    primary = container.resolve(IVenueContexts).primary()

    assert primary.venue is TradingVenue.DISABLED
    assert isinstance(primary.metadata_provider, FuturesMetadataProvider)
    assert container.resolve(TradingVenue) is TradingVenue.DISABLED


def test_primary_is_the_first_enabled_venue() -> None:
    container = _container(
        {ConfigKeys.EXCHANGE_TRADING_VENUES.value: ["spot_testnet", "futures_testnet"]}
    )

    contexts = container.resolve(IVenueContexts)

    assert contexts.primary() is contexts.get(TradingVenue.SPOT_TESTNET)
    assert container.resolve(TradingVenue) is TradingVenue.SPOT_TESTNET


@pytest.mark.parametrize(
    "port",
    [
        IExchangeCredentialsProvider,
        ISymbolOrderMetadataCache,
        IMarketMetadataProvider,
        ITradingClientFactory,
        ITradingAccountReader,
        IUserDataStream,
    ],
)
def test_no_per_venue_port_is_bound_on_its_own(port: type) -> None:
    """`EPIC-028B` AC5 — the single-venue doors are gone. A caller that
    resolved one of these would silently act on whichever venue is primary,
    so resolving one must fail, and the caller must name its venue."""
    container = _both_venues()

    with pytest.raises(DependencyResolutionError):
        container.resolve(port)


def test_session_state_and_equity_recorder_are_owned_per_venue() -> None:
    container = _both_venues()
    venues = container.resolve(VenueContexts)
    futures = venues.assembly(TradingVenue.FUTURES_TESTNET)
    spot = venues.assembly(TradingVenue.SPOT_TESTNET)

    scopes = container.resolve(VenueTradingScopes)

    assert futures.session_state is not spot.session_state
    assert futures.equity_recorder is not spot.equity_recorder
    # `EPIC-028B` — the state a venue's user data stream writes is the state
    # every handler acting on that venue reads, one object per venue.
    assert scopes.get(TradingVenue.FUTURES_TESTNET).session_state is (
        futures.session_state
    )
    assert scopes.get(TradingVenue.SPOT_TESTNET).session_state is spot.session_state
    assert scopes.get(TradingVenue.SPOT_TESTNET).equity_recorder is (
        spot.equity_recorder
    )
