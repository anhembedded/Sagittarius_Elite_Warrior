from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.venue_alignment import (
    VenueAlignment,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    BannerSeverity as Severity,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    venue_alignment_banner_content,
)


def test_every_alignment_state_has_content() -> None:
    for alignment in VenueAlignment:
        content = venue_alignment_banner_content(alignment)
        assert content.message
        assert content.icon
        assert content.severity in tuple(Severity)


def test_no_banner_state_says_trading_is_off() -> None:
    """`EPIC-034C` — the switch is gone, and so is the state that named it."""
    for alignment in VenueAlignment:
        assert "OFF" not in venue_alignment_banner_content(alignment).message


def test_mainnet_data_trap_names_both_venues() -> None:
    content = venue_alignment_banner_content(VenueAlignment.DATA_MAINNET_ORDERS_TESTNET)
    assert "MAINNET" in content.message
    assert "TESTNET" in content.message
    assert content.severity is Severity.WARN


def test_testnet_data_behind_mainnet_orders_says_real_money() -> None:
    content = venue_alignment_banner_content(VenueAlignment.DATA_TESTNET_ORDERS_MAINNET)
    assert "TESTNET prices" in content.message
    assert "REAL MONEY" in content.message
    assert content.severity is Severity.DANGER


def test_market_mismatch_warns_the_chart_is_not_the_fill_market() -> None:
    """`EPIC-027G` — a market-type mismatch is a real trading risk (the
    price/instrument on screen is not what the order books against), so it
    renders at the same `DANGER` tier as the mainnet-data trap, not a lesser
    one."""
    content = venue_alignment_banner_content(VenueAlignment.MARKET_MISMATCH)
    assert "market" in content.message.lower()
    assert content.severity is Severity.DANGER


def test_each_alignment_state_maps_to_its_documented_severity() -> None:
    """Severity follows the money at risk (`EPIC-034` D11): `DANGER` only where real
    money is planned against a price that is wrong — a market mismatch, or testnet
    data behind a mainnet venue; testnet orders on mainnet prices cost a price
    mismatch on a test venue, a warning. Fails if a state is added without an entry."""
    expected_severity = {
        VenueAlignment.ALIGNED: Severity.WARN,
        VenueAlignment.MARKET_MISMATCH: Severity.DANGER,
        VenueAlignment.DATA_MAINNET_ORDERS_TESTNET: Severity.WARN,
        VenueAlignment.DATA_TESTNET_ORDERS_MAINNET: Severity.DANGER,
    }
    assert set(expected_severity) == set(VenueAlignment)
    for alignment, severity in expected_severity.items():
        assert venue_alignment_banner_content(alignment).severity is severity


def test_an_aligned_banner_names_every_enabled_venue() -> None:
    """`EPIC-028K` — both desks may be open at once; the banner said
    "FUTURES TESTNET" even when only Spot was enabled."""
    content = venue_alignment_banner_content(
        VenueAlignment.ALIGNED,
        (TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET),
    )
    assert content.message == "FUTURES TESTNET · SPOT TESTNET — simulated funds."

    spot_only = venue_alignment_banner_content(
        VenueAlignment.ALIGNED, (TradingVenue.SPOT_TESTNET,)
    )
    assert "FUTURES" not in spot_only.message
    assert "SPOT TESTNET" in spot_only.message


def test_a_mainnet_venue_is_named_as_real_money_beside_the_simulated_testnets() -> None:
    """`EPIC-034` D11 — what is real is said, apart from what is not."""
    content = venue_alignment_banner_content(
        VenueAlignment.ALIGNED,
        (
            TradingVenue.FUTURES_TESTNET,
            TradingVenue.SPOT_TESTNET,
            TradingVenue.FUTURES_MAINNET,
            TradingVenue.SPOT_MAINNET,
        ),
    )

    assert content.message == (
        "FUTURES TESTNET · SPOT TESTNET — simulated funds. "
        "FUTURES MAINNET · SPOT MAINNET — REAL MONEY."
    )


def test_a_build_with_only_a_mainnet_venue_says_real_money_and_no_simulated_funds() -> (
    None
):
    content = venue_alignment_banner_content(
        VenueAlignment.ALIGNED, (TradingVenue.SPOT_MAINNET,)
    )

    assert content.message == "SPOT MAINNET — REAL MONEY."
