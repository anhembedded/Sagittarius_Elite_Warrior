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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_run_facts import (
    BotRunFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.other_active_bot import (
    other_active_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness_assessment import (
    ConnectionRead,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
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

    def __init__(
        self,
        catalog: IBotKindCatalog,
        now: Callable[[], datetime],
        run_facts: BotRunFactsReader,
    ) -> None:
        self._catalog = catalog
        self._now = now
        self._run_facts = run_facts
        #: Every bot the list shows, and the files it refused: what "another
        #: bot is active" is read from (ADR D20).
        self._bots: tuple[BotSnapshot, ...] = ()
        self._refused: tuple[str, ...] = ()
        self.bot: BotSnapshot | None = None
        self.market: PlannerMarket | None = None
        self.last_price: Decimal | None = None
        self.edited: Mapping[str, str] | None = None
        self.panel: BotKindPanel | None = None
        #: What the Connect step answered (`EPIC-034D`); the step sets it, so
        #: selecting a bot never clears it. It carries the account the balance
        #: and key constraints read (`EPIC-034F`).
        self.connection: ConnectionRead | None = None

    def select(self, bot: BotSnapshot | None) -> BotKindPanel | None:
        """Starts afresh on `bot`; returns its kind's editor showing its parameters."""
        self.bot, self.market, self.last_price, self.edited = bot, None, None, None
        self.panel = _editor_for(bot)
        if self.panel is not None and bot is not None:
            self.panel.set_config(bot.config)
        return self.panel

    def take_bots(
        self, bots: tuple[BotSnapshot, ...], refused_files: tuple[str, ...]
    ) -> None:
        self._bots, self._refused = bots, refused_files

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
        config = self.edited if self.edited is not None else self.bot.config
        run = self._run_facts.read(
            self.bot.bot_id,
            self.bot.venue,
            self.bot.symbol,
            config,
            other_active_bot(
                self.bot.bot_id,
                ((other.bot_id, other.state) for other in self._bots),
                self._refused,
            ),
        )
        return detail_for(
            DetailInputs(
                self.bot,
                kind,
                self.market,
                self.last_price,
                self._now(),
                self.edited,
                self.connection,
                run,
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
