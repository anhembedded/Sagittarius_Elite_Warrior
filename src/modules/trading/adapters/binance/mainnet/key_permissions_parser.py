"""`EPIC-034` D5 — `GET /sapi/v1/account/apiRestrictions` as `KeyPermissions`.

@details Binance answers `{"enableReading": true, "enableWithdrawals": false,
"enableSpotAndMarginTrading": true, ...}`. Each of the three flags the gate
decides on must be a boolean in the answer: a missing or non-boolean flag is an
error, never a `False`. The answer's other flags (Margin, Futures, transfers) are
not read: they decide nothing the gate does.
"""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)

_READING = "enableReading"
_SPOT_TRADING = "enableSpotAndMarginTrading"
_WITHDRAWALS = "enableWithdrawals"


def _flag(payload: dict[str, Any], name: str) -> bool:
    value = payload[name]
    if not isinstance(value, bool):
        raise TypeError(f"apiRestrictions {name} is {value!r}, not a boolean")
    return value


def parse_key_permissions(payload: dict[str, Any]) -> KeyPermissions:
    """@throws KeyError One of the three flags is missing.
    @throws TypeError A flag is not a boolean."""
    return KeyPermissions(
        can_read=_flag(payload, _READING),
        can_trade_spot=_flag(payload, _SPOT_TRADING),
        can_withdraw=_flag(payload, _WITHDRAWALS),
    )
