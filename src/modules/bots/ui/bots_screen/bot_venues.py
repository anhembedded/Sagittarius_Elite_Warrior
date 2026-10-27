"""`BOT-171` — which venues a bot may be on, and moving a draft between them.

@details Held apart from the presenter, which already orchestrates every read and
action of the screen. It asks for the venues (`GetVenueChoicesQuery`, a fenced read of its
own: at screen start and after every command, never at a click), holds the answer in the view
model for New bot and the Plan's Venue field to offer, builds the command
for the Plan's Venue field, and — because the Connect step, the chart, the
planner and the fills are all bound to the selected bot's venue — makes the
screen follow a bot whose venue moved, whichever writer moved it: selecting it
again starts all four afresh on the new venue (readiness is recomputed from
them), with the parameters the user had not saved still on screen.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_choice import (
    VenueChoice,
    VenueChoices,
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    BotQueries,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

NOT_READ_YET = (
    "The venues are not read yet, so New bot waits. Try it again in a moment."
)


class BotVenues:
    """@brief The venue a bot may be moved to, and the screen following a move."""

    def __init__(
        self,
        queries: BotQueries,
        model: BotsViewModel,
        selected: SelectedBot,
        account: ConnectStep,
        select: Callable[[BotSnapshot], None],
    ) -> None:
        self._queries = queries
        self._model = model
        self._selected = selected
        self._account = account
        self._select = select
        queries.reads.answered.connect(self._on_read_answered)
        self.refresh()

    def refresh(self) -> None:
        """Ask for every offered venue a kind runs on, with its connection state; the
        answer is what the Plan's Venue field and New bot show. Asked on the screen's beat
        too, so a key saved in Settings shows within a beat, not only after a command."""
        self._queries.venue_choices()

    def new_bot(
        self,
        ask: Callable[[Sequence[str], Sequence[VenueChoice]], CreateBotCommand | None],
        kinds: Sequence[str],
    ) -> CreateBotCommand | None:
        """New bot's command, asked with the venues last read; with none read yet (the first
        answer is on its way, or the read failed and its message bar offers Retry) the dialog
        would hold no venue, so it is not opened: the venues are asked again and the screen says so."""
        choices = self._model.venue_choices
        if choices:
            return ask(kinds, choices)
        self.refresh()
        self._model.set_status(NOT_READ_YET, False)
        return None

    def _on_read_answered(self, kind: ReadKind, _label: str, answer: object) -> None:
        if kind is not ReadKind.VENUES:
            return
        if not isinstance(answer, VenueChoices):
            raise TypeError(
                f"a venues read answers VenueChoices, not {type(answer).__name__}"
            )
        self._model.set_venue_choices(answer.choices)

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
