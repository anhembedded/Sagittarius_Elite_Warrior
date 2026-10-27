"""`EPIC-047H` - instances of the candle window, a full one and one for a symbol the host has no store for."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.closed_candle_window import (
    CandleWindow,
    StoredCandle,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

OPENED = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)


def full_candle_window() -> CandleWindow:
    return CandleWindow(
        TradingVenue.FUTURES_TESTNET,
        "BTCUSDT",
        "1m",
        tuple(
            StoredCandle(
                OPENED + timedelta(minutes=i),
                Decimal("67000.10") + i,
                Decimal("67010.5") + i,
                Decimal("66990.25") + i,
                Decimal("67005.75") + i,
                Decimal("12.345"),
            )
            for i in range(3)
        ),
        shard_found=True,
        older_available=True,
    )


def minimal_candle_window() -> CandleWindow:
    return CandleWindow(
        TradingVenue.SPOT_TESTNET,
        "ETHUSDT",
        "1h",
        (),
        shard_found=False,
        older_available=False,
    )
