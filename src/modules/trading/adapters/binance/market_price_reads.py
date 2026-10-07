"""`EPIC-028O` — what the book-ticker and mark-price readers share: turning
every failure of a public read into the port's one error, and reading a
`bookTicker` answer, whose shape both venues share.

@details `bookTicker?symbol=` answers `{symbol, bidPrice, bidQty, askPrice,
askQty}` on Spot and the same plus `time` on USD-M Futures, per Binance's
documented APIs; not re-verified against a live call (egress to
`*.binance.*` is blocked in this sandbox).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    describe_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)

#: What a public read can raise from the SDK, the network or a malformed
#: payload.
_READ_FAILURES = (
    BinanceAPIException,
    BinanceRequestException,
    RequestException,
    KeyError,
    TypeError,
    ValueError,
    InvalidOperation,
)


@contextmanager
def market_price_answer(what: str) -> Iterator[None]:
    """Translates every failure inside the block into
    `MarketPriceUnavailableError`, naming `what` was read."""
    try:
        yield
    except _READ_FAILURES as exc:
        raise MarketPriceUnavailableError(
            f"{what} could not be read: {describe_failure(exc, repr)}"
        ) from exc


def parse_book_ticker(answer: dict[str, Any], symbol: str) -> BestBidAsk:
    """@return The best bid and ask of a `bookTicker` answer for `symbol`.
    @throws ValueError The answer is for another symbol."""
    if answer["symbol"] != symbol:
        raise ValueError(f"bookTicker answered {answer['symbol']}, not {symbol}")
    return BestBidAsk(
        symbol=symbol,
        bid_price=Decimal(str(answer["bidPrice"])),
        bid_quantity=Decimal(str(answer["bidQty"])),
        ask_price=Decimal(str(answer["askPrice"])),
        ask_quantity=Decimal(str(answer["askQty"])),
    )
