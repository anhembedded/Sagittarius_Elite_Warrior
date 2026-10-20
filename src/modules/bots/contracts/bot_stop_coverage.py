"""`EPIC-038M` (decision O12) - whether a bot's position stands under a protective stop on the exchange.

@details The one question the `run` host asks of a bot before it leaves a position behind: does a stop
on the exchange cover it **now**? The answer is read from the exchange (`IExposureProtection.read_coverage`),
never from the bot's own record, which can say a stop stands that was cancelled by hand. The host leaves
a bot only when `leaves_standing` is true; an unread stop is not a covering stop.

  · `NOT_APPLICABLE` - the venue holds an inventory, not a position (Spot): nothing to cover, and the
    host's policy is what it always was;
  · `NOTHING_EXPOSED` - a position venue with no position and no ladder resting: no fill can open one;
  · `COVERED` - a position stands and a recorded stop that closes it stands on the exchange;
  · `UNCOVERED` - a position stands, or a ladder rests whose fill would open one, with no stop that
    closes it (missing, not on the exchange, or on the wrong side);
  · `UNREAD` - the exchange could not be read, so the answer is not known.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StopCoverage(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    NOTHING_EXPOSED = "nothing_exposed"
    COVERED = "covered"
    UNCOVERED = "uncovered"
    UNREAD = "unread"

    @property
    def leaves_standing(self) -> bool:
        """Whether a host that exits may leave the bot as it is: nothing it holds can run away
        while no copy of the app watches it."""
        return self in _LEFT_STANDING


_LEFT_STANDING = frozenset(
    {StopCoverage.NOT_APPLICABLE, StopCoverage.NOTHING_EXPOSED, StopCoverage.COVERED}
)


@dataclass(frozen=True, slots=True)
class StopCoverageReading:
    """What one look at a bot's stop found, and the sentence that says it."""

    coverage: StopCoverage
    words: str = ""


@dataclass(frozen=True, slots=True)
class GetBotStopCoverageQuery:
    """Read, fresh from the exchange, whether `bot_id`'s position is covered by its stop."""

    bot_id: str


@dataclass(frozen=True, slots=True)
class BotStopCoverage:
    """The answer to `GetBotStopCoverageQuery`."""

    bot_id: str
    coverage: StopCoverage
    words: str = ""
