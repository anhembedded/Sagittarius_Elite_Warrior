"""`EPIC-028K` — the banner every screen shows, read from the boot config.

@details The real `DictConfig` under the keys a user's settings file carries.
Before this, the bootstrapper judged the chart as Spot whatever the venue,
so a Futures-only run read as a market mismatch (DANGER) although each
screen charts its own venue's market since `EPIC-028C`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner.banner_from_config import (
    environment_banner_content_for,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.surfaces.banner import Severity
from sagittarius_engine.infrastructure.config.dict_config import DictConfig


def _config(venues: list[str], data: str = "futures_testnet") -> DictConfig:
    return DictConfig(
        {
            ConfigKeys.EXCHANGE_TRADING_VENUES.value: venues,
            ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value: data,
        }
    )


def test_a_futures_only_run_is_aligned_not_a_market_mismatch() -> None:
    content = environment_banner_content_for(_config(["futures_testnet"]))

    assert content.severity is Severity.WARN
    assert content.message == "FUTURES TESTNET — simulated funds."


def test_both_venues_enabled_names_both() -> None:
    content = environment_banner_content_for(
        _config(["futures_testnet", "spot_testnet"])
    )

    assert content.message == "FUTURES TESTNET · SPOT TESTNET — simulated funds."


def test_no_venue_enabled_says_view_only() -> None:
    content = environment_banner_content_for(_config([]))

    assert content.message == "Trading is OFF. Data view only."


def test_mainnet_data_with_testnet_orders_is_still_the_danger_state() -> None:
    content = environment_banner_content_for(
        _config(["spot_testnet"], data="mainnet_public")
    )

    assert content.severity is Severity.DANGER
