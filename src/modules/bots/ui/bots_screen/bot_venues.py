"""`BOT-171` — which venues a bot may be on, and moving a draft between them.

@details Held apart from the presenter, which already orchestrates every read and
action of the screen. It offers the venues (`venue_choices`), builds the command
for the Plan's Venue field, and — because the Connect step, the chart, the
planner and the fills are all bound to the selected bot's venue — makes the
screen follow a bot whose venue moved, whichever writer moved it: selecting it
again starts all four afresh on the new venue (readiness is recomputed from
them), with the parameters the user had not saved still on screen.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_commands import (
    PendingAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_step import (
    ConnectStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_choice import (
    VenueChoice,
    venue_choices,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class BotVenues:
    """@brief The venue a bot may be moved to, and the screen following a move."""

    def __init__(
        self,
        contexts: IVenueContexts,
        model: BotsViewModel,
        selected: SelectedBot,
        account: ConnectStep,
        select: Callable[[BotSnapshot], None],
    ) -> None:
        self._contexts = contexts
        self._model = model
        self._selected = selected
        self._account = account
        self._select = select

    def choices(self) -> tuple[VenueChoice, ...]:
        """Every Spot venue with its connection state, read now and shown by the
        Plan's Venue field and by New bot."""
        choices = venue_choices(self._contexts)
        self._model.set_venue_choices(choices)
        return choices

    def move_to(self, value: str) -> tuple[PendingAction, object] | None:
        """The action and command for the user's pick of `value` in the Plan's
        Venue field, or `None` with no bot selected."""
        bot = self._model.selected
        if bot is None:
            return None
        venue = TradingVenue(value)
        pending = PendingAction(
            f"Move {bot.name} to {venue.display_name}", moves_venue=True
        )
        return pending, ChangeBotVenueCommand(bot.bot_id, venue)

    def moved(self, fresh: BotSnapshot) -> bool:
        """Whether `fresh` is the bot the Connect step is bound to, now on another
        venue: the chart, the account and the numbers belong to the old one."""
        bound = self._account.bot
        return (
            bound is not None
            and bound.bot_id == fresh.bot_id
            and bound.venue is not fresh.venue
        )

    def follow(self, fresh: BotSnapshot) -> None:
        """Selects the moved bot again; parameters not yet saved stay on screen."""
        unsaved = self._selected.edited
        self._select(fresh)
        panel = self._selected.panel
        if unsaved is not None and panel is not None:
            panel.set_config(unsaved)
            self._selected.edit(unsaved)
