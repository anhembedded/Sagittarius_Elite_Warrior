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

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueAlignment(str, Enum):
    """@brief The four states a user can be in, in order of increasing risk."""

    #: `TradingVenue.DISABLED` — no order can ever be sent, regardless of
    #: `MarketDataVenue`. The safest state: nothing to misalign.
    TRADING_DISABLED = "trading_disabled"
    #: Both venues answer to the same environment (testnet data, testnet
    #: orders) and the chart shows the same market the order would fill in
    #: — what the price shown is the price that would fill at.
    ALIGNED = "aligned"
    #: The chart's market (`EPIC-027G` — e.g. the live Trading screen's own
    #: chart/stream, hard-coded to `MarketType.SPOT`) is not the market
    #: `trading_venue.market_type` sends orders to (e.g. `FUTURES_USD_M`
    #: while `TradingVenue.FUTURES_TESTNET` is active). The price and the
    #: instrument on screen are not the ones the order books against.
    MARKET_MISMATCH = "market_mismatch"
    #: `MarketDataVenue.MAINNET_PUBLIC` while `TradingVenue.FUTURES_TESTNET`
    #: — real prices on screen, fake money behind the order button. The
    #: literal trap `EPIC-021`'s ADR §2.2 names: "chart hiển thị giá
    #: mainnet trong khi lệnh khớp trên testnet."
    DATA_MAINNET_ORDERS_TESTNET = "data_mainnet_orders_testnet"


def compute_venue_alignment(
    market_data_venue: MarketDataVenue,
    trading_venue: TradingVenue,
    chart_market_type: MarketType,
) -> VenueAlignment:
    """@brief The one place this comparison is made.

    @details `chart_market_type` is the market the caller's chart/stream
    actually reads (`EPIC-027G` — the live Trading/Dashboard screens hard-
    code `MarketType.SPOT` today, independently of `trading_venue`, which
    this function's own docstring anticipated as "the fourth state" rather
    than a fifth independent comparison elsewhere).

    Priority when more than one condition holds: the mainnet-data trap is
    checked first because it is the one already named as the worst case
    (real prices driving a decision, `EPIC-021`'s ADR §2.2); a market-type
    mismatch is checked next, since either one alone is reason enough not
    to report `ALIGNED`.
    """
    if trading_venue is TradingVenue.DISABLED:
        return VenueAlignment.TRADING_DISABLED
    if market_data_venue is MarketDataVenue.MAINNET_PUBLIC:
        return VenueAlignment.DATA_MAINNET_ORDERS_TESTNET
    if chart_market_type is not trading_venue.market_type:
        return VenueAlignment.MARKET_MISMATCH
    return VenueAlignment.ALIGNED
