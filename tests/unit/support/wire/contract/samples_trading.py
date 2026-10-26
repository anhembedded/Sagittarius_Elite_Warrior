"""`EPIC-047A` — a full and a minimal instance of the trading contracts the link carries.

*Full* fills every optional field and every tuple; *minimal* leaves each optional `None` and each
tuple empty, so a codec that silently defaults an optional passes one and fails the other.
The figures are deliberately awkward as floats (`0.1`, `1E-8`, trailing zeros).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    PercentPriceBand,
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

#: A moment with an offset the wire must keep, and one in UTC.
BANGKOK = datetime(2026, 10, 26, 9, 30, 15, 123456, tzinfo=timezone(timedelta(hours=7)))
UTC_NOON = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

D = Decimal


def full_connect_failure() -> ConnectFailure:
    return ConnectFailure(
        AccountSource.SPOT_MAINNET,
        ConnectionFailureKind.RATE_LIMITED,
        "the price",
        "the exchange asked for a pause",
    )


def minimal_connect_failure() -> ConnectFailure:
    return ConnectFailure(
        AccountSource.FUTURES_TESTNET, ConnectionFailureKind.NOT_CONFIGURED
    )


def full_symbol_setting() -> FuturesSymbolSetting:

    return FuturesSymbolSetting("BTCUSDT", 20, MarginType.ISOLATED, D("5000000.50"))


def full_brackets() -> LeverageBrackets:
    return LeverageBrackets(
        "BTCUSDT",
        (
            LeverageBracket(1, 125, D(0), D("50000"), D("0.004"), D(0)),
            LeverageBracket(2, 100, D("50000"), D("250000"), D("0.005"), D("50.00")),
        ),
    )


def minimal_brackets() -> LeverageBrackets:
    return LeverageBrackets("BTCUSDT", (LeverageBracket(1, 1, D(0), D(1), D(0), D(0)),))


def full_budget_caps() -> OwnerBudgetCaps:
    return OwnerBudgetCaps(40, timedelta(milliseconds=250, microseconds=7), 30)


def minimal_budget_caps() -> OwnerBudgetCaps:
    return OwnerBudgetCaps(1, timedelta(0), 1)


def full_earlier_runs() -> EarlierRunsInventory:
    return EarlierRunsInventory(D("0.00000100"), D("12.3400"), BANGKOK, "")


def minimal_earlier_runs() -> EarlierRunsInventory:
    return EarlierRunsInventory()


def full_venue_account() -> VenueAccountSnapshot:
    return VenueAccountSnapshot(
        source=AccountSource.SPOT_TESTNET,
        symbol="BTCUSDT",
        read_at=BANGKOK,
        quote_asset="USDT",
        available=D("1000.10"),
        holdings=(
            SpotHolding("BTC", D("0.1"), D("0.2"), D("1E-8")),
            SpotHolding("USDT", D(5), D(0), D(0)),
        ),
        commission=CommissionRate("BTCUSDT", D("0.001"), D("0.00075")),
        can_trade=True,
        rules=SymbolOrderMetadata(
            "BTCUSDT",
            "TRADING",
            D("0.00001"),
            D("0.01"),
            D("5"),
            5,
            2,
            UTC_NOON,
            D("0.00002"),
            PercentPriceBand(D("0.2"), D("5"), D("0.2"), D("5")),
        ),
        price=D("67000.5"),
        server_time_skew_ms=-120,
    )


def minimal_venue_account() -> VenueAccountSnapshot:
    return VenueAccountSnapshot(
        source=AccountSource.FUTURES_TESTNET,
        symbol="ETHUSDT",
        read_at=UTC_NOON,
        quote_asset="USDT",
        available=D(0),
        holdings=(),
        commission=CommissionRate("ETHUSDT", D(0), D(0)),
        can_trade=None,
        rules=SymbolOrderMetadata(
            "ETHUSDT", "BREAK", D(1), D(1), D(0), None, None, UTC_NOON
        ),
        price=D(1),
    )
