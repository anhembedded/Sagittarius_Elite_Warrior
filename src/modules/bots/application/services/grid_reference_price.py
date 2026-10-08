"""`EPIC-035J` (M1) — the price a Grid acts on, with the moment it was heard.

Held in the bot's run context and touched only on the bot's worker, like
`GridPriceAge`. Two sources, one rule:

  · **a tick** is noted with the monotonic moment it was heard;
  · **the book** is read when no price is held, or the held one is older than
    `REFERENCE_PRICE_MAX_AGE_SECONDS`, and the reading is noted the same way.

`current()` is the price for any use that is not an order's own limit: a resume
proposal, a stop's slices, the dust check, an opening plan. `fresh()` always reads
the book, for the moment just before a confirmed ladder is laid.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    FreshPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.reference_price import (
    REFERENCE_PRICE_MAX_AGE_SECONDS,
    price_is_too_old,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)


class GridReferencePrice:
    """A price and when it was heard, refreshed from the book when it is old."""

    def __init__(
        self, clock: IMonotonicClock, read_book_price: Callable[[], Decimal]
    ) -> None:
        self._clock = clock
        self._read_book_price = read_book_price
        self._price: Decimal | None = None
        self._heard_at = 0.0

    def note_tick(self, price: Decimal) -> None:
        self._remember(price)

    def current(self) -> Decimal:
        """The held price while it is young enough, else the book's.

        @raise FreshPriceUnavailableError The venue did not answer."""
        if self._price is None or price_is_too_old(
            self._heard_at, self._clock.seconds(), REFERENCE_PRICE_MAX_AGE_SECONDS
        ):
            return self.fresh()
        return self._price

    def fresh(self) -> Decimal:
        """The book's price now, held from here on.

        @raise ExchangeRateLimitedError The exchange asked for a pause: the bot
        halts for it or waits it out, as for any other call it made.
        @raise FreshPriceUnavailableError The venue did not answer."""
        try:
            price = self._read_book_price()
        except FreshPriceUnavailableError as unavailable:
            if unavailable.retry_after is None:
                raise
            raise ExchangeRateLimitedError(
                unavailable.retry_after, banned=False, raw_message=str(unavailable)
            ) from unavailable
        self._remember(price)
        return price

    def _remember(self, price: Decimal) -> None:
        self._price = price
        self._heard_at = self._clock.seconds()
