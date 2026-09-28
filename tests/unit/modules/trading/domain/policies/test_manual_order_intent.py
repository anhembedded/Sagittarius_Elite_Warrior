from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.manual_short_not_supported_on_market_error import (
    ManualShortNotSupportedOnMarketError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
    manual_order_intent_for,
)

_FUTURES = MarketType.FUTURES_USD_M


def _holding(free: str, *, dust_threshold: str = "0.00001") -> SpotHolding:
    return SpotHolding(
        asset="BTC",
        free=Decimal(free),
        locked=Decimal(0),
        dust_threshold=Decimal(dust_threshold),
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
        intent = manual_order_intent_for(ManualOrderDirection.LONG, None, _FUTURES)
        assert intent.side is OrderSide.BUY
        assert intent.reduce_only is False

    def test_already_long_adds_to_long_not_reduce_only(self) -> None:
        intent = manual_order_intent_for(
            ManualOrderDirection.LONG, _position("0.01"), _FUTURES
        )
        assert intent.side is OrderSide.BUY
        assert intent.reduce_only is False

    def test_currently_short_closes_the_short_reduce_only(self) -> None:
        intent = manual_order_intent_for(
            ManualOrderDirection.LONG, _position("-0.01"), _FUTURES
        )
        assert intent.side is OrderSide.BUY
        assert intent.reduce_only is True

    def test_long_is_allowed_on_spot_too(self) -> None:
        """Spot has no short capability, but Long (a plain Buy) is always
        valid there — only `SHORT` is refused (see `TestSpotRefusesShort`)."""
        intent = manual_order_intent_for(
            ManualOrderDirection.LONG, None, MarketType.SPOT
        )
        assert intent.side is OrderSide.BUY
        assert intent.reduce_only is False


class TestShortClick:
    """`EPIC-024B` §2's table, row 3-4: bấm Short — on a market that can
    represent one (`MarketType.FUTURES_USD_M`); Spot's own refusal is
    `TestSpotRefusesShort` below."""

    def test_flat_opens_short_not_reduce_only(self) -> None:
        intent = manual_order_intent_for(ManualOrderDirection.SHORT, None, _FUTURES)
        assert intent.side is OrderSide.SELL
        assert intent.reduce_only is False

    def test_already_short_adds_to_short_not_reduce_only(self) -> None:
        intent = manual_order_intent_for(
            ManualOrderDirection.SHORT, _position("-0.01"), _FUTURES
        )
        assert intent.side is OrderSide.SELL
        assert intent.reduce_only is False

    def test_currently_long_closes_the_long_reduce_only(self) -> None:
        intent = manual_order_intent_for(
            ManualOrderDirection.SHORT, _position("0.01"), _FUTURES
        )
        assert intent.side is OrderSide.SELL
        assert intent.reduce_only is True


class TestSpotRefusesShort:
    """`EPIC-027K` post-review fix (PR #284) — before this fix, a Spot
    Short click silently became a plain `SELL`/`reduce_only=False`,
    indistinguishable from a deliberate sale of a real holding, because
    `SpotTradingClient.get_positions()` always answers `[]` (no leveraged
    position to read), which made `current_position` always `None` here
    regardless of the account's real holdings. `EPIC-027O` narrows the
    refusal to "no real holding" — `TestSpotSellsWithHolding` below covers
    the case it no longer refuses."""

    def test_flat_short_is_refused(self) -> None:
        with pytest.raises(
            ManualShortNotSupportedOnMarketError, match="not supported on Spot"
        ):
            manual_order_intent_for(ManualOrderDirection.SHORT, None, MarketType.SPOT)

    def test_short_is_refused_even_with_a_position_argument(self) -> None:
        """Never reachable in production (Spot's own `get_positions()`
        always answers `[]`), but the refusal must not depend on that —
        it is a market capability, not a position-shape coincidence."""
        with pytest.raises(ManualShortNotSupportedOnMarketError):
            manual_order_intent_for(
                ManualOrderDirection.SHORT, _position("0.01"), MarketType.SPOT
            )

    def test_dust_holding_is_still_refused(self) -> None:
        """A holding at or below its own `dust_threshold` is not sellable
        (`SpotHolding.is_dust`) — the button reads as "no real holding"."""
        dust = _holding("0.000001", dust_threshold="0.00001")
        with pytest.raises(
            ManualShortNotSupportedOnMarketError, match="not supported on Spot"
        ):
            manual_order_intent_for(
                ManualOrderDirection.SHORT, None, MarketType.SPOT, dust
            )


class TestSpotSellsWithHolding:
    """`EPIC-027O` — a Spot "Sell" click (still `ManualOrderDirection.SHORT`
    under the hood, see `ManualOrderCard`'s own docstring) is allowed once a
    real, non-dust holding backs it."""

    def test_real_holding_sells_not_reduce_only(self) -> None:
        intent = manual_order_intent_for(
            ManualOrderDirection.SHORT, None, MarketType.SPOT, _holding("0.5")
        )
        assert intent.side is OrderSide.SELL
        assert intent.reduce_only is False

    def test_ignores_current_position_argument(self) -> None:
        """Spot never has one (`get_positions()` always `[]`), and this
        path must not depend on that happening to be true — the holding is
        what decides, not the position."""
        intent = manual_order_intent_for(
            ManualOrderDirection.SHORT,
            _position("0.01"),
            MarketType.SPOT,
            _holding("0.5"),
        )
        assert intent.side is OrderSide.SELL
        assert intent.reduce_only is False


def test_long_and_short_share_no_ambiguity_the_signal_path_has() -> None:
    """Unlike `signal_action_to_order_intent.py` (SELL and SHORT share a
    side), Long/Short here map to different `OrderSide` values outright —
    the button itself already disambiguates direction; only
    `reduce_only`, driven by the real current position, still varies."""
    flat = None
    long_intent = manual_order_intent_for(ManualOrderDirection.LONG, flat, _FUTURES)
    short_intent = manual_order_intent_for(ManualOrderDirection.SHORT, flat, _FUTURES)
    assert long_intent.side is not short_intent.side
