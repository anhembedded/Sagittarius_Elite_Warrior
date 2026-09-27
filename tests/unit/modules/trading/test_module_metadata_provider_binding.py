"""`IMarketMetadataProvider`'s venue-branching bind (`EPIC-027I`), locked
against a real container — the same doctrine
`test_module_account_reader_binding.py` already established for
`ITradingAccountReader` (`architecture-rule.md` §7.3: a docstring is not
what breaks when reality changes, a test is).

Real components throughout (`test_no_foreign_port_is_mocked.py`'s own
doctrine): `StdLibContainer` is the Engine's real `IContainer`, `DictConfig`
its real in-memory `IConfig`, and `bind_adapters()` is the same production
wiring `TradingModule.register()` calls.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.interfaces.i_config import IConfig


def _container_with_venue(venue: TradingVenue | None) -> StdLibContainer:
    container = StdLibContainer()
    config = (
        DictConfig()
        if venue is None
        else DictConfig({ConfigKeys.EXCHANGE_TRADING_VENUE.value: venue.value})
    )
    container.singleton(IConfig, config)
    bind_adapters(container)
    return container


def test_metadata_provider_is_futures_by_default():
    """No config value at all — the same shape a fresh install boots
    with. Unconditional bind, matching `ITradingClientFactory`'s own
    dependency on this port, so it must still resolve."""
    container = _container_with_venue(None)

    provider = container.resolve(IMarketMetadataProvider)

    assert isinstance(provider, FuturesMetadataProvider)


def test_metadata_provider_is_futures_when_venue_is_explicitly_disabled():
    container = _container_with_venue(TradingVenue.DISABLED)

    provider = container.resolve(IMarketMetadataProvider)

    assert isinstance(provider, FuturesMetadataProvider)


def test_metadata_provider_is_futures_when_venue_is_futures_testnet():
    container = _container_with_venue(TradingVenue.FUTURES_TESTNET)

    provider = container.resolve(IMarketMetadataProvider)

    assert isinstance(provider, FuturesMetadataProvider)


def test_metadata_provider_is_spot_when_venue_is_spot_testnet():
    """`EPIC-027I` — before this bind existed, every venue silently
    resolved `FuturesMetadataProvider`, which would round a Spot order's
    quantity against Futures' own `stepSize`/`tickSize`/`minNotional`."""
    container = _container_with_venue(TradingVenue.SPOT_TESTNET)

    provider = container.resolve(IMarketMetadataProvider)

    assert isinstance(provider, SpotMetadataProvider)
