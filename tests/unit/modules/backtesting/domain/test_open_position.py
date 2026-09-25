"""`OpenPosition` equality — `PR #268` (`BOT-105C` follow-up): two positions
that happen to be field-identical must not compare equal, since they can be
distinct pyramided entries a caller needs to tell apart."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.open_position import (
    OpenPosition,
)

_T1 = datetime(2024, 1, 1, tzinfo=UTC)


def _position() -> OpenPosition:
    return OpenPosition(
        quantity=10.0,
        entry_price=100.0,
        entry_time=_T1,
        balance_before_entry=1_000.0,
        entry_fee=0.0,
        entry_reason="test",
    )


def test_two_field_identical_positions_are_not_equal():
    """Mutation-sensitive: a value-equality `__eq__` (the dataclass default)
    would make this pass; identity-based equality (`eq=False`) is what
    makes two distinct pyramided entries at the same price/time/size
    correctly compare unequal."""
    first = _position()
    second = _position()

    assert first != second


def test_the_same_position_reference_compares_equal_to_itself():
    pos = _position()
    same_reference = pos

    assert pos == same_reference
