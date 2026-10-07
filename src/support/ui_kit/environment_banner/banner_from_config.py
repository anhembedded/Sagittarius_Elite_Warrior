"""`EPIC-028K` — the environment banner's content, read from the boot config.

@details Moved out of `app_bootstrapper.py` (over the 400-line ceiling), with
two changes: the banner names every enabled venue, since both desks may be
open, and the chart is judged by the primary venue's market. Since
`EPIC-028C` every screen charts its own venue's market, so the
`MarketType.SPOT` the bootstrapper passed made a Futures run read as a
market mismatch.

Read once at boot: neither venue key has a Settings control that applies
without a restart (`environment_banner_content.py`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_market_data_venue,
    resolve_trading_venue,
    resolve_trading_venues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.venue_alignment import (
    compute_venue_alignment,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner.environment_banner_content import (
    EnvironmentBannerContent,
    venue_alignment_banner_content,
)
from sagittarius_engine.interfaces.i_config import IConfig


def environment_banner_content_for(config: IConfig) -> EnvironmentBannerContent:
    """What every screen's banner says in this run."""
    venues = resolve_trading_venues(config)
    primary = resolve_trading_venue(config)
    alignment = compute_venue_alignment(
        resolve_market_data_venue(config),
        primary,
        primary.market_type or MarketType.SPOT,
    )
    return venue_alignment_banner_content(alignment, venues)
