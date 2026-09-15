from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.domain.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
    manual_order_intent_for,
)


def _position(signed_amount: str) -> LivePosition:
    return LivePosition(
        symbol="BTCUSDT",
        position_amt=Decimal(signed_amount),
        entry_price=Decimal(64000),
        mark_price=Decimal(64000),
        unrealized_pnl=Decimal(0),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


class TestLongClick:
    """`EPIC-024B` §2's table, row 1-2: bấm Long."""

    def test_flat_opens_long_not_reduce_only(self) -> None:
        intent = manual_order_intent_for(ManualOrderDirection.LONG, None)
        assert intent.side is OrderSide.BUY
        assert intent.reduce_only is False

    def test_already_long_adds_to_long_not_reduce_only(self) -> None:
        intent = manual_order_intent_for(ManualOrderDirection.LONG, _position("0.01"))
        assert intent.side is OrderSide.BUY
        assert intent.reduce_only is False

    def test_currently_short_closes_the_short_reduce_only(self) -> None:
        intent = manual_order_intent_for(ManualOrderDirection.LONG, _position("-0.01"))
        assert intent.side is OrderSide.BUY
        assert intent.reduce_only is True


class TestShortClick:
    """`EPIC-024B` §2's table, row 3-4: bấm Short."""

    def test_flat_opens_short_not_reduce_only(self) -> None:
        intent = manual_order_intent_for(ManualOrderDirection.SHORT, None)
        assert intent.side is OrderSide.SELL
        assert intent.reduce_only is False

    def test_already_short_adds_to_short_not_reduce_only(self) -> None:
        intent = manual_order_intent_for(ManualOrderDirection.SHORT, _position("-0.01"))
        assert intent.side is OrderSide.SELL
        assert intent.reduce_only is False

    def test_currently_long_closes_the_long_reduce_only(self) -> None:
        intent = manual_order_intent_for(ManualOrderDirection.SHORT, _position("0.01"))
        assert intent.side is OrderSide.SELL
        assert intent.reduce_only is True


def test_long_and_short_share_no_ambiguity_the_signal_path_has() -> None:
    """Unlike `signal_action_to_order_intent.py` (SELL and SHORT share a
    side), Long/Short here map to different `OrderSide` values outright —
    the button itself already disambiguates direction; only
    `reduce_only`, driven by the real current position, still varies."""
    flat = None
    long_intent = manual_order_intent_for(ManualOrderDirection.LONG, flat)
    short_intent = manual_order_intent_for(ManualOrderDirection.SHORT, flat)
    assert long_intent.side is not short_intent.side
