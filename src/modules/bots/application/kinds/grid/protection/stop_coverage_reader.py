"""`EPIC-038M` (decision O12) - does a stop on the exchange cover this Futures bot's position now?

@details The one read behind two questions: the halt's words ("its protective stop stands on the
exchange", `IExposureProtection.describe_stop`) and the `run` host's choice between leaving a bot
and closing it (`read_coverage`). Both read the exchange fresh - the bot's open protective orders and
its position - and judge them against the stops the bot's record holds (`judge_stop`), because the
record alone can say a stop stands that was cancelled by hand.

A flat account is not "covered": a ladder that rests on the exchange opens a position when it fills,
and the stop is placed only over a position that exists (a stop over nothing could open one), so
nobody places it while the host is down. A flat bot is exposed only while its ladder rests.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protective_stop_plan import (
    covers,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.stop_words import (
    StopFinding,
    judge_stop,
    words_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverage,
    StopCoverageReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop import (
    ProtectiveStop,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order

logger = logging.getLogger("App.Bots.GridExecutor")

_UNREAD = StopCoverageReading(StopCoverage.UNREAD, words_of(StopFinding.UNREAD))


class StopCoverageReader:
    """Reads one Futures Grid's stop against the exchange."""

    def __init__(
        self,
        context: GridRunContext,
        recorded: Callable[[], tuple[ProtectiveStop, ...]],
        open_stops: Callable[[], dict[str, Order] | None],
    ) -> None:
        self._context = context
        self._recorded = recorded
        self._open_stops = open_stops

    def describe(self) -> str:
        """The halt's words; empty when the account is flat (nothing for a stop to cover)."""
        open_stops = self._open_stops()
        position = self._context.gateway.position()
        if open_stops is None or position is None:
            return words_of(StopFinding.UNREAD)
        if position == 0:
            return ""
        return words_of(self._finding(open_stops, position))

    def read(self) -> StopCoverageReading:
        open_stops = self._open_stops()
        position = self._context.gateway.position()
        if open_stops is None or position is None:
            return _UNREAD
        if position == 0:
            return self._flat()
        finding = self._finding(open_stops, position)
        coverage = (
            StopCoverage.COVERED
            if finding is StopFinding.STANDS
            else StopCoverage.UNCOVERED
        )
        return StopCoverageReading(coverage, words_of(finding))

    def _finding(self, open_stops: dict[str, Order], position: Decimal) -> StopFinding:
        recorded = self._recorded()
        covering = {
            stop.client_order_id
            for stop in recorded
            if covers(self._context.params, stop.side, position)
        }
        return judge_stop(recorded, set(open_stops), covering)

    def _flat(self) -> StopCoverageReading:
        try:
            ladder = self._context.gateway.account_reads.ladder_orders()
        except (
            Exception
        ):  # converted at this seam: an unread ladder is `UNREAD`, never "none"
            logger.exception(
                "Bot %s: the ladder on the exchange could not be read [protective-stop]",
                self._context.state.bot_id,
            )
            return _UNREAD
        if ladder:
            return StopCoverageReading(
                StopCoverage.UNCOVERED,
                f"it holds no position but {len(ladder)} ladder order(s) rest on the exchange: "
                "a fill opens a position that no stop covers",
            )
        return StopCoverageReading(
            StopCoverage.NOTHING_EXPOSED, "it holds no position and rests no ladder"
        )
