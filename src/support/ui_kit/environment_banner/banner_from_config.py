"""`EPIC-028K` — the environment banner's content, read from the boot config.

@details Moved out of `app_bootstrapper.py` (over the 400-line ceiling): the
banner names every enabled venue, since both desks may be open. Since `BUG-172`
it no longer judges the chart against the venue, because a screen's chart is its
venue's own market and the two cannot differ.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_trading_venues,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner.environment_banner_content import (
    EnvironmentBannerContent,
    venue_banner_content,
)
from sagittarius_engine.interfaces.i_config import IConfig


def environment_banner_content_for(config: IConfig) -> EnvironmentBannerContent:
    """What every screen's banner says in this run: each enabled venue and
    whether its funds are simulated or real."""
    return venue_banner_content(resolve_trading_venues(config))
