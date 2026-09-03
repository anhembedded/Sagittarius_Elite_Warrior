"""`BUG-091` — shared "unrecognized value -> named fallback, never a raised/
lost update" helpers for `OrderStatus`/`OrderType`/`TimeInForce`, used by
both order-payload parsers this app has (`user_data_event_parser.py`, the
websocket stream shape, and `futures_order_payload_mapper.py`, the REST
shape) — the same underlying risk in two different wire formats: Binance's
account-wide APIs can report a status/type this app's deliberately-narrow
enums (`OrderStatus`/`OrderType` — "add a member only when a real call
site needs it") have no name for yet, on an order this app did not itself
place (a manually-placed testnet order, an exchange-internal status).
Losing the whole update over an unrecognized field would leave this app
blind about a real order/position change; `OrderStatus.UNKNOWN`/
`OrderType.UNKNOWN` are the same "named catch-all" idiom
`OrderRejectionReason.UNKNOWN` already established in this app.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.time_in_force import TimeInForce


def order_status_or_unknown(raw: str) -> OrderStatus:
    """@brief `OrderStatus[raw]`, falling back to `OrderStatus.UNKNOWN`
    instead of raising `KeyError` on a status this app has no member for."""
    try:
        return OrderStatus[raw]
    except KeyError:
        return OrderStatus.UNKNOWN


def order_type_or_unknown(raw: str) -> OrderType:
    """@brief `OrderType[raw]`, falling back to `OrderType.UNKNOWN` instead
    of raising `KeyError` on a type this app has no member for."""
    try:
        return OrderType[raw]
    except KeyError:
        return OrderType.UNKNOWN


def time_in_force_or_none(raw: str | None) -> TimeInForce | None:
    """@brief `TimeInForce(raw)`, falling back to `None` ("not applicable"
    — `Order`'s own representation for a non-`LIMIT` order) on a value
    this app has no member for. `None`, not a dedicated `UNKNOWN` member:
    nothing branches on `time_in_force` for order identification/tracking
    the way it does on `status`/`order_type`, so there is no lost-tracking
    risk to guard against here."""
    if not raw:
        return None
    try:
        return TimeInForce(raw)
    except ValueError:
        return None
