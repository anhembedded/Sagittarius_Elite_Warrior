"""`EPIC-034B` — `resolve_trading_venues`: every venue that can place orders is
assembled, whatever the configuration says; a configuration written before the
toggles left still loads, and says so once."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    log_ignored_venue_setting,
    resolve_trading_venue,
    resolve_trading_venues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig

_LIST_KEY = ConfigKeys.EXCHANGE_TRADING_VENUES.value
_SCALAR_KEY = ConfigKeys.EXCHANGE_TRADING_VENUE.value
_ALL = (
    TradingVenue.FUTURES_TESTNET,
    TradingVenue.SPOT_TESTNET,
    TradingVenue.FUTURES_MAINNET,
    TradingVenue.SPOT_MAINNET,
)


@pytest.mark.parametrize(
    "values",
    [
        {},
        {_SCALAR_KEY: "disabled"},
        {_SCALAR_KEY: "spot_testnet"},
        {_LIST_KEY: []},
        {_LIST_KEY: ["spot_testnet"], _SCALAR_KEY: "futures_testnet"},
        {_LIST_KEY: "not a list"},
        {_LIST_KEY: ["futures_mainnet"]},
    ],
)
def test_every_orderable_venue_is_assembled_whatever_the_configuration_says(
    values: dict[str, object],
) -> None:
    assert resolve_trading_venues(DictConfig(values)) == _ALL


def test_disabled_is_never_assembled() -> None:
    assert TradingVenue.DISABLED not in resolve_trading_venues(DictConfig())


def test_the_single_venue_reader_is_the_first_in_venue_order() -> None:
    config = DictConfig({_LIST_KEY: ["spot_testnet"], _SCALAR_KEY: "spot_testnet"})

    assert resolve_trading_venue(config) is TradingVenue.FUTURES_TESTNET


@pytest.mark.parametrize(
    "values",
    [
        {_LIST_KEY: ["futures_testnet"]},
        {_LIST_KEY: []},
        {_SCALAR_KEY: "spot_testnet"},
    ],
)
def test_a_configuration_that_names_venues_is_ignored_and_says_so(
    values: dict[str, object], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="App.ExchangeClient"):
        assert log_ignored_venue_setting(DictConfig(values)) is True

    assert "ignored" in caplog.text
    assert "EPIC-034B" in caplog.text


@pytest.mark.parametrize("values", [{}, {_SCALAR_KEY: "disabled"}])
def test_the_defaults_say_nothing(
    values: dict[str, object], caplog: pytest.LogCaptureFixture
) -> None:
    """The defaults file carries `"disabled"`; nobody chose it."""
    with caplog.at_level("INFO", logger="App.ExchangeClient"):
        assert log_ignored_venue_setting(DictConfig(values)) is False

    assert caplog.text == ""
