"""`EPIC-027H` — `SpotHolding`'s own arithmetic: `total` and `is_dust`."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)


def _holding(free: str, locked: str, dust_threshold: str = "0.00000001") -> SpotHolding:
    return SpotHolding(
        asset="BTC",
        free=Decimal(free),
        locked=Decimal(locked),
        dust_threshold=Decimal(dust_threshold),
    )


def test_total_is_free_plus_locked():
    holding = _holding("0.5", "0.25")
    assert holding.total == Decimal("0.75")


def test_a_balance_above_the_dust_threshold_is_not_dust():
    holding = _holding("0.5", "0", dust_threshold="0.00000001")
    assert holding.is_dust is False


def test_a_balance_at_the_dust_threshold_is_dust():
    """Mutation-verify the boundary (`<=`, not `<`): the threshold value
    itself is dust, not the first amount past it."""
    holding = _holding("0.00000001", "0", dust_threshold="0.00000001")
    assert holding.is_dust is True


def test_a_balance_below_the_dust_threshold_is_dust():
    holding = _holding("0.000000005", "0", dust_threshold="0.00000001")
    assert holding.is_dust is True


def test_zero_is_dust():
    holding = _holding("0", "0", dust_threshold="0.00000001")
    assert holding.is_dust is True
