"""`EPIC-028A` — `resolve_trading_venues`: the list key wins, the scalar key
still reads exactly as before, and no malformed entry ever turns a venue on."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_trading_venue,
    resolve_trading_venues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig

_LIST_KEY = ConfigKeys.EXCHANGE_TRADING_VENUES.value
_SCALAR_KEY = ConfigKeys.EXCHANGE_TRADING_VENUE.value


def test_the_list_is_read_in_configuration_order() -> None:
    config = DictConfig({_LIST_KEY: ["spot_testnet", "futures_testnet"]})

    assert resolve_trading_venues(config) == (
        TradingVenue.SPOT_TESTNET,
        TradingVenue.FUTURES_TESTNET,
    )


def test_the_list_wins_over_the_scalar() -> None:
    config = DictConfig({_LIST_KEY: ["spot_testnet"], _SCALAR_KEY: "futures_testnet"})

    assert resolve_trading_venues(config) == (TradingVenue.SPOT_TESTNET,)


def test_an_empty_list_turns_trading_off_even_with_a_scalar_venue() -> None:
    config = DictConfig({_LIST_KEY: [], _SCALAR_KEY: "futures_testnet"})

    assert resolve_trading_venues(config) == ()


@pytest.mark.parametrize(
    ("scalar", "expected"),
    [
        ("futures_testnet", (TradingVenue.FUTURES_TESTNET,)),
        ("spot_testnet", (TradingVenue.SPOT_TESTNET,)),
        ("disabled", ()),
    ],
)
def test_a_scalar_only_config_reads_as_a_one_element_set(
    scalar: str, expected: tuple[TradingVenue, ...]
) -> None:
    assert resolve_trading_venues(DictConfig({_SCALAR_KEY: scalar})) == expected


def test_no_venue_key_at_all_means_trading_is_off() -> None:
    assert resolve_trading_venues(DictConfig()) == ()


def test_an_unknown_entry_is_dropped_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = DictConfig({_LIST_KEY: ["futures_mainnet", "spot_testnet"]})

    assert resolve_trading_venues(config) == (TradingVenue.SPOT_TESTNET,)
    assert "futures_mainnet" in caplog.text


def test_disabled_and_repeats_inside_the_list_are_skipped() -> None:
    config = DictConfig({_LIST_KEY: ["disabled", "futures_testnet", "futures_testnet"]})

    assert resolve_trading_venues(config) == (TradingVenue.FUTURES_TESTNET,)


def test_a_non_list_value_turns_trading_off_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bare string is the likeliest slip (the scalar's shape under the
    list's key); reading it character by character would be nonsense, and
    guessing it meant a one-element list would turn trading on by typo."""
    config = DictConfig({_LIST_KEY: "futures_testnet"})

    assert resolve_trading_venues(config) == ()
    assert "must be a list" in caplog.text


def test_the_single_venue_reader_is_the_primary_of_the_list() -> None:
    """Review F2: the banner, the Welcome line and Settings read one venue.
    They must name the venue the process actually runs as primary, not the
    scalar key the list has overridden."""
    config = DictConfig(
        {_LIST_KEY: ["spot_testnet", "futures_testnet"], _SCALAR_KEY: "disabled"}
    )

    assert resolve_trading_venue(config) is TradingVenue.SPOT_TESTNET


def test_the_single_venue_reader_is_disabled_for_an_empty_list() -> None:
    config = DictConfig({_LIST_KEY: [], _SCALAR_KEY: "futures_testnet"})

    assert resolve_trading_venue(config) is TradingVenue.DISABLED
