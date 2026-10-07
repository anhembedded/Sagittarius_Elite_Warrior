"""`EPIC-034D` — the `canTrade` flag of a Binance account payload.

Spot `GET /api/v3/account` and USD-M `GET /fapi/v2/account` both carry it. It
is the account's switch, not the key's permission list (that is
`GET /sapi/v1/account/apiRestrictions`, `EPIC-034E`), and it is `None` when the
payload has no boolean flag — never a guessed `True`.
"""

from __future__ import annotations

from typing import Any


def can_trade_of(account: dict[str, Any]) -> bool | None:
    flag = account.get("canTrade")
    return flag if isinstance(flag, bool) else None
