"""`EPIC-048B` — the selected bot's Run facts: asked off the UI thread, held, dropped when stale.

@details What only the host knows of a bot's Run step (the other bots on its symbol and venue,
who holds the symbol's lease, whether the venue is on, the budget caps) is one fenced read of its
own (`ReadKind.RUN`, `fenced_reads.py`, `GetBotRunFactsQuery`). It is asked when a bot is
selected, when the bots are read again (another bot started, stopped or was created), when a
command finishes and on the screen's clock; a newer ask supersedes the older, so an answer for a
bot no longer selected is dropped and logged (`async-ui-action-rule.md` §1). The answer is held
in `SelectedBot` with the bot's other facts, so a re-judge after an edit reads nothing: the budget
of the parameters on screen is judged from the caps the answer carries.

Until the first answer the facts are not known, and the assessment says the Run step is being
checked, so Start is never offered on facts nobody has read. A read that failed is told once in
the message bar (`BotsFailures`) and leaves Start waiting. It owns no FSM state and no action
ids: the tracker is the presenter's, the facts are `SelectedBot`'s.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_run_facts import (
    BotRunFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
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


class RunFactsCheck:
    """@brief Keeps the selected bot's Run facts current, read on the thread manager."""

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
        """`bot` was selected, or `None` for no bot: ask for its Run facts, or drop the ask."""
        if bot is None:
            self._reads.abandon(ReadKind.RUN)
            return
        self._queries.run_facts(bot)

    def recheck(self) -> None:
        """Ask again for the selected bot, keeping the facts held until the answer."""
        self.follow(self._selected.bot)

    def _on_read_answered(self, kind: ReadKind, label: str, answer: object) -> None:
        bot = self._selected.bot
        if kind is not ReadKind.RUN:
            return
        if bot is None or bot.bot_id != label:
            logger.debug(
                "Run facts: the facts of %s arrived after the selection moved", label
            )
            return
        if not isinstance(answer, BotRunFacts):
            raise TypeError(
                f"a Run facts read answers BotRunFacts, not {type(answer).__name__}"
            )
        self._selected.take_run(answer)
        self._refresh_detail()
