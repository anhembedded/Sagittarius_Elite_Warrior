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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    GridLadder,
    LadderUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    ActionAvailability,
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    BotFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_view import (
    ConnectView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks import (
    PlanChecks,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot_precisions import (
    SelectedBotPrecisions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_choice import (
    VenueChoice,
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
    #: The selected bot's ladder, or why it has none, changed (`BOT-193`).
    ladder_changed = Signal()
    judgement_changed = Signal()
    #: Why no grid is drawn on the chart (`EPIC-035N`).
    chart_note_changed = Signal()
    #: What is left before Start changed (`EPIC-034H`).
    readiness_changed = Signal()
    actions_changed = Signal()
    fills_changed = Signal()
    log_changed = Signal()
    #: An action is in flight: every command waits for it (`EPIC-033D`).
    action_in_flight_changed = Signal()
    #: Whether New bot works in this tab changed (`EPIC-047E`: the VPS tab creates bots by Add to VPS).
    new_bot_availability_changed = Signal()
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
    #: Ask the exchange again for the facts the readiness is judged on (`BOT-174`).
    refresh_exchange_requested = Signal()
    #: Write the bots as a plan file (`BOT-176`).
    export_plan_requested = Signal()
    #: Do the first fix the readiness offers (`EPIC-034H`): bring the field
    #: forward, read the account again, or select the bot that is still active.
    fix_next_requested = Signal()
    #: Scale the chart's price axis to every level of the selected bot.
    fit_levels_requested = Signal()
    #: The user picked another Spot venue for the selected draft bot
    #: (`BOT-171`): a `TradingVenue` value.
    venue_change_requested = Signal(str)
    #: The venues the Plan's Venue field offers changed.
    venue_choices_changed = Signal()
    #: The planner read a venue and symbol's tick and step sizes the tables quote in (`EPIC-048B`).
    precisions_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.bots: tuple[BotSnapshot, ...] = ()
        self.selected: BotSnapshot | None = None
        self.facts: BotFacts | None = None
        self.ladder: GridLadder | LadderUnavailable | None = None
        self.checks = PlanChecks()
        self.chart_note = ""
        #: What is left before Start, and where the bot stands among the three
        #: steps; `None` while the bot has a run or none is selected.
        self.readiness: BotReadiness | None = None
        self.readiness_state = ReadinessState.NOT_CONNECTED
        #: Whether the readiness has an item whose fix the screen can do.
        self.fixable = False
        self.availability: Mapping[BotAction, ActionAvailability] = {}
        self.fills = BotFills()
        self.connect_view = ConnectView()
        self.venue_choices: tuple[VenueChoice, ...] = ()
        #: The tick and step sizes the selected bot's orders and fills are written in.
        self.precisions = SelectedBotPrecisions(lambda: self.selected)
        self.action_in_flight = False
        self.new_bot_unavailable = ""
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

    @Slot(object)
    def set_ladder(self, ladder: GridLadder | LadderUnavailable | None) -> None:
        self.ladder = ladder
        self.ladder_changed.emit()

    @Slot(str)
    def set_chart_note(self, text: str) -> None:
        self.chart_note = text
        self.chart_note_changed.emit()

    @Slot(object)
    def set_judgement(self, checks: PlanChecks) -> None:
        self.checks = checks
        self.judgement_changed.emit()

    @property
    def verdict_lines(self) -> tuple[str, ...]:
        """Every check's whole sentence, the attention ones first."""
        return tuple(check.detail for check in self.checks.everything)

    @Slot(object, object, bool)
    def set_readiness(
        self,
        readiness: BotReadiness | None,
        state: ReadinessState,
        fixable: bool = False,
    ) -> None:
        self.readiness, self.readiness_state = readiness, state
        self.fixable = fixable
        self.readiness_changed.emit()

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

    @Slot(object)
    def set_venue_choices(self, choices: tuple[VenueChoice, ...]) -> None:
        self.venue_choices = choices
        self.venue_choices_changed.emit()

    def set_new_bot_unavailable(self, reason: str) -> None:
        """Why New bot does not work in this tab; `""` when it does."""
        if reason != self.new_bot_unavailable:
            self.new_bot_unavailable = reason
            self.new_bot_availability_changed.emit()

    @Slot(bool)
    def set_action_in_flight(self, in_flight: bool) -> None:
        if in_flight != self.action_in_flight:
            self.action_in_flight = in_flight
            self.action_in_flight_changed.emit()

    @Slot(object)
    def set_fills(self, fills: BotFills) -> None:
        self.fills = fills
        self.fills_changed.emit()

    def learn_market(self, market: PlannerMarket) -> None:
        """The planner's answer for the selected bot: its sizes quote the tables, which show
        again when new."""
        if self.selected is not None and self.precisions.learn(self.selected, market):
            self.precisions_changed.emit()

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
