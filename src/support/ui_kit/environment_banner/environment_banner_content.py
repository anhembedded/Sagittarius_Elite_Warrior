"""What the environment banner says, computed once from `VenueAlignment`
(`EPIC-021K`).

@details `EXCHANGE_MARKET_DATA_VENUE`/`EXCHANGE_TRADING_VENUE` are read
only at boot (`resolve_market_data_venue`/`resolve_trading_venue`,
`binance_endpoints.py`) — Settings has no UI control for either (grep
confirms), so both are file-edit-and-restart config, same tier as
`DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL`. `VenueAlignment` is therefore fixed
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
    VenueAlignment.TRADING_DISABLED: (
        "⏸",
        "Trading is OFF. Data view only.",
        BannerSeverity.INFO,
    ),
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
    banner names every one of them, since both desks may be open at once;
    it used to say "FUTURES TESTNET" even when only Spot was enabled."""
    icon, message, severity = _CONTENT[alignment]
    if alignment is VenueAlignment.ALIGNED and venues:
        names = " · ".join(venue.value.replace("_", " ").upper() for venue in venues)
        message = f"{names} — simulated funds."
    return EnvironmentBannerContent(icon=icon, message=message, severity=severity)
