"""`EPIC-021E` — the app-generated idempotency key for one live order.

@details `python-binance`'s own `futures_create_order` auto-generates a
`newClientOrderId` when the caller doesn't supply one (`client.py:7657-
7658` of that library). Accepting that default would mean this app never
learns its own order's id before sending it — so after a mid-flight
disconnect there would be no way to ask the exchange "did my order go
through". This app instead always generates and records its own id
*before* sending, with a recognizable prefix: the same shape that makes
resending the same `client_order_id` after a timeout an idempotent retry
rather than a second order.
"""

from __future__ import annotations

import uuid
from typing import NewType

#: Distinct from a bare `str` so a call site can't pass an arbitrary string
#: (a symbol, an exchange order id) where an app-generated id belongs.
ClientOrderId = NewType("ClientOrderId", str)

#: Binance's own limit on `newClientOrderId` length. Mirrored here as a
#: literal rather than imported from `binance` — this module must stay free
#: of any exchange-SDK import (`architecture-rule.md` §3).
MAX_CLIENT_ORDER_ID_LENGTH = 36

_PREFIX = "SEW-"
_SUFFIX_LENGTH = 12


def generate_client_order_id() -> ClientOrderId:
    """@brief Generates one new, unique, app-prefixed client order id.

    @details `SEW-` (Sagittarius Elite Warrior) + 12 lowercase hex chars —
    16 characters total, well under Binance's 36-char limit, matching this
    epic's own worked example (`SEW-a91f4c72e0b8`).
    """
    suffix = uuid.uuid4().hex[:_SUFFIX_LENGTH]
    return ClientOrderId(f"{_PREFIX}{suffix}")
