"""`TradingModule._bind_trading_client_if_enabled()` — `ITradingClient`'s
conditional bind (`EPIC-021F`), locked in both directions against a real
container.

Found missing by an independent review of PR 4.4f-4 (`EPIC-025E`): the only
existing coverage was `tests/sanity/test_composition_root.py`'s
`_NOT_DISPATCHED` entry for `SubmitOrderCommand`, which *skips* asserting a
resolve under the default (disabled) boot rather than proving either branch
— a regression that made the bind unconditional (the dangerous direction:
real order placement enabled by default) would leave that test green. This
file resolves `ITradingClient` against a real `StdLibContainer` in both
states instead of trusting an exclusion list, per `architecture-rule.md`
§7.3: a docstring is not what breaks when reality changes, a test is.

Real components throughout (`test_no_foreign_port_is_mocked.py`'s own
doctrine): `StdLibContainer` is the Engine's real `IContainer`, `DictConfig`
its real in-memory `IConfig`, and `bind_adapters()` is the same production
wiring `TradingModule.register()` calls — nothing here is a hand-shaped
double.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.module import TradingModule
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.exceptions import DependencyResolutionError
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


def test_trading_client_stays_unbound_when_venue_is_disabled_by_default():
    """No config value at all — the same shape a fresh install boots with."""
    container = _container_with_venue(None)

    TradingModule._bind_trading_client_if_enabled(container)

    with pytest.raises(DependencyResolutionError):
        container.resolve(ITradingClient)


def test_trading_client_stays_unbound_when_venue_is_explicitly_disabled():
    container = _container_with_venue(TradingVenue.DISABLED)

    TradingModule._bind_trading_client_if_enabled(container)

    with pytest.raises(DependencyResolutionError):
        container.resolve(ITradingClient)


def test_trading_client_is_bound_and_constructible_when_venue_is_enabled():
    container = _container_with_venue(TradingVenue.FUTURES_TESTNET)

    TradingModule._bind_trading_client_if_enabled(container)

    client = container.resolve(ITradingClient)
    assert isinstance(client, FuturesTradingClient)
