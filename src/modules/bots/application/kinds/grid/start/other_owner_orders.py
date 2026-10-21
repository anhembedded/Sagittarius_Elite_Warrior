"""`BUG-259` — the account's orders on a symbol that carry a bot tag this data root does not hold.

Each data root enforces "one active bot per symbol" only for itself. A second copy of the app on
the same account (a VPS host beside a desktop) trading the same symbol is invisible to it, yet in
one-way mode Binance nets both bots into one position, and a close-position stop of one closes the
other's. A bot's orders carry its tag (`SEW-<tag>-...`, `client_order_id.tag_of`); a tag that no
bot of this data root holds belongs to another owner. Untagged orders are a person's and are not
judged here. The registration's `FOREIGN_POSITION` covers a position beside a flat bot; this
covers the orders, which are there before and after any position.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order


def other_owner_tags(
    orders: Iterable[Order], symbol: str, known_tags: frozenset[str]
) -> dict[str, int]:
    """Each tag in `orders` on `symbol` that is not in `known_tags`, with its order count."""
    found = Counter(
        tag
        for order in orders
        if order.symbol == symbol
        and (tag := tag_of(str(order.client_order_id))) is not None
        and tag not in known_tags
    )
    return dict(found)


def other_owner_refusal(symbol: str, tags: dict[str, int], *, on_spot: bool) -> str:
    """The refusal in the user's words. A position venue nets both bots into one position; Spot
    has no position, but both bots would trade one balance of the symbol's assets."""
    held = ", ".join(f"{tag} ({count} order(s))" for tag, count in sorted(tags.items()))
    effect = (
        "and both bots would trade the same balance of its assets"
        if on_spot
        else "and Binance nets both bots into one position"
    )
    return (
        f"{symbol} has open orders of a bot this app does not hold: {held}. Another copy of the "
        f"app on this account (a VPS host, a second desktop) is trading it, {effect}. Stop that "
        "bot or cancel its orders, or pick another symbol or account"
    )
