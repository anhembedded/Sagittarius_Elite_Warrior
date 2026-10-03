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

@par The bot tag (`EPIC-029A`, ADR D5)
A bot's orders carry its six-character tag: `SEW-{tag}-{hex10}`, 21 characters.
The tag is the bot's id (`[a-z0-9]`, six characters), so a bot recognises its
own orders in account-wide reads and in history, and trading attributes fills
and inventory to it. Untagged ids keep the original `SEW-{hex12}` shape, so no
existing id, stored or on the exchange, changes meaning. Trading still owns id
generation: a caller supplies the tag, never the id.
"""

from __future__ import annotations

import re
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
_TAGGED_SUFFIX_LENGTH = 10
CLIENT_ORDER_TAG_LENGTH = 6
_TAG_PATTERN = re.compile(rf"[a-z0-9]{{{CLIENT_ORDER_TAG_LENGTH}}}")
_TAGGED_ID_PATTERN = re.compile(
    rf"{_PREFIX}(?P<tag>[a-z0-9]{{{CLIENT_ORDER_TAG_LENGTH}}})-"
    rf"[0-9a-f]{{{_TAGGED_SUFFIX_LENGTH}}}"
)


class InvalidClientOrderTagError(ValueError):
    """A client order tag that is not six characters of `[a-z0-9]`."""

    def __init__(self, tag: str) -> None:
        super().__init__(
            f"A client order tag is {CLIENT_ORDER_TAG_LENGTH} characters of "
            f"[a-z0-9], got {tag!r}"
        )
        self.tag = tag


def validate_client_order_tag(tag: str | None) -> None:
    """@raise InvalidClientOrderTagError `tag` is set and not `[a-z0-9]{6}`."""
    if tag is not None and not _TAG_PATTERN.fullmatch(tag):
        raise InvalidClientOrderTagError(tag)


def generate_client_order_id(tag: str | None = None) -> ClientOrderId:
    """@brief Generates one new, unique, app-prefixed client order id.

    @details Untagged: `SEW-` (Sagittarius Elite Warrior) + 12 lowercase hex
    chars, 16 characters, matching `EPIC-021E`'s worked example
    (`SEW-a91f4c72e0b8`). Tagged (`EPIC-029A`): `SEW-{tag}-` + 10 hex chars,
    21 characters, still well under Binance's 36.

    @raise InvalidClientOrderTagError `tag` is not `[a-z0-9]{6}`.
    """
    validate_client_order_tag(tag)
    if tag is None:
        return ClientOrderId(f"{_PREFIX}{uuid.uuid4().hex[:_SUFFIX_LENGTH]}")
    suffix = uuid.uuid4().hex[:_TAGGED_SUFFIX_LENGTH]
    return ClientOrderId(f"{_PREFIX}{tag}-{suffix}")


def tag_of(client_order_id: str) -> str | None:
    """The bot tag inside a client order id, or `None` for an untagged or
    foreign id. How trading attributes an account-wide read to an owner."""
    match = _TAGGED_ID_PATTERN.fullmatch(client_order_id)
    return match.group("tag") if match else None
