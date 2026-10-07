"""`EPIC-028K` — the banner every screen shows, read from the boot config.

@details The real `DictConfig` under the keys a user's settings file carries.
`BUG-172`: the banner no longer reads `exchange.market_data_venue` at all — a
venue's chart is its own market, so what the setting says cannot change what the
banner says.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    BannerSeverity as Severity,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner.banner_from_config import (
    environment_banner_content_for,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig


def _config(venues: list[str], data: str = "mainnet_public") -> DictConfig:
    #: The retired Data Source key, spelled as a configuration of an earlier build
    #: holds it: the banner never reads it.
    return DictConfig(
        {
            ConfigKeys.EXCHANGE_TRADING_VENUES.value: venues,
            "exchange.market_data_venue": data,
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


@pytest.mark.parametrize("data", [venue.value for venue in MarketDataVenue])
def test_the_data_source_setting_changes_nothing_the_banner_says(data: str) -> None:
    """`BUG-172` — it was DANGER under a testnet data source with mainnet venues
    on, and a warning about mainnet prices under the default. Neither state exists
    any more: no venue's chart reads that setting."""
    content = environment_banner_content_for(_config([], data=data))

    assert content == environment_banner_content_for(_config([]))
    assert content.severity is Severity.WARN
    assert "prices" not in content.message
    assert "REAL MONEY" in content.message and "simulated funds" in content.message
