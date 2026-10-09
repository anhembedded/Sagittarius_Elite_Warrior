"""`BUG-193` — a plan that could not be judged is judged again when the venue
answers.

The planner's market numbers are read once, when a bot is selected. A read that
failed (the key refused for a moment, the exchange not answering) stayed the
Plan's verdict for good while the header, fed by the Connect step, went back to
"Connected". The Connect step re-reads the account every minute and tells the
screen each answer; the first answer that says the venue is connected while the
selected bot's market is unreadable asks the planner again, so a recovered key
judges the Plan without a user action.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    CONNECTED_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_step import (
    ConnectStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_view import (
    ConnectView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    BotQueries,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)

logger = logging.getLogger("App.Bots.Screen")


class PlannerRecovery:
    """@brief Reads the planner's numbers again once the venue is reachable."""

    def __init__(
        self, step: ConnectStep, selected: SelectedBot, queries: BotQueries
    ) -> None:
        self._selected = selected
        self._queries = queries
        #: The problem last told, so a standing one is one line, not one a minute.
        self._told = ""
        step.changed.connect(self._on_connection)

    def _on_connection(self, view: ConnectView) -> None:
        bot, market = self._selected.bot, self._selected.market
        problem = market.problem if market is not None else ""
        if not problem:
            self._told = ""
            return
        if bot is None or view.state not in CONNECTED_STATES:
            return
        log = logger.debug if problem == self._told else logger.info
        log(
            "Bots screen: %s is connected, but its plan could not be judged (%s); "
            "reading the planner's numbers again [plan-rejudge]",
            bot.name,
            problem,
        )
        self._told = problem
        self._queries.planner(bot)
