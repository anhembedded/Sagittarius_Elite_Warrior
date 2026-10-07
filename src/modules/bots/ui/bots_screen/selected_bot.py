"""`EPIC-029F` — the selected bot's working state on the Bots screen.

What the screen knows about the selection beyond its snapshot: the planner's
market numbers, the latest price, the parameters being edited and the kind's
editor showing them. Selecting another bot starts all of it afresh, so no
number of one bot is ever judged against another's.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    BotDetail,
    DetailInputs,
    detail_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import panel_for

logger = logging.getLogger("App.Bots.Screen")


class SelectedBot:
    """@brief The selection's market numbers, price, edits and editor."""

    def __init__(self, catalog: IBotKindCatalog, now: Callable[[], datetime]) -> None:
        self._catalog = catalog
        self._now = now
        self.bot: BotSnapshot | None = None
        self.market: PlannerMarket | None = None
        self.last_price: Decimal | None = None
        self.edited: Mapping[str, str] | None = None
        self.panel: BotKindPanel | None = None
        #: Why Start waits on the venue's account (`EPIC-034D`); the Connect
        #: step sets it, so selecting a bot never clears it.
        self.connection = ""
        #: What the Connect step read, for the balance and the key
        #: constraints (`EPIC-034F`); `None` while the account is unread.
        self.account: AccountView | None = None

    def select(self, bot: BotSnapshot | None) -> BotKindPanel | None:
        """Starts afresh on `bot`; returns its kind's editor showing its parameters."""
        self.bot, self.market, self.last_price, self.edited = bot, None, None, None
        self.panel = _editor_for(bot)
        if self.panel is not None and bot is not None:
            self.panel.set_config(bot.config)
        return self.panel

    def take_snapshot(self, bot: BotSnapshot) -> None:
        """The same bot, re-read: its state and progress may have moved."""
        self.bot = bot

    def take_market(self, market: PlannerMarket) -> None:
        self.market = market
        self.last_price = market.market.last_price if market.market else None
        if self.panel is not None:
            self.panel.set_planner_market(market)

    def take_price(self, symbol: str, price: Decimal) -> bool:
        """Keeps a live price for the selected symbol; `False` for another."""
        if self.bot is None or symbol != self.bot.symbol:
            return False
        self.last_price = price
        return True

    def edit(self, config: Mapping[str, str]) -> None:
        self.edited = dict(config)

    def saved(self) -> None:
        self.edited = None

    def detail(self) -> BotDetail | None:
        if self.bot is None:
            return None
        try:
            kind = self._catalog.kind(self.bot.kind)
        except UnknownBotKindError:
            kind = None
        return detail_for(
            DetailInputs(
                self.bot,
                kind,
                self.market,
                self.last_price,
                self._now(),
                self.edited,
                self.connection,
                self.account,
            )
        )


def _editor_for(bot: BotSnapshot | None) -> BotKindPanel | None:
    if bot is None:
        return None
    try:
        return panel_for(bot.kind)
    except UnknownBotKindError:
        logger.warning("Bots screen: no editor for kind %s", bot.kind)
        return None
