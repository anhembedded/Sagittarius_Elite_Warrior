"""`ITradingAccountReader`'s venue-branching bind (`EPIC-027H`), locked
against a real container — the same doctrine `test_module_trading_client_binding.py`
already established for `ITradingClient`: a docstring is not what breaks
when reality changes, a test is (`architecture-rule.md` §7.3).

Real components throughout (`test_no_foreign_port_is_mocked.py`'s own
doctrine): `StdLibContainer` is the Engine's real `IContainer`, `DictConfig`
its real in-memory `IConfig`, and `bind_adapters()` is the same production
wiring `TradingModule.register()` calls.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
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


def test_account_reader_is_futures_by_default():
    """No config value at all — the same shape a fresh install boots
    with. Unconditional bind (`ITradingAccountReader` is read-only and does
    not require trading to be "enabled"), so this must still resolve."""
    container = _container_with_venue(None)

    reader = container.resolve(ITradingAccountReader)

    assert isinstance(reader, FuturesAccountReader)


def test_account_reader_is_futures_when_venue_is_explicitly_disabled():
    container = _container_with_venue(TradingVenue.DISABLED)

    reader = container.resolve(ITradingAccountReader)

    assert isinstance(reader, FuturesAccountReader)


def test_account_reader_is_futures_when_venue_is_futures_testnet():
    container = _container_with_venue(TradingVenue.FUTURES_TESTNET)

    reader = container.resolve(ITradingAccountReader)

    assert isinstance(reader, FuturesAccountReader)


def test_account_reader_is_spot_when_venue_is_spot_testnet():
    """`EPIC-027H` — before this bind existed, every venue silently
    resolved `FuturesAccountReader`, which would have signed a Futures
    Testnet request with Spot Testnet credentials for `SPOT_TESTNET`."""
    container = _container_with_venue(TradingVenue.SPOT_TESTNET)

    reader = container.resolve(ITradingAccountReader)

    assert isinstance(reader, SpotAccountReader)
