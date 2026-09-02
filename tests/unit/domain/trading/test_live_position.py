from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.live_position import (
    LiquidationPrice,
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)


def _position(
    position_amt: Decimal, unrealized_pnl: Decimal = Decimal(0)
) -> LivePosition:
    return LivePosition(
        symbol="BTCUSDT",
        position_amt=position_amt,
        entry_price=Decimal(60000),
        mark_price=Decimal(60100),
        unrealized_pnl=unrealized_pnl,
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=LiquidationPrice(Decimal(50000)),
        updated_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def test_positive_position_amt_is_long() -> None:
    assert _position(Decimal("0.5")).side is PositionSide.LONG


def test_negative_position_amt_is_short() -> None:
    assert _position(Decimal("-0.5")).side is PositionSide.SHORT


def test_live_pnl_excludes_funding_fees() -> None:
    """Locks current scope (`EPIC-021E` §2.5): `unrealized_pnl` is read
    verbatim from Binance's own `unRealizedProfit` field, which the
    exchange itself defines as excluding funding fees already settled on
    this position. `LivePosition` does not separately track or net out
    funding here — there is no `funding_fee` field to subtract.

    Gate to change this: the day a caller needs a funding-inclusive PnL
    figure (e.g. a "true cost of holding" report), add a *new* field for
    it rather than redefining what `unrealized_pnl` means — every existing
    caller, this test included, already depends on it being the exchange's
    raw mark-to-market number.
    """
    position = _position(Decimal("0.5"), unrealized_pnl=Decimal("125.50"))

    assert not hasattr(position, "funding_fee")
    assert position.unrealized_pnl == Decimal("125.50")
