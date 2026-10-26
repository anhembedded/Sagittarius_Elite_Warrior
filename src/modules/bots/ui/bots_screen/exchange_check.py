"""`BOT-174` — the selected bot's exchange snapshot: asked, awaited, dropped when stale.

@details A bot that is at rest (DRAFT, STOPPED) or HALTED has a Start or a Resume
whose rules need the exchange's facts, so the screen asks for them when it is
selected, on demand (Bots → Refresh exchange check, and the Run step's own fix),
and whenever its state changes or a command it was sent finishes. The ask is one
fenced read of its own kind (`ReadKind.EXCHANGE`, `fenced_reads.py`): a newer ask
supersedes the older, so an answer for a bot no longer selected or a request
already replaced is dropped and logged (`async-ui-action-rule.md` §1), and
deselecting, or a state with nothing to check, cancels the one in flight.

While the answer is awaited the snapshot is `ExchangeChecking`: the Run step says
so and neither Start nor Resume is enabled. A read that failed is
`ExchangeUnavailable` with its text, never an empty account. It owns no FSM state
and no action ids (`async-ui-action-rule.md` §2): the tracker is the presenter's,
the snapshot is `SelectedBot`'s, and the screen's refresh is handed in.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    RUN_STARTING_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    BotQueries,
    FencedReads,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_risk_check import (
    PlanRiskCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.run_facts_check import (
    RunFactsCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)

logger = logging.getLogger("App.Bots.Screen")

#: The states whose next step (a Start, a Resume) the exchange's facts judge.
CHECKED_STATES = RUN_STARTING_STATES | RESUME_PROPOSES_STATES


class ExchangeCheck:
    """@brief Keeps the selected bot's exchange snapshot current, and with it the liquidation
    facts of a bot on a position venue."""

    def __init__(
        self,
        queries: BotQueries,
        reads: FencedReads,
        selected: SelectedBot,
        refresh_detail: Callable[[], None],
    ) -> None:
        self._risk = PlanRiskCheck(queries, reads, selected, refresh_detail)
        self._run = RunFactsCheck(queries, reads, selected, refresh_detail)
        self._queries = queries
        self._reads = reads
        self._selected = selected
        self._refresh_detail = refresh_detail
        reads.answered.connect(self._on_read_answered)
        reads.failed.connect(self._on_read_failed)

    def follow(self, bot: BotSnapshot | None) -> None:
        """`bot` was selected, or its state changed: ask again, or cancel the
        ask when nothing is left to check."""
        self._selected.take_exchange(ExchangeChecking())
        self._run.follow(bot)
        if bot is None:
            self._reads.abandon(ReadKind.EXCHANGE)
            self._risk.follow(None)
            return
        if bot.state not in CHECKED_STATES:
            # Start's readiness has nothing to check for a bot that runs, but its Backtest still
            # needs the symbol's brackets (`EPIC-039J` hand-off): the risk facts are read in
            # every state, the exchange snapshot only for a bot at rest.
            self._reads.abandon(ReadKind.EXCHANGE)
            self._risk.follow(bot)
            return
        logger.debug("Exchange check: asking for %s (%s)", bot.name, bot.state.value)
        self._queries.exchange(bot)
        self._risk.follow(bot)

    def follow_a_change(self, shown: BotSnapshot, fresh: BotSnapshot) -> None:
        """A list read brought `fresh` for the bot `shown`: asked again when its
        state moved (the executor halted it, a command stopped it)."""
        if shown.state is not fresh.state:
            self.follow(fresh)

    def recheck_run(self) -> None:
        """The Run facts of the selected bot again (the bots were read again, the clock)."""
        self._run.recheck()

    def refresh(self) -> None:
        """Ask again for the selected bot (the command, the Run step's fix, a
        command that finished)."""
        self.follow(self._selected.bot)
        self._refresh_detail()

    def _on_read_answered(self, kind: ReadKind, label: str, answer: object) -> None:
        bot = self._selected.bot
        if kind is not ReadKind.EXCHANGE or bot is None or bot.bot_id != label:
            return
        if not isinstance(
            answer,
            ExchangeChecking | ExchangeUnavailable | ExchangeLoaded | FuturesLoaded,
        ):
            raise TypeError(
                f"an exchange read answers a snapshot, not {type(answer).__name__}"
            )
        self._selected.take_exchange(answer)
        self._refresh_detail()

    def _on_read_failed(self, kind: ReadKind, label: str, detail: str) -> None:
        """The read itself failed (the reader never raises, so this is a fault of
        the app, not of the exchange): said as the snapshot's own unavailable
        state, for the bot that asked, instead of a second message bar."""
        bot = self._selected.bot
        if kind is not ReadKind.EXCHANGE or bot is None or bot.bot_id != label:
            return
        self._selected.take_exchange(ExchangeUnavailable(detail or "the read failed"))
        self._refresh_detail()
