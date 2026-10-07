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


def _config(venues: list[str], data: str = "futures_testnet") -> DictConfig:
    return DictConfig(
        {
            ConfigKeys.EXCHANGE_TRADING_VENUES.value: venues,
            ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value: data,
        }
    )


def test_every_venue_is_named_whatever_the_legacy_setting_lists() -> None:
    """`EPIC-034B` — a configuration that lists one venue (or none) no longer
    changes what the banner says: every venue is on."""
    for venues in (["futures_testnet"], ["spot_testnet"], []):
        content = environment_banner_content_for(_config(venues))

        assert content.severity is Severity.WARN
        assert content.message == (
            "FUTURES TESTNET · SPOT TESTNET — simulated funds. "
            "FUTURES MAINNET · SPOT MAINNET — REAL MONEY."
        )


def test_mainnet_data_with_testnet_orders_is_still_the_danger_state() -> None:
    content = environment_banner_content_for(
        _config(["spot_testnet"], data="mainnet_public")
    )

    assert content.severity is Severity.DANGER
