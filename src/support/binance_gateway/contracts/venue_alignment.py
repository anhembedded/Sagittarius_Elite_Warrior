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
    """@brief The states a user can be in, in order of increasing risk."""

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
    #: `MarketDataVenue.FUTURES_TESTNET` while a mainnet venue is the one the
    #: orders go to (`EPIC-034` D11) — testnet prices on screen, real money
    #: behind the order button: the trap above turned over, and the worse of
    #: the two. The chart, its live stream and the backtests read one
    #: process-wide market-data venue, so while a mainnet venue is enabled no
    #: setting is right for every venue (the full fix is a market-data source
    #: per trading venue); this state says so rather than letting it pass.
    DATA_TESTNET_ORDERS_MAINNET = "data_testnet_orders_mainnet"


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

    Priority when more than one condition holds: testnet data behind a mainnet
    venue is checked first, since real money is at stake on a price that is
    not real (`EPIC-034` D11); the mainnet-data trap is next, the case
    `EPIC-021`'s ADR §2.2 names (real prices driving a decision); a market-type
    mismatch is checked next, since either one alone is reason enough not
    to report `ALIGNED`.

    @raise ValueError `trading_venue` places no orders (`DISABLED`).
    """
    if not trading_venue.supports_order_submission:
        raise ValueError(
            f"{trading_venue.value} places no orders, so its alignment with the "
            "chart is not a question (`EPIC-034C` removed the 'Trading is OFF' state)"
        )
    if (
        market_data_venue is MarketDataVenue.FUTURES_TESTNET
        and trading_venue.is_mainnet
    ):
        return VenueAlignment.DATA_TESTNET_ORDERS_MAINNET
    if (
        market_data_venue is MarketDataVenue.MAINNET_PUBLIC
        and not trading_venue.is_mainnet
    ):
        # Real prices behind testnet orders; behind a mainnet venue's they are the
        # right prices (`EPIC-034` D11).
        return VenueAlignment.DATA_MAINNET_ORDERS_TESTNET
    if chart_market_type is not trading_venue.market_type:
        return VenueAlignment.MARKET_MISMATCH
    return VenueAlignment.ALIGNED
