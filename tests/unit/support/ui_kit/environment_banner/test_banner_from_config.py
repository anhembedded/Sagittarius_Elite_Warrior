"""`EPIC-028K` — the banner every screen shows, read from the boot config.

@details The real `DictConfig` under the keys a user's settings file carries.
Before this, the bootstrapper judged the chart as Spot whatever the venue,
so a Futures-only run read as a market mismatch (DANGER) although each
screen charts its own venue's market since `EPIC-028C`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    BannerSeverity as Severity,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner.banner_from_config import (
    environment_banner_content_for,
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


def test_mainnet_data_with_testnet_orders_is_still_the_danger_state() -> None:
    content = environment_banner_content_for(
        _config(["spot_testnet"], data="mainnet_public")
    )

    assert content.severity is Severity.DANGER


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


def test_mainnet_data_names_the_testnet_trap_not_the_mainnet_one() -> None:
    content = environment_banner_content_for(_config([], data="mainnet_public"))

    assert content.severity is Severity.DANGER
    assert "MAINNET prices, orders fill on TESTNET" in content.message
