"""The statuses and previews whose printed text is pinned byte for byte (`EPIC-038B`).

One table per command, name -> the value the formatter is given. The expected
text sits beside it in `golden/<command>__<name>.txt`, written from the
formatter as it was **before** the report renderer replaced its string
building, so a byte that moves is a visible diff, not a re-recorded fixture.

`test_golden_cases_cover_every_failure_kind` keeps the table from going stale:
a `ConnectionFailureKind` added without a golden case fails there.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

GOLDEN_DIR = Path(__file__).parent / "golden"


def golden_text(command: str, name: str) -> str:
    return (GOLDEN_DIR / f"{command}__{name}.txt").read_text(encoding="utf-8")


def _futures(**overrides: object) -> ExchangeConnectionStatus:
    fields: dict[str, object] = {
        "venue": TradingVenue.FUTURES_TESTNET,
        "reachable": True,
        "failure": None,
        "server_time_skew_ms": 134,
        "usdt_balance": Decimal("15000.00"),
        "position_mode": PositionMode.ONE_WAY,
        "margin_type": MarginType.CROSSED,
        "open_position_count": 0,
    }
    fields.update(overrides)
    return ExchangeConnectionStatus(**fields)  # type: ignore[arg-type]


def _unreachable(
    kind: ConnectionFailureKind, venue: TradingVenue = TradingVenue.FUTURES_TESTNET
) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=venue,
        reachable=False,
        failure=kind,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        retry_after=(
            timedelta(seconds=60)
            if kind is ConnectionFailureKind.RATE_LIMITED
            else None
        ),
    )


def _spot(**overrides: object) -> ExchangeConnectionStatus:
    fields: dict[str, object] = {
        "venue": TradingVenue.SPOT_TESTNET,
        "reachable": True,
        "failure": None,
        "server_time_skew_ms": -12,
        "usdt_balance": Decimal("9876.5"),
        "position_mode": None,
        "margin_type": None,
        "open_position_count": None,
        "holdings": (
            SpotHolding("USDT", Decimal("9876.5"), Decimal(0), Decimal("0.01")),
            SpotHolding("BTC", Decimal("0.5"), Decimal("0.1"), Decimal("0.00001")),
            SpotHolding("DOGE", Decimal("0.000001"), Decimal(0), Decimal("0.01")),
        ),
        "equity": Decimal("41000.25"),
    }
    fields.update(overrides)
    return ExchangeConnectionStatus(**fields)  # type: ignore[arg-type]


def _futures_summary(asset_mode: AssetMode) -> FuturesAccountSummary:
    return FuturesAccountSummary(
        venue=TradingVenue.FUTURES_TESTNET,
        available_balance=Decimal("12345.67"),
        equity=Decimal("15100.00"),
        wallet_balance=Decimal("15000.00"),
        margin_balance=Decimal("15100.00"),
        unrealized_pnl=Decimal("-100.5"),
        position_mode=PositionMode.ONE_WAY,
        asset_mode=asset_mode,
    )


EXCHANGE_STATUS_CASES: dict[str, ExchangeConnectionStatus] = {
    "futures_success_without_summary": _futures(),
    "futures_success_single_asset": _futures(
        summary=_futures_summary(AssetMode.SINGLE_ASSET), open_position_count=2
    ),
    "futures_success_multi_assets": _futures(
        summary=_futures_summary(AssetMode.MULTI_ASSETS)
    ),
    "futures_skew_beyond_recv_window": _futures(server_time_skew_ms=6000),
    "futures_unknown_fields": _futures(
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    ),
    "futures_hedge_mode_with_balance": _futures(
        failure=ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED,
        position_mode=PositionMode.HEDGE,
    ),
    "futures_hedge_mode_without_balance": _futures(
        failure=ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED, usdt_balance=None
    ),
    **{
        f"futures_{kind.name.lower()}": _unreachable(kind)
        for kind in ConnectionFailureKind
    },
    "spot_not_configured": _unreachable(
        ConnectionFailureKind.NOT_CONFIGURED, TradingVenue.SPOT_TESTNET
    ),
    "spot_key_rejected": _unreachable(
        ConnectionFailureKind.KEY_REJECTED, TradingVenue.SPOT_TESTNET
    ),
    "spot_clock_skew": _unreachable(
        ConnectionFailureKind.CLOCK_SKEW, TradingVenue.SPOT_TESTNET
    ),
    "spot_success_with_holdings": _spot(),
    "spot_success_without_holdings": _spot(holdings=()),
    "spot_success_unknown_equity": _spot(equity=None, server_time_skew_ms=None),
}


def _preview(
    quantity: str, raw: str, notional: str, check: NotionalCheck
) -> OrderPreview:
    order = Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal(quantity),
    )
    return OrderPreview(
        order=order,
        raw_quantity=Decimal(raw),
        estimated_notional=Decimal(notional),
        min_notional=Decimal(100),
        step_size=Decimal("0.001"),
        notional_check=check,
    )


ORDER_PREVIEW_CASES: dict[str, OrderPreview] = {
    "ready_rounded_down": _preview(
        "0.013", "0.0137", "832.00", NotionalCheck.SUFFICIENT
    ),
    "ready_exact": _preview("0.013", "0.013", "832.00", NotionalCheck.SUFFICIENT),
    "rejected_min_notional": _preview(
        "0.001", "0.001", "64.00", NotionalCheck.INSUFFICIENT
    ),
}
