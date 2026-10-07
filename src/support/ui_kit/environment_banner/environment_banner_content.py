"""What the environment banner says: which funds each enabled venue trades.

@details Computed once from the venues the build assembles (`EPIC-034B`), so it is
fixed for the whole session and needs no signal — a plain, immutable projection,
not a reactive ViewModel.

The banner used to judge, per venue, whether the chart's market matched the
market the orders fill in (`VenueAlignment`, `EPIC-021K`) and to warn of a
mismatch. Since `BUG-172` the chart a screen shows *is* its venue's own market
(`TradingVenue.market_data_venue`), so no mismatch can occur on a venue screen and
none of those states is left. Only the screens that act on no venue (Data mode, a
plain historical backtest) read the configured `exchange.market_data_venue`, and
they place no orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class BannerSeverity(Enum):
    """@brief How alarming the banner is, named by what it means.

    @details The banner shows it with the icon and the weight of its text,
    never by colour alone (`ui-presentation-rule.md` §1).
    """

    INFO = "info"
    WARN = "warn"
    DANGER = "danger"


@dataclass(frozen=True)
class EnvironmentBannerContent:
    """@brief Everything `EnvironmentBanner` renders — icon, message,
    severity — as plain, already-decided values."""

    icon: str
    message: str
    severity: BannerSeverity


def venue_banner_content(venues: tuple[TradingVenue, ...]) -> EnvironmentBannerContent:
    """@brief Names every enabled venue and whether its funds are simulated or
    real (`EPIC-028K`, `EPIC-034` D11): every desk may be open at once.

    @raise ValueError `venues` is empty: a build assembles at least one.
    """
    if not venues:
        raise ValueError("the environment banner names at least one venue")
    return EnvironmentBannerContent(
        icon="ⓘ", message=_funds_message(venues), severity=BannerSeverity.WARN
    )


def _funds_message(venues: tuple[TradingVenue, ...]) -> str:
    """The testnets are simulated funds and the mainnets are real money
    (`EPIC-034` D11): both are said when both are there, each for its own."""
    sentences = [
        f"{_names(group)} — {what}."
        for group, what in (
            ([v for v in venues if not v.is_mainnet], "simulated funds"),
            ([v for v in venues if v.is_mainnet], "REAL MONEY"),
        )
        if group
    ]
    return " ".join(sentences)


def _names(venues: list[TradingVenue]) -> str:
    return " · ".join(venue.display_name.upper() for venue in venues)
