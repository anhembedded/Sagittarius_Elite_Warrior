"""`EPIC-038M` (decision O12) - handler for `GetBotStopCoverageQuery`.

@details The question the `run` host asks before it leaves a bot behind: does a stop on the exchange
cover its position now? The venue profile says whether the question applies at all (an inventory
venue has no stop to ask about, and answers `NOT_APPLICABLE` without touching the exchange); the
bot's executor reads the exchange for a position venue (`IBotRunner.stop_coverage`). Whatever cannot be
read is `UNREAD`, which the host treats as not covered: an unread stop is not a covering stop.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    BotStopCoverage,
    GetBotStopCoverageQuery,
    StopCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    IBotStore,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BotId,
    InvalidBotIdError,
)

logger = logging.getLogger("App.CommandHandler")


class GetBotStopCoverageQueryHandler(
    IQueryHandler[GetBotStopCoverageQuery, BotStopCoverage]
):
    def __init__(self, store: IBotStore, runner: IBotRunner) -> None:
        self._store = store
        self._runner = runner

    def execute(self, query: GetBotStopCoverageQuery) -> BotStopCoverage:
        try:
            stored = self._store.load(BotId(query.bot_id))
        except (InvalidBotIdError, BotNotFoundError, UnreadableBotError) as exc:
            return self._unread(query.bot_id, f"its record could not be read ({exc})")
        profile = venue_profile_of(stored.bot.definition.venue)
        if profile is None or profile.exposure_kind is not ExposureKind.POSITION:
            return BotStopCoverage(query.bot_id, StopCoverage.NOT_APPLICABLE)
        try:
            reading = self._runner.stop_coverage(query.bot_id)
        except (
            Exception
        ) as exc:  # converted at this seam: an unread stop is `UNREAD`, never covered
            logger.exception(
                "Bot %s: the stop over its position could not be read", query.bot_id
            )
            return self._unread(
                query.bot_id,
                f"whether its protective stop stands could not be read ({type(exc).__name__})",
            )
        if reading.coverage is StopCoverage.NOT_APPLICABLE:
            # A position venue whose bot has no protection wired: nothing stands over the position.
            return BotStopCoverage(
                query.bot_id,
                StopCoverage.UNCOVERED,
                "no protective stop is wired for this position venue",
            )
        return BotStopCoverage(query.bot_id, reading.coverage, reading.words)

    @staticmethod
    def _unread(bot_id: str, words: str) -> BotStopCoverage:
        return BotStopCoverage(bot_id, StopCoverage.UNREAD, words)
