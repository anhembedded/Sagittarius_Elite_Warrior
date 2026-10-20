"""`EPIC-026L` — one read of the host's bots, in the words the cap judges them in.

The bots are read through the status report every other reader of "what are my bots doing" reads
(`GetBotStatusReportQuery`), so the cap cannot disagree with `bot list`. A bot's result is its
run account at its own last price (`RunEarnings.total_pnl`): the bot's record, not the
exchange's. That is accepted for this control (decision N3: the smallest cap that depends on no
bot's own *logic*), and a bot with no price yet, no account, or another quote asset is reported
unjudged rather than counted as zero.

A read that fails is a reading with a `failure`, never an empty list: the cap must not take "I
could not look" for "there is nothing to lose" (`code/errors.md` §7).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_figure import (
    LossCapFigure,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_ledger import (
    BotObservation,
)

logger = logging.getLogger("App.Bots.LossCap")


@dataclass(frozen=True, slots=True)
class LossCapReading:
    """One sample: what each bot made, which bots may hold risk, and what could not be judged."""

    observations: tuple[BotObservation, ...] = ()
    #: The bots that are not at rest: the ones a trip stops.
    active: tuple[BotStatusEntry, ...] = ()
    #: Bot files this build refused to load; each may be a bot with orders.
    unreadable: tuple[str, ...] = ()
    #: Empty when the bots were read; the exception type's name when they were not.
    failure: str = ""

    @property
    def unjudged_bots(self) -> tuple[str, ...]:
        return tuple(o.bot_id for o in self.observations if o.is_unjudged)

    @property
    def is_unjudged(self) -> bool:
        return bool(self.failure or self.unreadable or self.unjudged_bots)

    def why_unjudged(self) -> str:
        parts: list[str] = []
        if self.failure:
            parts.append(f"the bots could not be read ({self.failure})")
        if self.unreadable:
            parts.append(
                f"bot file(s) {', '.join(self.unreadable)} cannot be read by this build"
            )
        if self.unjudged_bots:
            parts.append(
                f"no result in the cap's quote asset for {', '.join(self.unjudged_bots)} "
                "(no price yet, no run account, or another quote asset)"
            )
        return "; ".join(parts)


class LossCapSampler:
    def __init__(
        self, dispatcher: ICommandDispatcher, figure: LossCapFigure | None
    ) -> None:
        self._dispatcher = dispatcher
        self._covers: Callable[[str], bool] = (
            figure.covers if figure is not None else lambda _symbol: True
        )

    def read(self) -> LossCapReading:
        try:
            report = cast(
                BotStatusReport,
                self._dispatcher.dispatch(
                    GetBotStatusReportQuery, GetBotStatusReportQuery()
                ),
            )
        # Converted at the seam: a read that raised is a reading that says so, which the cap
        # counts as "cannot judge" and not as "nothing to lose".
        except Exception as exc:  # noqa: BLE001 — see above
            logger.warning(
                "[loss-cap] the bots could not be read: %s", type(exc).__name__
            )
            return LossCapReading(failure=type(exc).__name__)
        return LossCapReading(
            observations=tuple(self._observed(bot) for bot in report.bots),
            active=tuple(bot for bot in report.bots if not bot.is_at_rest),
            unreadable=tuple(bot.bot_id for bot in report.unreadable),
        )

    def _observed(self, bot: BotStatusEntry) -> BotObservation:
        earnings = bot.earnings
        judged = earnings is not None and earnings.judged and self._covers(bot.symbol)
        return BotObservation(
            bot.bot_id,
            bot.run_started_at,
            earnings.total_pnl if judged and earnings is not None else None,
            bot.is_at_rest,
        )
