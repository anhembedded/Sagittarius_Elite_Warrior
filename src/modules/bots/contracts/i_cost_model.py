"""`EPIC-039G` — what trading costs a bot on one venue, in one place.

@details The one statement of what trading costs on a venue: Spot's answer is the maker and
taker rate with no funding; Futures' is the account's rates and the funding rate the exchange
reports now.

@par Today this is a seam, not yet a shared source
The Grid's checks still read the same fees from `ExchangeTerms`, and a test
(`test_futures_fees_come_from_the_account_and_set_the_break_even_step`) pins the two equal. The
port exists for the consumers that need funding over a horizon and cannot take it from the
terms: the Futures executor (`EPIC-039H`) and the Futures backtest (`EPIC-039K`). When one of
them reads it, the checks should move to it so that a fee has one reader (the `EPIC-037`
lesson).

@par Unknown is a value
A funding rate that could not be read is `None` from `funding_estimate`, never `0`
(`domain-truth-rule.md`, the `ExchangeSnapshot` pattern): a screen shows "unknown", and a
total built on it says what it lacks.

@par Extension cases
  · a second Futures market (Coin-M) - one more implementation, quoting in its own asset;
  · the backtest (`EPIC-039K`) - an implementation fed from recorded rates instead of the
    exchange's current one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from decimal import Decimal


class ICostModel(ABC):
    """The fees and funding one venue charges one symbol."""

    @abstractmethod
    def fees(self) -> tuple[Decimal, Decimal]:
        """@brief `(maker, taker)` as fractions of the traded notional: `0.001` is 0.1 %."""

    @abstractmethod
    def funding_estimate(self, position: Decimal, horizon: timedelta) -> Decimal | None:
        """@brief What holding `position` for `horizon` costs in funding, in the quote asset.
        @param position The position's signed notional in the quote asset: positive long,
        negative short.
        @return Positive when the position pays, negative when it earns; `Decimal(0)` on a
        venue with no funding, by definition; `None` when the venue has funding and its
        rate is unknown."""

    @abstractmethod
    def breakeven_step_fraction(self) -> Decimal:
        """@brief The step, as a fraction of the buy price, at which a completed cycle earns
        nothing: both legs rest, so both pay the maker fee (`step % - 2 x fee`)."""
