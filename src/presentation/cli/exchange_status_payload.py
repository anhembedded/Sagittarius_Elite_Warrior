"""`ExchangeConnectionStatus` as the JSON-ready facts of `exchange-status` (`EPIC-038B`).

Schema `sew.exchange-status/1`. Every key is always present (`null` when the
value was never learned), so a script reads a field without checking it exists.
A field is added within version 1, never renamed or removed; a breaking change
is version 2 (`tests/unit/presentation/cli/test_exchange_status_report.py` pins
the key set).

Nothing here reads a credential: the status carries none (`ExchangeConnection
Status` holds a venue, balances and a failure kind), and
`test_no_secret_reaches_a_json_report` runs the command with a recognisable
fake secret in the environment and searches the output for it. Money is a
string (`"15000.00"`), never a float, for the reason `order_preview_to_dict`
already gives.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    RECV_WINDOW_MS,
)

SCHEMA_VERSION = 1


def _money(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _holding(holding: SpotHolding) -> dict[str, JsonValue]:
    return {
        "asset": holding.asset,
        "free": str(holding.free),
        "locked": str(holding.locked),
        "is_dust": holding.is_dust,
    }


def exchange_status_payload(status: ExchangeConnectionStatus) -> dict[str, JsonValue]:
    skew = status.server_time_skew_ms
    summary = status.summary
    futures = summary if isinstance(summary, FuturesAccountSummary) else None
    return {
        "venue": status.venue.value,
        "reachable": status.reachable,
        "failure": None if status.failure is None else status.failure.value,
        "server_time_skew_ms": skew,
        "clock_skew_within_recv_window": None
        if skew is None
        else abs(skew) < RECV_WINDOW_MS,
        "usdt_balance": _money(status.usdt_balance),
        "available_balance": None
        if summary is None
        else _money(summary.available_balance),
        "unrealized_pnl": None if futures is None else _money(futures.unrealized_pnl),
        "asset_mode": None if futures is None else futures.asset_mode.value,
        "position_mode": None
        if status.position_mode is None
        else status.position_mode.value,
        "margin_type": None if status.margin_type is None else status.margin_type.value,
        "open_position_count": status.open_position_count,
        "equity": _money(status.equity),
        "holdings": None
        if status.holdings is None
        else [_holding(h) for h in status.holdings],
        "can_trade": status.can_trade,
    }
