"""`EPIC-029D` — the selected bot's kind's backtest, as the Bots screen hosts it.

Kind-neutral: the backtest comes from `kind_panels.backtest_for`, built once
per kind and kept while bots of that kind are selected (selecting another bot
of the same kind cancels its run and clears its result, `BotBacktest.follow`).
A kind with no backtest, or no selection, hides the Backtest tab.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_backtest import (
    BacktestContext,
    BacktestPorts,
    BotBacktest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import (
    backtest_for,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.Screen")


class KindBacktests:
    """@brief Builds, follows and shuts down the selected kind's backtest."""

    def __init__(
        self,
        ports_for: Callable[[TradingVenue], BacktestPorts],
        show: Callable[[QWidget | None], None],
    ) -> None:
        self._ports_for = ports_for
        self._show = show
        self._kind: str | None = None
        self._venue: TradingVenue | None = None
        self._backtest: BotBacktest | None = None

    def follow(self, selected: SelectedBot) -> None:
        """What is selected now: the bot, its edits and its market numbers.

        The page is built for the bot's kind **and venue** (`BUG-172`): its
        chart and its sync read the market the bot's orders fill in, so a bot of
        the same kind on another venue gets a page of its own."""
        bot = selected.bot
        kind = bot.kind if bot is not None else None
        venue = bot.venue if bot is not None else None
        if (kind, venue) != (self._kind, self._venue):
            self.close()
            self._kind, self._venue = kind, venue
            self._backtest = (
                backtest_for(kind, self._ports_for(venue))
                if kind and venue is not None
                else None
            )
            logger.info(
                "Bots screen: backtest for kind %s on %s: %s",
                kind,
                venue.value if venue is not None else None,
                "built" if self._backtest is not None else "none",
            )
            self._show(self._backtest.page if self._backtest is not None else None)
        if self._backtest is not None:
            self._backtest.follow(backtest_context(selected))

    def close(self) -> None:
        """Cancels a run in flight and drops the page. Safe to call twice."""
        if self._backtest is not None:
            self._backtest.shutdown()
        self._backtest = None
        self._kind = None
        self._venue = None


def backtest_context(selected: SelectedBot) -> BacktestContext | None:
    """The selection as a backtest reads it: the edits when there are any."""
    bot = selected.bot
    if bot is None:
        return None
    market = selected.market
    return BacktestContext(
        bot_id=bot.bot_id,
        venue=bot.venue,
        symbol=bot.symbol,
        config=dict(selected.edited if selected.edited is not None else bot.config),
        terms=market.terms if market is not None else None,
    )
