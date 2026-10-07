"""`BUG-170` — what a failed order submission, or a read of one, means.

A `BinanceAPIException` that carries an exchange code is an answer: the
exchange read the request and refused it (`OrderRejectedByExchangeError`).
A non-JSON answer (a gateway's `502` page) and a failed transport are not
answers: a live order may have reached the exchange before the reply was lost,
so they raise `OrderOutcomeUnknownError`, which the execute handler resolves
by reading the order back by its client order id. A `VALIDATE_ONLY` send never
creates an order, so there nothing can be live and the old words stay.

Both trading clients (Futures and Spot) call these two functions, so the
decision exists once.
"""

from __future__ import annotations

import logging
from typing import NoReturn

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_error_translator import (
    translate_binance_error,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    describe_failure,
    is_non_json_answer,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)

logger = logging.getLogger("App.TradingAdapter")

#: A failure that says nothing about whether the request arrived.
_UNREADABLE = (BinanceRequestException, RequestException)

#: What a send or a read of one order can raise that this module words.
SEND_FAILURES = (BinanceAPIException, *_UNREADABLE)

#: Binance's "Order does not exist.": the read's answer for an id it never saw.
ORDER_DOES_NOT_EXIST_CODE = -2013


#: Binance's own codes that say the execution status is unknown: `-1006`
#: ("Execution status unknown", an unexpected answer from its message bus) and
#: `-1007` ("Timeout waiting for response from backend server. Send status
#: unknown"). They carry a code, but they are no refusal.
_STATUS_UNKNOWN_CODES = frozenset({-1006, -1007})


def is_unreadable_answer(exc: BaseException) -> bool:
    """Whether `exc` leaves open that the request reached the exchange."""
    return (
        is_non_json_answer(exc)
        or isinstance(exc, _UNREADABLE)
        or (isinstance(exc, BinanceAPIException) and exc.code in _STATUS_UNKNOWN_CODES)
    )


def raise_for_failed_send(order: Order, exc: Exception, *, live: bool) -> NoReturn:
    """@raise OrderOutcomeUnknownError A live send with no readable answer.
    @raise OrderRejectedByExchangeError An answer the exchange gave.
    @raise Exception `exc` itself, a transport failure of a `VALIDATE_ONLY` send.
    """
    if live and is_unreadable_answer(exc):
        reason = describe_failure(exc, other=_transport_words)
        logger.error(
            "Order %s on %s: no readable answer from the exchange, it may be live: %s [order-outcome-unknown]",
            order.client_order_id,
            order.symbol,
            reason,
        )
        raise OrderOutcomeUnknownError(
            order.symbol, order.client_order_id, reason
        ) from exc
    if isinstance(exc, BinanceAPIException):
        raise OrderRejectedByExchangeError(
            translate_binance_error(exc), describe_failure(exc)
        ) from exc
    raise exc


def raise_for_failed_read(symbol: str, client_order_id: str, exc: Exception) -> None:
    """Words a failed read of one order. It returns when the exchange answered
    that it has no such order; anything unreadable is `OrderOutcomeUnknownError`.

    @raise OrderRejectedByExchangeError The exchange refused the read itself.
    """
    if isinstance(exc, BinanceAPIException) and exc.code == ORDER_DOES_NOT_EXIST_CODE:
        return
    if is_unreadable_answer(exc):
        raise OrderOutcomeUnknownError(
            symbol, client_order_id, describe_failure(exc, other=_transport_words)
        ) from exc
    if isinstance(exc, BinanceAPIException):
        raise OrderRejectedByExchangeError(
            translate_binance_error(exc), describe_failure(exc)
        ) from exc
    raise exc


def _transport_words(exc: BaseException) -> str:
    """A transport failure as its class name; the library's text can carry a URL."""
    return f"the exchange could not be reached ({type(exc).__name__})"
