"""`EPIC-039H` — the price a position venue's stop loss and take profit are judged on.

@details A leveraged position is valued, margined and liquidated at the exchange's mark price,
not at the last trade: a stop loss placed on the last price can fire on a wick that never touched
the mark, or miss a move the mark made. A Grid on a position venue therefore judges its exits on
the mark (`IExposureCloser`'s sibling joint; Spot has none and keeps judging the streamed last
price and the range it traded in, `BUG-191`).

The mark is read, not streamed: it is a smoothed index, so a wick between two reads is rare and
what liquidates is the mark of the moment. The price paid is the read's cadence (the price watch's
beat, `CHECK_EVERY_SECONDS`): an exit fires up to one beat after the mark crossed.

Plausible extensions, each a local change: a reader fed by the `@markPrice` stream is one more
implementation of `IMarkSource` that answers its last frame; a Coin-M venue is the same port with
its own reader.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal


class MarkReadError(Exception):
    """The mark price could not be read; it says nothing about where the price is."""


class IMarkSource(ABC):
    @abstractmethod
    def read(self) -> Decimal:
        """@return The bot's symbol's mark price now.
        @raise MarkReadError The exchange did not answer, or reports no mark price."""
