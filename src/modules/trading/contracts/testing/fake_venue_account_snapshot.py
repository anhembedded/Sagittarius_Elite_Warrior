"""`EPIC-034D` — a `VenueAccountSnapshot` a test can start from.

@details A funded Spot Testnet account with a `BTCUSDT` book at 101, the key
allowed to trade. A test changes the one field it is about with `replace()`,
so the others stay what a working account has: a default that failed would
make every test that forgot to seed pass or fail for the wrong reason.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

READ_AT = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def a_venue_account_snapshot(
    source: AccountSource = AccountSource.SPOT_TESTNET, symbol: str = "BTCUSDT"
) -> VenueAccountSnapshot:
    return VenueAccountSnapshot(
        source=source,
        symbol=symbol,
        read_at=READ_AT,
        quote_asset="USDT",
        available=Decimal(900),
        holdings=(
            SpotHolding("USDT", Decimal(900), Decimal(100), Decimal("0.00000001")),
            SpotHolding("BTC", Decimal("0.5"), Decimal(0), Decimal("0.00000001")),
        ),
        commission=CommissionRate(symbol, Decimal("0.001"), Decimal("0.001")),
        can_trade=True,
        rules=SymbolOrderMetadata(
            symbol=symbol,
            status="TRADING",
            step_size=Decimal("0.00001"),
            tick_size=Decimal("0.01"),
            min_notional=Decimal(5),
            quantity_precision=None,
            price_precision=None,
            fetched_at=READ_AT,
        ),
        price=Decimal(101),
    )
