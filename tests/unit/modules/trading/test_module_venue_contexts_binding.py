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

from typing import Any, ClassVar
from unittest.mock import Mock

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance import (
    binance_client_builder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.cached_history_reader import (
    CachedAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_book_ticker_reader import (
    FuturesBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_commission_rate_reader import (
    FuturesCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_mark_price_reader import (
    FuturesMarkPriceReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_book_ticker_reader import (
    SpotBookTickerReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    FUTURES_MAINNET_ENV_API_KEY,
    FUTURES_MAINNET_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
    SPOT_MAINNET_ENV_API_KEY,
    SPOT_MAINNET_ENV_API_SECRET,
    EnvFirstCredentialsProvider,
    MainnetCredentialsProvider,
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
        TradingVenue.FUTURES_MAINNET,
        TradingVenue.SPOT_MAINNET,
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
    assert isinstance(futures.history_reader, CachedAccountHistoryReader)
    assert isinstance(futures.history_reader.source, FuturesHistoryReader)
    assert isinstance(futures.commission_reader, FuturesCommissionRateReader)
    assert isinstance(futures.account_control, FuturesAccountControl)
    assert isinstance(futures.book_ticker_reader, FuturesBookTickerReader)
    assert isinstance(futures.mark_price_reader, FuturesMarkPriceReader)
    assert spot.venue is TradingVenue.SPOT_TESTNET
    assert isinstance(spot.metadata_provider, SpotMetadataProvider)
    assert isinstance(spot.client_factory, SpotTradingClientFactory)
    assert isinstance(spot.account_reader, SpotAccountReader)
    assert isinstance(spot.user_data_stream, SpotUserDataStream)
    assert isinstance(spot.history_reader, CachedAccountHistoryReader)
    assert isinstance(spot.history_reader.source, SpotHistoryReader)
    assert isinstance(spot.commission_reader, SpotCommissionRateReader)
    # `EPIC-028F` — Spot has no leverage or margin mode, so no control.
    assert spot.account_control is None
    # `EPIC-028O` — Spot reads its own book, and has no mark price.
    assert isinstance(spot.book_ticker_reader, SpotBookTickerReader)
    assert spot.mark_price_reader is None


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


def test_an_empty_configuration_assembles_every_venue() -> None:
    """`EPIC-034B` — a venue is on because it exists, not because a setting
    names it: the defaults carry no venue and both are assembled."""
    contexts = _container({}).resolve(IVenueContexts)

    assert contexts.enabled() == (
        TradingVenue.FUTURES_TESTNET,
        TradingVenue.SPOT_TESTNET,
        TradingVenue.FUTURES_MAINNET,
        TradingVenue.SPOT_MAINNET,
    )


def test_a_configuration_that_names_one_venue_still_loads_and_changes_nothing() -> None:
    """`EPIC-034B` — a file written before the toggles left still loads; what
    it says about venues is ignored."""
    contexts = _container(
        {ConfigKeys.EXCHANGE_TRADING_VENUES.value: ["futures_testnet"]}
    ).resolve(IVenueContexts)

    assert contexts.get(TradingVenue.SPOT_TESTNET).venue is TradingVenue.SPOT_TESTNET
    assert len(contexts.enabled()) == 4


def test_disabled_is_not_a_venue_anything_may_address() -> None:
    contexts = _container({}).resolve(IVenueContexts)

    with pytest.raises(VenueNotEnabledError):
        contexts.get(TradingVenue.DISABLED)


def test_the_primary_venue_is_the_first_in_venue_order() -> None:
    """Whatever a legacy list said: the primary does not depend on a setting."""
    container = _container(
        {ConfigKeys.EXCHANGE_TRADING_VENUES.value: ["spot_testnet", "futures_testnet"]}
    )

    contexts = container.resolve(IVenueContexts)

    assert contexts.primary() is contexts.get(TradingVenue.FUTURES_TESTNET)
    assert container.resolve(TradingVenue) is TradingVenue.FUTURES_TESTNET


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


_TWINS = [
    (TradingVenue.FUTURES_TESTNET, TradingVenue.FUTURES_MAINNET),
    (TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET),
]


@pytest.mark.parametrize(("testnet", "mainnet"), _TWINS)
def test_a_mainnet_venue_is_built_from_the_same_classes_as_its_testnet_twin(
    testnet: TradingVenue, mainnet: TradingVenue
) -> None:
    """`EPIC-034` D11 — no mainnet-specific reader, trading client or parser:
    the same adapters, with the venue and its key passed in."""
    contexts = _both_venues().resolve(IVenueContexts)

    twin, real = contexts.get(testnet), contexts.get(mainnet)

    assert real.venue is mainnet
    for part in (
        "metadata_provider",
        "client_factory",
        "account_reader",
        "user_data_stream",
        "history_reader",
        "commission_reader",
        "account_control",
        "book_ticker_reader",
        "mark_price_reader",
    ):
        assert type(getattr(real, part)) is type(getattr(twin, part)), part


@pytest.mark.parametrize(("testnet", "mainnet"), _TWINS)
def test_a_mainnet_venues_key_comes_from_the_environment_or_the_keyring_never_a_file(
    testnet: TradingVenue, mainnet: TradingVenue
) -> None:
    contexts = _both_venues().resolve(IVenueContexts)

    assert isinstance(
        contexts.get(mainnet).credentials_provider, MainnetCredentialsProvider
    )
    assert isinstance(
        contexts.get(testnet).credentials_provider, EnvFirstCredentialsProvider
    )


_KEY_NAMES = {
    TradingVenue.FUTURES_TESTNET: (FUTURES_ENV_API_KEY, FUTURES_ENV_API_SECRET),
    TradingVenue.SPOT_TESTNET: (SPOT_ENV_API_KEY, SPOT_ENV_API_SECRET),
    TradingVenue.FUTURES_MAINNET: (
        FUTURES_MAINNET_ENV_API_KEY,
        FUTURES_MAINNET_ENV_API_SECRET,
    ),
    TradingVenue.SPOT_MAINNET: (SPOT_MAINNET_ENV_API_KEY, SPOT_MAINNET_ENV_API_SECRET),
}


class _RefusingClient:
    """python-binance's `Client` as the builder meets it: it records how it was
    built and then fails like an unreachable exchange, so no request leaves."""

    built: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, **kwargs: Any) -> None:
        _RefusingClient.built.append(kwargs)
        raise RequestsConnectionError("no network in a unit test")


@pytest.mark.parametrize("venue", list(_KEY_NAMES))
def test_testnet_false_reaches_the_client_of_a_mainnet_venue_and_true_the_testnets(
    monkeypatch: pytest.MonkeyPatch, venue: TradingVenue
) -> None:
    """`EPIC-034` D11 — through the real assembly, from the venue's own key to the
    `Client(...)` call: the flag is the venue's and nothing else decides it."""
    _RefusingClient.built = []
    monkeypatch.setattr(binance_client_builder, "Client", _RefusingClient)
    for key_name, secret_name in _KEY_NAMES.values():
        monkeypatch.delenv(key_name, raising=False)
        monkeypatch.delenv(secret_name, raising=False)
    key_name, secret_name = _KEY_NAMES[venue]
    monkeypatch.setenv(key_name, "key")
    monkeypatch.setenv(secret_name, "secret")
    contexts = _both_venues().resolve(IVenueContexts)

    status = contexts.get(venue).account_reader.check_connection()

    assert status.venue is venue
    assert [kwargs["testnet"] for kwargs in _RefusingClient.built] == [venue.is_testnet]
    assert status.failure is ConnectionFailureKind.NETWORK
