from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.venue_alignment import (
    VenueAlignment,
    compute_venue_alignment,
)


def test_a_venue_that_places_no_orders_has_no_alignment() -> None:
    """`EPIC-034C` — the "trading disabled" state is gone: asking for the
    alignment of a venue that cannot trade is a caller's mistake."""
    with pytest.raises(ValueError, match="places no orders"):
        compute_venue_alignment(
            MarketDataVenue.MAINNET_PUBLIC, TradingVenue.DISABLED, MarketType.SPOT
        )


def test_testnet_data_with_testnet_trading_and_matching_chart_market_is_aligned() -> (
    None
):
    assert (
        compute_venue_alignment(
            MarketDataVenue.FUTURES_TESTNET,
            TradingVenue.FUTURES_TESTNET,
            MarketType.FUTURES_USD_M,
        )
        is VenueAlignment.ALIGNED
    )
    assert (
        compute_venue_alignment(
            MarketDataVenue.FUTURES_TESTNET,
            TradingVenue.SPOT_TESTNET,
            MarketType.SPOT,
        )
        is VenueAlignment.ALIGNED
    )


def test_mainnet_data_with_testnet_trading_is_the_named_trap() -> None:
    assert (
        compute_venue_alignment(
            MarketDataVenue.MAINNET_PUBLIC,
            TradingVenue.FUTURES_TESTNET,
            MarketType.FUTURES_USD_M,
        )
        is VenueAlignment.DATA_MAINNET_ORDERS_TESTNET
    )


def test_chart_market_not_matching_trading_venue_market_is_a_market_mismatch() -> None:
    """`EPIC-027G` — the live Trading/Dashboard screens chart `MarketType.SPOT`
    today regardless of `TradingVenue`; while trading Futures Testnet, that
    is a real mismatch this state must name rather than report `ALIGNED`."""
    assert (
        compute_venue_alignment(
            MarketDataVenue.FUTURES_TESTNET,
            TradingVenue.FUTURES_TESTNET,
            MarketType.SPOT,
        )
        is VenueAlignment.MARKET_MISMATCH
    )


def test_market_mismatch_the_other_direction_also_flags() -> None:
    """A Futures-market chart with a Spot Testnet trading venue is the
    mirror case of the named scenario above and must flag the same way."""
    assert (
        compute_venue_alignment(
            MarketDataVenue.FUTURES_TESTNET,
            TradingVenue.SPOT_TESTNET,
            MarketType.FUTURES_USD_M,
        )
        is VenueAlignment.MARKET_MISMATCH
    )


def test_mainnet_data_trap_outranks_a_market_mismatch_when_both_hold() -> None:
    """The mainnet-data trap is the already-named worst case (`EPIC-021`'s
    ADR §2.2); it wins priority over a simultaneous market-type mismatch
    rather than being masked by it."""
    assert (
        compute_venue_alignment(
            MarketDataVenue.MAINNET_PUBLIC,
            TradingVenue.FUTURES_TESTNET,
            MarketType.SPOT,
        )
        is VenueAlignment.DATA_MAINNET_ORDERS_TESTNET
    )


@pytest.mark.parametrize(
    "venue", [TradingVenue.SPOT_MAINNET, TradingVenue.FUTURES_MAINNET]
)
def test_testnet_data_behind_a_mainnet_venue_is_flagged(venue: TradingVenue) -> None:
    """`EPIC-034` D11 — the chart reads one market-data venue; testnet prices
    on screen with real money behind the order button is the worst mismatch."""
    assert (
        compute_venue_alignment(
            MarketDataVenue.FUTURES_TESTNET, venue, venue.market_type
        )
        is VenueAlignment.DATA_TESTNET_ORDERS_MAINNET
    )


@pytest.mark.parametrize(
    "venue", [TradingVenue.SPOT_MAINNET, TradingVenue.FUTURES_MAINNET]
)
def test_mainnet_data_behind_a_mainnet_venue_is_aligned(venue: TradingVenue) -> None:
    assert (
        compute_venue_alignment(
            MarketDataVenue.MAINNET_PUBLIC, venue, venue.market_type
        )
        is VenueAlignment.ALIGNED
    )


def test_testnet_data_behind_a_mainnet_venue_outranks_a_market_mismatch() -> None:
    assert (
        compute_venue_alignment(
            MarketDataVenue.FUTURES_TESTNET,
            TradingVenue.FUTURES_MAINNET,
            MarketType.SPOT,
        )
        is VenueAlignment.DATA_TESTNET_ORDERS_MAINNET
    )
