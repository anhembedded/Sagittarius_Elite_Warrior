"""`EPIC-021K` — whether the venue a user is *looking at* (`MarketDataVenue`)
and the venue their orders actually *go to* (`TradingVenue`) agree, and
what that means for the money at stake.

@details Named, not inferred by the UI from two separate reads: a screen
that read `MarketDataVenue`/`TradingVenue` independently and built its own
"are these the same" string would be the exact per-screen duplication
`architecture-rule.md` §6 exists to forbid, and a second screen doing the
same comparison slightly differently is how a "silent misalignment" bug
gets born. This type is the single source of truth for what the banner
says, computed once at boot (`compute_venue_alignment`), never re-derived
per screen.
"""

from __future__ import annotations

from enum import Enum

from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)


class VenueAlignment(str, Enum):
    """@brief The three states a user can be in, in order of increasing risk."""

    #: `TradingVenue.DISABLED` — no order can ever be sent, regardless of
    #: `MarketDataVenue`. The safest state: nothing to misalign.
    TRADING_DISABLED = "trading_disabled"
    #: Both venues answer to the same environment (testnet data, testnet
    #: orders) — what the price shown is the price that would fill at.
    ALIGNED = "aligned"
    #: `MarketDataVenue.MAINNET_PUBLIC` while `TradingVenue.FUTURES_TESTNET`
    #: — real prices on screen, fake money behind the order button. The
    #: literal trap `EPIC-021`'s ADR §2.2 names: "chart hiển thị giá
    #: mainnet trong khi lệnh khớp trên testnet."
    DATA_MAINNET_ORDERS_TESTNET = "data_mainnet_orders_testnet"


def compute_venue_alignment(
    market_data_venue: MarketDataVenue, trading_venue: TradingVenue
) -> VenueAlignment:
    """@brief The one place this comparison is made.

    @details `TradingVenue` has no `MAINNET` member yet (ADR §3 — a future
    epic's reviewed addition, not a config flip), so the only real
    misalignment this app can produce today is testnet orders against
    mainnet data; when that day comes, this function is where the fourth
    state gets added, not a fifth independent comparison somewhere else.
    """
    if trading_venue is TradingVenue.DISABLED:
        return VenueAlignment.TRADING_DISABLED
    if market_data_venue is MarketDataVenue.MAINNET_PUBLIC:
        return VenueAlignment.DATA_MAINNET_ORDERS_TESTNET
    return VenueAlignment.ALIGNED
