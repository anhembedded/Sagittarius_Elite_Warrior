"""`EPIC-021M` §2.2/§4 — `EquitySample.total = wallet_balance +
unrealized_pnl`, the one domain calculation this task's design section
calls out as needing to be testable with no network."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.equity_sample import EquitySample


def _sample(wallet_balance: str, unrealized_pnl: str) -> EquitySample:
    return EquitySample(
        captured_at=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
        wallet_balance=Decimal(wallet_balance),
        unrealized_pnl=Decimal(unrealized_pnl),
    )


def test_total_is_wallet_balance_plus_unrealized_pnl() -> None:
    sample = _sample("1000.00", "25.50")

    assert sample.total == Decimal("1025.50")


def test_total_with_a_negative_unrealized_pnl() -> None:
    sample = _sample("1000.00", "-42.13")

    assert sample.total == Decimal("957.87")


def test_total_with_zero_unrealized_pnl_is_just_the_wallet_balance() -> None:
    sample = _sample("500.00", "0")

    assert sample.total == Decimal("500.00")
