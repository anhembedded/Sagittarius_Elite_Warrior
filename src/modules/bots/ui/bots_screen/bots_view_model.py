"""`EPIC-029F` — what the Bots screen shows, and the user's intents.

The presenter writes read models here (the list, the selected bot, its
judgement, its fills, the log); the view reads them and turns clicks into the
intent signals below. No decision lives here: which actions are live comes
from `bot_action_rules`, what a plan is worth from the kind.

Signals are snake_case, as `BotTickFeed.candle` is: the bots UI tree keeps
the repository's naming rule.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping

from PySide6.QtCore import QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    BotFills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    ActionAvailability,
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    BotFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_view import (
    ConnectView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)

#: Log lines kept across every bot; the selected bot's are filtered out of them.
LOG_LIMIT = 1000


class BotsViewModel(StatusMessageViewModel):
    """@brief State behind the Bots screen."""

    bots_changed = Signal()
    selection_changed = Signal()
    facts_changed = Signal()
    judgement_changed = Signal()
    actions_changed = Signal()
    fills_changed = Signal()
    log_changed = Signal()
    #: An action is in flight: every command waits for it (`EPIC-033D`).
    action_in_flight_changed = Signal()
    #: The selected bot's venue account was read, or could not be
    #: (`EPIC-034D`).
    connect_changed = Signal()

    #: The bot the user picked, `""` for none.
    select_requested = Signal(str)
    new_bot_requested = Signal()
    #: A `BotAction` value.
    action_requested = Signal(str)
    refresh_fills_requested = Signal()
    #: Read the selected bot's venue account again (`EPIC-034D`).
    retry_connect_requested = Signal()
    #: Show the owner's real account, read only (`EPIC-034E`).
    mainnet_account_requested = Signal()
    #: Scale the chart's price axis to every level of the selected bot.
    fit_levels_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.bots: tuple[BotSnapshot, ...] = ()
        self.selected: BotSnapshot | None = None
        self.facts: BotFacts | None = None
        self.verdict_lines: tuple[str, ...] = ()
        self.refusal = ""
        self.availability: Mapping[BotAction, ActionAvailability] = {}
        self.fills = BotFills()
        self.connect_view = ConnectView()
        self.action_in_flight = False
        self._log: deque[str] = deque(maxlen=LOG_LIMIT)

    @Slot(object)
    def set_bots(self, bots: tuple[BotSnapshot, ...]) -> None:
        self.bots = bots
        self.bots_changed.emit()

    @Slot(object)
    def set_selected(self, bot: BotSnapshot | None) -> None:
        changed = (self.selected.bot_id if self.selected else None) != (
            bot.bot_id if bot else None
        )
        self.selected = bot
        if changed:
            self.fills = BotFills()
            self.selection_changed.emit()
            self.fills_changed.emit()
            self.log_changed.emit()

    @Slot(object)
    def set_facts(self, facts: BotFacts | None) -> None:
        self.facts = facts
        self.facts_changed.emit()

    @Slot(object, str)
    def set_judgement(self, verdict_lines: tuple[str, ...], refusal: str) -> None:
        self.verdict_lines = verdict_lines
        self.refusal = refusal
        self.judgement_changed.emit()

    @Slot(object)
    def set_availability(
        self, availability: Mapping[BotAction, ActionAvailability]
    ) -> None:
        self.availability = availability
        self.actions_changed.emit()

    @Slot(object)
    def set_connect(self, view: ConnectView) -> None:
        self.connect_view = view
        self.connect_changed.emit()

    @Slot(bool)
    def set_action_in_flight(self, in_flight: bool) -> None:
        if in_flight != self.action_in_flight:
            self.action_in_flight = in_flight
            self.action_in_flight_changed.emit()

    @Slot(object)
    def set_fills(self, fills: BotFills) -> None:
        self.fills = fills
        self.fills_changed.emit()

    @Slot(str)
    def append_log_line(self, line: str) -> None:
        self._log.append(line)
        if self.selected is not None and _mentions(line, self.selected.bot_id):
            self.log_changed.emit()

    def selected_log(self) -> tuple[str, ...]:
        """The kept lines that name the selected bot, oldest first."""
        if self.selected is None:
            return ()
        bot_id = self.selected.bot_id
        return tuple(line for line in self._log if _mentions(line, bot_id))


def _mentions(line: str, bot_id: str) -> bool:
    """Every bot log line names its bot as `Bot <id>` (worker, executor,
    resume); matching that form keeps another bot's id inside an order id
    from counting."""
    return f"Bot {bot_id}" in line
