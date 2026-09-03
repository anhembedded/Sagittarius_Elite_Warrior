"""`EPIC-021E` — the post-send lifecycle of one live order on the exchange.

@details Deliberately narrower than a bare `Enum` would suggest: alongside
the values, this module owns the transition matrix (`is_valid_transition`)
so "an order cannot go from `FILLED` back to `NEW`" is enforced by a
function every caller must go through, not a convention someone has to
remember. `NEW`/`PARTIALLY_FILLED` also have exactly one path forward
each that skips ahead correctly (`NEW` -> `FILLED` directly, for a market
order that fills whole); this file is the one place that shape is written
down.
"""

from __future__ import annotations

from enum import Enum


class OrderStatus(str, Enum):
    """@brief Where one order sent to the exchange currently stands.

    @details `NEW` is also this app's own pre-send default (`Order.status`
    defaults to it) — an order is `NEW` the moment this app constructs it,
    before the exchange has seen it at all; the exchange only ever confirms
    or advances that status, never assigns it from scratch.
    """

    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    #: `BUG-091` — the honest answer for a Binance status this app's
    #: parsers (`user_data_event_parser.py`, `futures_order_payload_
    #: mapper.py`) don't have a narrower name for, e.g. `EXPIRED_IN_MATCH`
    #: on an order this app did not itself construct (a manually-placed
    #: testnet order the account-wide user data stream still reports).
    #: Same "named catch-all, never a raised/lost update" idiom
    #: `OrderRejectionReason.UNKNOWN` already established in this app.
    UNKNOWN = "unknown"


#: `FILLED`/`CANCELED`/`REJECTED`/`EXPIRED` are terminal — empty target sets.
#: An exchange order that reached one of these cannot un-happen; there is no
#: real-world event that would justify e.g. `FILLED` -> `NEW`.
_VALID_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.NEW: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.EXPIRED}
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
    #: Not terminal — the opposite of the four above: an `UNKNOWN` status
    #: means this app couldn't name what the exchange reported, not that
    #: the order is actually done. A later update carrying a real status
    #: must always be accepted as a correction.
    OrderStatus.UNKNOWN: frozenset(
        {
            OrderStatus.NEW,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
    ),
}


def is_valid_transition(current: OrderStatus, target: OrderStatus) -> bool:
    """@brief Whether an order in `current` status may move to `target`.
    @details A terminal status has no valid target — not even itself:
    re-observing an unchanged terminal status is the caller's idempotency
    concern, not a "transition" this function should bless.
    """
    return target in _VALID_TRANSITIONS[current]
