"""`BUG-247` — what a protective-stop read that fails says, and how often.

A pause of a minute fails the same reads on every beat of every bot, and the pause itself is
told once by the venue's gate (`ExchangeCallPolicy`). So the first failed position read of a
run is a WARNING and the beats after it are DEBUG until a read works (`UnreadStreak`), and an
open-stops read that meets the pause is DEBUG (`log_unread_stops`), anything else an ERROR with its
traceback.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)


class UnreadStreak:
    """The level a failed read is logged at: WARNING for the first of a run, DEBUG after it."""

    def __init__(self) -> None:
        self._told = False

    def failed(self) -> int:
        """The level to tell a failed read at."""
        level = logging.DEBUG if self._told else logging.WARNING
        self._told = True
        return level

    def tell_position_unread(self, logger: logging.Logger, bot_id: str) -> None:
        """The position could not be read: WARNING for the first of a run, DEBUG after it."""
        logger.log(
            self.failed(),
            "Bot %s: the position could not be read, so the protective stop is not "
            "looked at this time [protective-stop]",
            bot_id,
        )

    def cleared(self) -> None:
        """A read worked: the run is over."""
        self._told = False


def log_unread_stops(logger: logging.Logger, failure: Exception, bot_id: str) -> None:
    """The open protective stops could not be read: DEBUG for the exchange's pause, else ERROR."""
    if isinstance(failure, ExchangeRateLimitedError):
        logger.debug(
            "Bot %s: the open protective stops could not be read [protective-stop]",
            bot_id,
        )
    else:
        logger.error(
            "Bot %s: the open protective stops could not be read [protective-stop]",
            bot_id,
            exc_info=failure,
        )
