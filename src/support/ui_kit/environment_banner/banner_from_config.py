"""`EPIC-028K` — the environment banner's content, read from the boot config.

@details Moved out of `app_bootstrapper.py` (over the 400-line ceiling), with
two changes: the banner names every enabled venue, since both desks may be
open, and the chart is judged by each venue's own market. Since
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
    resolve_trading_venues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.venue_alignment import (
    VenueAlignment,
    compute_venue_alignment,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner.environment_banner_content import (
    EnvironmentBannerContent,
    venue_alignment_banner_content,
)
from sagittarius_engine.interfaces.i_config import IConfig


def environment_banner_content_for(config: IConfig) -> EnvironmentBannerContent:
    """What every screen's banner says in this run.

    The chart reads one market-data venue for every desk, so each enabled venue
    is judged against it, the mainnet ones first (real money), and the banner
    says the first that is not aligned (`EPIC-034` D11)."""
    venues = resolve_trading_venues(config)
    market_data = resolve_market_data_venue(config)
    alignments = (
        compute_venue_alignment(
            market_data, venue, venue.market_type or MarketType.SPOT
        )
        for venue in sorted(venues, key=lambda venue: not venue.is_mainnet)
    )
    alignment = next(
        (a for a in alignments if a is not VenueAlignment.ALIGNED),
        VenueAlignment.ALIGNED,
    )
    return venue_alignment_banner_content(alignment, venues)
