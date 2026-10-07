"""What the environment banner says, computed once from `VenueAlignment`
(`EPIC-021K`).

@details `EXCHANGE_MARKET_DATA_VENUE` is read only at boot
(`resolve_market_data_venue`, `binance_endpoints.py`) — Settings has no UI
control for it (grep confirms), so it is file-edit-and-restart config, same
tier as `DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL`; the trading venues are every
venue the build assembles (`EPIC-034B`). `VenueAlignment` is therefore fixed
for the whole session, and `EnvironmentBannerContent` needs no signal to
notify a change that can never happen — it is a plain, immutable
projection, not a reactive ViewModel.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.venue_alignment import (
    VenueAlignment,
)


class BannerSeverity(Enum):
    """@brief How alarming the venue situation is, named by what it means.

    @details The banner shows it with the icon and the weight of its text,
    never by colour alone (`ui-presentation-rule.md` §1).
    """

    INFO = "info"
    WARN = "warn"
    DANGER = "danger"


#: English copy, translated from the task's own worked mock (`EPIC-021K`
#: §2.1's table).
_CONTENT: dict[VenueAlignment, tuple[str, str, BannerSeverity]] = {
    VenueAlignment.ALIGNED: (
        "ⓘ",
        "TESTNET — simulated funds.",
        BannerSeverity.WARN,
    ),
    VenueAlignment.MARKET_MISMATCH: (
        "⚠",
        "Chart is showing a different market than your orders trade in. Price shown is not the order's fill market.",
        BannerSeverity.DANGER,
    ),
    VenueAlignment.DATA_MAINNET_ORDERS_TESTNET: (
        "⚠",
        "Chart is showing MAINNET prices, orders fill on TESTNET. Price shown ≠ fill price.",
        # No money is at risk: the only cost is a price mismatch on a test venue
        # (`EPIC-034` D11 — it was DANGER while the testnet was the only venue).
        BannerSeverity.WARN,
    ),
    VenueAlignment.DATA_TESTNET_ORDERS_MAINNET: (
        "⚠",
        (
            "Chart is showing TESTNET prices, orders fill on MAINNET with REAL MONEY. "
            "Set the chart's data source to mainnet."
        ),
        BannerSeverity.DANGER,
    ),
}


@dataclass(frozen=True)
class EnvironmentBannerContent:
    """@brief Everything `EnvironmentBanner` renders — icon, message,
    severity — as plain, already-decided values. No `VenueAlignment`
    logic lives in the widget itself."""

    icon: str
    message: str
    severity: BannerSeverity


def venue_alignment_banner_content(
    alignment: VenueAlignment, venues: tuple[TradingVenue, ...] = ()
) -> EnvironmentBannerContent:
    """@param venues The enabled venues (`EPIC-028K`). While aligned, the
    banner names every one of them, since every desk may be open at once, and says
    whether its funds are simulated or real; it used to say "FUTURES TESTNET" even
    when only Spot was enabled."""
    icon, message, severity = _CONTENT[alignment]
    if alignment is VenueAlignment.ALIGNED and venues:
        message = _aligned_message(venues)
    return EnvironmentBannerContent(icon=icon, message=message, severity=severity)


def _aligned_message(venues: tuple[TradingVenue, ...]) -> str:
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
