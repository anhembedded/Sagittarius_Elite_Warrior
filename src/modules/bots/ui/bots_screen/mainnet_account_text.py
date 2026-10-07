"""`EPIC-034E` — what the Mainnet account window says, as plain lines.

Each number is written by the application's formatter, as every figure of the
Bots mode is. Pure, so each sentence is tested without a widget.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.connect_failure_words import (
    error_cause,
    failure_cause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

TITLE = AccountSource.SPOT_MAINNET_READONLY.venue_title
READING = "Reading the account…"
#: Said whenever the key can do more than read: the app reads only, so the
#: safest key for it is one that cannot.
ADVICE_READ_ONLY_KEY = (
    "This key can do more than read ({}). The app only reads it and never "
    "places an order, but create a read-only key (reading only, everything else "
    "off) and use that instead."
)
UNKNOWN_BEYOND_READING = (
    "The exchange did not say whether this key can trade Margin or Futures or "
    "transfer between accounts. Check its restrictions on Binance."
)


@dataclass(frozen=True, slots=True)
class MainnetAccountText:
    headline: str
    lines: tuple[str, ...] = ()


def reading_text() -> MainnetAccountText:
    return MainnetAccountText(f"{TITLE}: {READING}")


def failure_text(failure: ConnectFailure) -> MainnetAccountText:
    return MainnetAccountText(f"{TITLE}: not connected", (failure_cause(failure),))


def error_text(error: str) -> MainnetAccountText:
    return MainnetAccountText(f"{TITLE}: not connected", (error_cause(error),))


def account_text(snapshot: VenueAccountSnapshot) -> MainnetAccountText:
    lines = [
        _key_line(snapshot.key_permissions),
        *_advice(snapshot.key_permissions),
        f"Available to spend: {_money(snapshot.available)} {snapshot.quote_asset}",
        (
            f"Fees: maker {_percent(snapshot.commission.maker)}, "
            f"taker {_percent(snapshot.commission.taker)}"
        ),
        _orders_line(snapshot.open_order_count),
        "Balances:",
        *(
            f"  {holding.asset}: {_quantity(holding.free)} free, "
            f"{_quantity(holding.locked)} in orders"
            for holding in snapshot.holdings
        ),
    ]
    return MainnetAccountText(f"{TITLE}: Connected", tuple(lines))


def _key_line(permissions: KeyPermissions | None) -> str:
    if permissions is None:
        return "Key permissions: not read"
    return (
        "Key: "
        f"{'can' if permissions.can_read else 'cannot'} read, "
        f"{'can' if permissions.can_trade_spot else 'cannot'} trade Spot, "
        f"{'can' if permissions.can_withdraw else 'cannot'} withdraw"
    )


def _advice(permissions: KeyPermissions | None) -> tuple[str, ...]:
    if permissions is None:
        return ()
    if permissions.beyond_reading:
        return (ADVICE_READ_ONLY_KEY.format(", ".join(permissions.beyond_reading)),)
    if not permissions.is_read_only:
        return (UNKNOWN_BEYOND_READING,)
    return ()


def _orders_line(count: int | None) -> str:
    return "Open orders: not read" if count is None else f"Open orders: {count}"


def _money(value: Decimal) -> str:
    return write_value(ColumnKind.MONEY, float(value))


def _quantity(value: Decimal) -> str:
    return write_value(ColumnKind.QUANTITY, float(value))


def _percent(rate: Decimal) -> str:
    return write_value(ColumnKind.PERCENT, float(rate * 100))
