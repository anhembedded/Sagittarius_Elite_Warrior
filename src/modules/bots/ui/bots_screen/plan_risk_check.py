"""`EPIC-039J` — the selected bot's liquidation facts: asked, awaited, dropped when stale.

@details A bot on a position venue is judged for liquidation from the symbol's leverage
brackets and the account's setting, which only the exchange knows. They are read once a bot is
selected (and again on Refresh exchange check), as one fenced read of their own
(`ReadKind.RISK`, `fenced_reads.py`): a newer ask supersedes the older one, so an answer for a
bot no longer selected, or for a request already replaced, never overwrites a newer one
(`async-ui-action-rule.md` §1). A venue with no position risk is never asked, and a bot that
is not at rest has no plan to judge.

A read the venue could not answer leaves no facts: the Liquidation row then says it is not
estimated, never a figure, and the reason is logged (the Run step's exchange check already tells
the user an unreadable account).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.plan_risk_read import (
    PlanRiskUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    BotQueries,
    FencedReads,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)

logger = logging.getLogger("App.Bots.Screen")


class PlanRiskCheck:
    """@brief Keeps the selected bot's liquidation facts current."""

    def __init__(
        self,
        queries: BotQueries,
        reads: FencedReads,
        selected: SelectedBot,
        refresh_detail: Callable[[], None],
    ) -> None:
        self._queries = queries
        self._reads = reads
        self._selected = selected
        self._refresh_detail = refresh_detail
        reads.answered.connect(self._on_read_answered)

    def follow(self, bot: BotSnapshot | None) -> None:
        """`bot` is at rest and was selected or refreshed (`ExchangeCheck` decides that),
        or is `None` for no bot left to judge: ask for its venue's facts, or drop the ask
        when the venue has no position risk."""
        self._selected.take_risk(None)
        if bot is None or not _carries_position_risk(bot):
            self._reads.abandon(ReadKind.RISK)
            return
        logger.debug("Plan risk: asking for the facts of %s", bot.name)
        self._queries.risk(bot)

    def refresh(self) -> None:
        self.follow(self._selected.bot)

    def _on_read_answered(self, kind: ReadKind, label: str, answer: object) -> None:
        """An answer of the read: kept only when it is the selected bot's."""
        bot = self._selected.bot
        if kind is not ReadKind.RISK:
            return
        if bot is None or bot.bot_id != label:
            logger.debug(
                "Plan risk: facts for %s arrived after the selection moved", label
            )
            return
        if not isinstance(answer, PlanRiskFacts | PlanRiskUnavailable):
            raise TypeError(
                f"a plan-risk read answers facts, not {type(answer).__name__}"
            )
        if isinstance(answer, PlanRiskUnavailable):
            logger.info(
                "Plan risk: %s not estimated: %s [plan-risk]", bot.name, answer.reason
            )
        self._selected.take_risk(answer)
        self._refresh_detail()


def _carries_position_risk(bot: BotSnapshot) -> bool:
    profile = venue_profile_of(bot.venue)
    return profile is not None and bool(profile.margin_modes)
