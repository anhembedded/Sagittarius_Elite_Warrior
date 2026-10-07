"""`BUG-170` — an order's submission whose outcome the app could not read.

@details A rejection (`OrderRejectedByExchangeError`) means the exchange read
the request and refused it: nothing is live. An answer that is not an API reply
(a gateway's HTML page) or a failed transport says nothing about that: the
order may have reached the exchange and be live. The adapter raises
`OrderOutcomeUnknownError` for that case, and the execute handler resolves it
by asking the exchange for the order by its client order id, which the app
generated before sending (`client_order_id.py`). A caller then sees one of
three truths: the order is placed (an ordinary result), it is not placed
(`OrderNotPlacedError`), or it is still unknown (`OrderOutcomeUnknownError`,
with the reason): the one a caller must never treat as "not placed".
"""

from __future__ import annotations


class OrderOutcomeUnknownError(Exception):
    """The order may be live on the exchange: its submission got no readable
    answer, and so far nothing says whether it arrived."""

    def __init__(self, symbol: str, client_order_id: str, reason: str) -> None:
        super().__init__(
            f"order {client_order_id} on {symbol}: outcome unknown, it may be "
            f"live on the exchange ({reason})"
        )
        self.symbol = symbol
        self.client_order_id = client_order_id
        self.reason = reason


class OrderNotPlacedError(Exception):
    """The exchange answered that it holds no order with this client order id,
    after a submission whose own answer was unreadable: nothing is live."""

    def __init__(self, symbol: str, client_order_id: str, reason: str) -> None:
        super().__init__(
            f"order {client_order_id} on {symbol} was not placed ({reason})"
        )
        self.symbol = symbol
        self.client_order_id = client_order_id
        self.reason = reason
