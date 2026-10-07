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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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


def venue_alignments(config: IConfig) -> dict[TradingVenue, VenueAlignment]:
    """Each enabled venue judged against the one market-data venue the chart reads
    (`EPIC-034` D11), the mainnet venues first.

    Only a mainnet venue behind testnet data is the real-money trap
    (`DATA_TESTNET_ORDERS_MAINNET`); under the default `mainnet_public` the mainnet
    venues are `ALIGNED`, and a testnet venue behind mainnet data keeps the
    `DATA_MAINNET_ORDERS_TESTNET` level it had before mainnet was a venue."""
    market_data = resolve_market_data_venue(config)
    return {
        venue: compute_venue_alignment(
            market_data, venue, venue.market_type or MarketType.SPOT
        )
        for venue in sorted(
            resolve_trading_venues(config), key=lambda venue: not venue.is_mainnet
        )
    }


def environment_banner_content_for(config: IConfig) -> EnvironmentBannerContent:
    """What every screen's banner says in this run: the first venue, mainnet
    first, that is not aligned (`venue_alignments`)."""
    alignment = next(
        (
            a
            for a in venue_alignments(config).values()
            if a is not VenueAlignment.ALIGNED
        ),
        VenueAlignment.ALIGNED,
    )
    return venue_alignment_banner_content(alignment, resolve_trading_venues(config))
