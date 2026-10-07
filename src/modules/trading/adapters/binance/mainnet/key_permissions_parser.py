"""`EPIC-034E` — `GET /sapi/v1/account/apiRestrictions` as `KeyPermissions`.

@details Binance answers `{"enableReading": true, "enableWithdrawals": false,
"enableSpotAndMarginTrading": true, ...}`. Each of the three flags the app
decides on must be a boolean in the answer: a missing or non-boolean flag is
an error, never a `False`, because "cannot withdraw" is the one thing a
read-only account must be sure of (`code/errors.md` #7). The Margin, Futures
and transfer flags (`KeyPermissions`' optional ones) are `None` when the answer
leaves them out: they decide what the screen says, not whether a key is kept.
"""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)

_READING = "enableReading"
_SPOT_TRADING = "enableSpotAndMarginTrading"
_WITHDRAWALS = "enableWithdrawals"
_MARGIN = "enableMargin"
_FUTURES = "enableFutures"
_INTERNAL_TRANSFER = "enableInternalTransfer"
_UNIVERSAL_TRANSFER = "permitsUniversalTransfer"


def _flag(payload: dict[str, Any], name: str) -> bool:
    value = payload[name]
    if not isinstance(value, bool):
        raise TypeError(f"apiRestrictions {name} is {value!r}, not a boolean")
    return value


def _optional_flag(payload: dict[str, Any], *names: str) -> bool | None:
    """On when any named flag is on; `None` when none of them was reported;
    off only when every one was reported and off. A flag that is there but not
    a boolean is an error all the same."""
    reported = [_flag(payload, name) for name in names if name in payload]
    if not reported:
        return None
    if len(reported) < len(names) and not any(reported):
        return None
    return any(reported)


def parse_key_permissions(payload: dict[str, Any]) -> KeyPermissions:
    """@throws KeyError One of the three decisive flags is missing.
    @throws TypeError A flag is not a boolean."""
    return KeyPermissions(
        can_read=_flag(payload, _READING),
        can_trade_spot=_flag(payload, _SPOT_TRADING),
        can_withdraw=_flag(payload, _WITHDRAWALS),
        can_trade_margin=_optional_flag(payload, _MARGIN),
        can_trade_futures=_optional_flag(payload, _FUTURES),
        can_transfer=_optional_flag(payload, _INTERNAL_TRANSFER, _UNIVERSAL_TRANSFER),
    )
