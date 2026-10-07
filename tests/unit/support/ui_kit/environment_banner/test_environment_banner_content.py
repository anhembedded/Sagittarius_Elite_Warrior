from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    BannerSeverity as Severity,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    venue_banner_content,
)


def test_a_banner_names_every_enabled_venue() -> None:
    """`EPIC-028K` — both desks may be open at once; the banner said
    "FUTURES TESTNET" even when only Spot was enabled."""
    content = venue_banner_content(
        (TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET)
    )
    assert content.message == "FUTURES TESTNET · SPOT TESTNET — simulated funds."

    spot_only = venue_banner_content((TradingVenue.SPOT_TESTNET,))
    assert "FUTURES" not in spot_only.message
    assert "SPOT TESTNET" in spot_only.message


def test_a_mainnet_venue_is_named_as_real_money_beside_the_simulated_testnets() -> None:
    """`EPIC-034` D11 — what is real is said, apart from what is not."""
    content = venue_banner_content(
        (
            TradingVenue.FUTURES_TESTNET,
            TradingVenue.SPOT_TESTNET,
            TradingVenue.FUTURES_MAINNET,
            TradingVenue.SPOT_MAINNET,
        )
    )

    assert content.message == (
        "FUTURES TESTNET · SPOT TESTNET — simulated funds. "
        "FUTURES MAINNET · SPOT MAINNET — REAL MONEY."
    )


def test_a_build_with_only_a_mainnet_venue_says_real_money_and_no_simulated_funds() -> (
    None
):
    content = venue_banner_content((TradingVenue.SPOT_MAINNET,))

    assert content.message == "SPOT MAINNET — REAL MONEY."


def test_the_banner_says_neither_that_trading_is_off_nor_that_a_chart_is_wrong() -> (
    None
):
    """`EPIC-034C` removed the switch; `BUG-172` removed the chart mismatch: a
    screen's chart is its venue's own market, so the banner has nothing to warn of
    there and says nothing of it."""
    content = venue_banner_content(
        tuple(venue for venue in TradingVenue if venue.supports_order_submission)
    )

    assert "OFF" not in content.message
    assert "prices" not in content.message
    assert content.icon
    assert content.severity is Severity.WARN


def test_a_banner_names_at_least_one_venue() -> None:
    with pytest.raises(ValueError, match="at least one venue"):
        venue_banner_content(())
