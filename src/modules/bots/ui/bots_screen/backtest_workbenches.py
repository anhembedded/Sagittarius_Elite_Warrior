"""`EPIC-040E` — the Backtest tab's content: the workbench of the selected bot's venue.

One `BacktestWorkbench` (`EPIC-040D`) per venue, built when a bot of that venue first needs it and
kept: its chart and its candle sync read that venue's market (`BUG-172`), and a sandbox with edits
survives the selection moving to a bot of another venue, so the question about discarding them is
asked on the workbench that holds them, not skipped by closing it. The page shown is the selected
bot's venue's; a workbench follows only bots of its own venue.

The tab says why it is off instead of disappearing (`ui-presentation-rule.md` §2): no selection
leaves an instruction, a kind with no backtester or a venue the kind does not trade on turns the tab
off and says which.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    is_in_markets,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench import (
    BacktestWorkbench,
    WorkbenchPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    NO_BACKTEST_TEXT,
    NO_SELECTION_BACKTEST_TEXT,
    BotsView,
    TabAvailability,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import kind_title
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.Screen")


class WorkbenchUnavailableError(RuntimeError):
    """A tab's backend offers no workbench for a venue (the VPS tab, which reads nothing at Binance,
    `EPIC-047E` D6); `reason` is the sentence the tab shows where the page would be."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class BacktestWorkbenches:
    """@brief Builds, follows and shuts down the workbench of the selected bot's venue."""

    def __init__(
        self,
        ports_for: Callable[[TradingVenue], WorkbenchPorts],
        catalog: IBotKindCatalog,
        view: BotsView,
    ) -> None:
        self._ports_for = ports_for
        self._catalog = catalog
        self._view = view
        self._workbenches: dict[TradingVenue, BacktestWorkbench] = {}
        self._shown: TradingVenue | None = None

    def follow(self, selected: SelectedBot) -> None:
        """What is selected now: the bot, its market numbers and its risk facts."""
        bot = selected.bot
        if bot is None:
            self._leave(TabAvailability(), NO_SELECTION_BACKTEST_TEXT)
            return
        reason = self._why_not(bot.kind, bot.venue)
        if reason:
            self._leave(TabAvailability(False, reason), reason)
            return
        try:
            workbench = self._workbench_of(bot.venue)
        except WorkbenchUnavailableError as unavailable:
            self._leave(TabAvailability(False, unavailable.reason), unavailable.reason)
            return
        if self._shown != bot.venue:
            self._shown = bot.venue
            self._view.set_backtest_page(workbench.page, "")
        self._view.set_backtest_available(TabAvailability())
        workbench.follow(WorkbenchSelection(bot, selected.market, selected.risk))

    def close(self) -> None:
        """Cancels every run in flight and drops the pages. Safe to call twice."""
        for workbench in self._workbenches.values():
            workbench.shutdown()
        self._workbenches.clear()
        self._shown = None

    def _leave(self, availability: TabAvailability, note: str) -> None:
        """No workbench fits the selection: the tab shows `note` where the page would be."""
        self._shown = None
        self._view.set_backtest_page(None, note)
        self._view.set_backtest_available(availability)

    def _workbench_of(self, venue: TradingVenue) -> BacktestWorkbench:
        workbench = self._workbenches.get(venue)
        if workbench is None:
            workbench = self._workbenches[venue] = BacktestWorkbench(
                self._ports_for(venue)
            )
            logger.info("Bots screen: backtest workbench built for %s", venue.value)
        return workbench

    def _why_not(self, kind_id: str, venue: TradingVenue) -> str:
        """Why the selected bot's kind cannot be backtested on its venue; `""` when it can."""
        try:
            kind = self._catalog.kind(kind_id)
        except UnknownBotKindError:
            return NO_BACKTEST_TEXT
        if kind.backtester() is None:
            return NO_BACKTEST_TEXT
        profile = venue_profile_of(venue)
        if profile is not None and not is_in_markets(
            profile, kind.supported_profiles()
        ):
            return (
                f"The {kind_title(kind_id)} backtest does not replay "
                f"{venue.display_name}."
            )
        return ""
