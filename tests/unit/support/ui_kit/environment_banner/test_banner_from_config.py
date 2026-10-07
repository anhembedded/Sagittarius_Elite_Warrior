"""`EPIC-028K` — the banner every screen shows, read from the boot config.

@details The real `DictConfig` under the keys a user's settings file carries.
Before this, the bootstrapper judged the chart as Spot whatever the venue,
so a Futures-only run read as a market mismatch (DANGER) although each
screen charts its own venue's market since `EPIC-028C`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.venue_alignment import (
    VenueAlignment,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    BannerSeverity as Severity,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner.banner_from_config import (
    environment_banner_content_for,
    venue_alignments,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig


def _config(venues: list[str], data: str = "mainnet_public") -> DictConfig:
    return DictConfig(
        {
            ConfigKeys.EXCHANGE_TRADING_VENUES.value: venues,
            ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value: data,
        }
    )


def test_the_legacy_venue_setting_changes_nothing_the_banner_says() -> None:
    """`EPIC-034B` — a configuration that lists one venue (or none) no longer
    changes what the banner says: every venue is on."""
    said = {
        environment_banner_content_for(_config(venues))
        for venues in (["futures_testnet"], ["spot_testnet"], [])
    }

    assert len(said) == 1


def test_under_the_default_config_there_is_no_danger_banner_at_all() -> None:
    """`EPIC-034` D11 — every venue is always on, so the testnets read mainnet
    prices under the default `mainnet_public`; that costs a price mismatch on a test
    venue and no money, so it is a warning, and nothing about the mainnet venues
    raises an alarm. A banner red under the default is one the owner stops reading."""
    for venues in (["spot_testnet"], []):
        content = environment_banner_content_for(_config(venues, data="mainnet_public"))

        assert content.severity is Severity.WARN
        assert "MAINNET prices, orders fill on TESTNET" in content.message


def test_testnet_data_with_a_mainnet_venue_enabled_says_real_money_on_testnet_prices() -> (
    None
):
    """`EPIC-034` D11 — every venue is on, the mainnet ones included, so the
    testnet data source is wrong for them: the banner says that, and says it
    before the testnet-side trap because real money is at stake."""
    content = environment_banner_content_for(_config([], data="futures_testnet"))

    assert content.severity is Severity.DANGER
    assert "TESTNET prices" in content.message
    assert "REAL MONEY" in content.message


def test_only_testnet_data_behind_a_mainnet_venue_is_danger() -> None:
    danger = {
        data: environment_banner_content_for(_config([], data=data)).severity
        is Severity.DANGER
        for data in ("mainnet_public", "futures_testnet")
    }

    assert danger == {"mainnet_public": False, "futures_testnet": True}


_MAINNETS = (TradingVenue.FUTURES_MAINNET, TradingVenue.SPOT_MAINNET)
_TESTNETS = (TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET)


def test_under_the_default_data_source_no_mainnet_venue_raises_an_alarm() -> None:
    """`EPIC-034` D11 — the banner is DANGER only where the risk is: under the
    default `mainnet_public` the mainnet venues read the right prices and are
    aligned; what is left is the testnet venues reading mainnet prices, the level
    they had before mainnet was a venue."""
    alignments = venue_alignments(_config([], data="mainnet_public"))

    assert {alignments[venue] for venue in _MAINNETS} == {VenueAlignment.ALIGNED}
    assert {alignments[venue] for venue in _TESTNETS} == {
        VenueAlignment.DATA_MAINNET_ORDERS_TESTNET
    }


def test_under_testnet_data_only_the_mainnet_venues_are_the_real_money_trap() -> None:
    alignments = venue_alignments(_config([], data="futures_testnet"))

    assert {alignments[venue] for venue in _MAINNETS} == {
        VenueAlignment.DATA_TESTNET_ORDERS_MAINNET
    }
    assert {alignments[venue] for venue in _TESTNETS} == {VenueAlignment.ALIGNED}


def test_the_mainnet_venues_are_judged_before_the_testnets() -> None:
    assert list(venue_alignments(_config([]))) == [*_MAINNETS, *_TESTNETS]
