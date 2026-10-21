"""`EPIC-033K` — the Bots mode's Plan panel: the selected bot's plan.

The bot's name and state word, one status banner (`BOT-209`, `plan_status.py`: the first thing
left before Start, or how the run ended, or that it is ready), the kind's parameter editor, what
the kind says about those parameters as a list of checks (`plan_checks_view.py`), and the
readiness steps and figures as a property table (`BOT-206`, `plan_property_grid.py`) (HLD §11.2.1,
"right: Plan (the kind's panel: parameters and verdicts)"). The panel names no kind: the editor
arrives from the presenter. With no bot selected it holds the instruction to pick or create one.

The plan scrolls once, at the panel (`ui-presentation-rule.md` §3): the table, a Grid's editor
and its checks stand over 500 px, and without the scroll they set the whole mode's minimum
height (the PR #361 review measured 703 px). So both lists are as tall as their rows and the
panel is the one thing that scrolls.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    title_word_of,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_ladder_facts import (
    LADDER_ROWS,
    ladder_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_state_looks import (
    state_look,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks_view import (
    PlanChecksView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_grid import (
    PlanPropertyGrid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_rows import (
    COST_KEYS,
    LIQUIDATION_KEY,
    PROPERTY_GROUPS,
    PROPERTY_KEYS,
    READINESS_GROUP,
    step_key,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_status import (
    PlanStatus,
    StatusInputs,
    plan_status,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_status_banner import (
    PlanStatusBanner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.readiness_words import (
    step_rows,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_choice import (
    add_venue_choice,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.empty_page import empty_page
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.state_badge import StateBadge

from .widget_slot import replace_in

EMPTY_TEXT = "Select a bot in Bots, or create one with Bots → New bot…."
#: The rows that come from the bot's ladder (`bot_ladder_facts.LADDER_ROWS`), not from `BotFacts`.
_LADDER_KEYS = frozenset(LADDER_ROWS)
#: The rows that say where a readiness step stands, written from the readiness and not from `BotFacts`.
_STEP_KEYS = frozenset(step_key(step) for step in ReadinessStep)
#: The rows `BotFacts` writes, by the name of the field.
_FACT_KEYS = tuple(key for key in PROPERTY_KEYS if key not in _LADDER_KEYS | _STEP_KEYS)


class BotPlanPanel(QStackedWidget):
    """@brief The selected bot's name, state, figures, parameters and verdicts."""

    def __init__(self, model: BotsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelBotPlan")
        self._model = model
        self.title = plain_label()
        self.title.setObjectName("lblBotName")
        self.state = StateBadge("lblBotState", wrap=True)
        self.venue = QComboBox()
        self.venue.setObjectName("cmbBotVenue")
        #: Where the bot stands, in one sentence with the platform's message icon (`BOT-209`).
        self.banner = PlanStatusBanner()
        self._kind_panel: QWidget | None = None
        #: What the Venue field shows now, so a tick that changes nothing does not
        #: close a drop-down the user has open.
        self._venue_shown: tuple[object, ...] = ()
        self.properties = PlanPropertyGrid(PROPERTY_GROUPS)
        self.checks = PlanChecksView()
        self._venue_form = QFormLayout()
        self._panel_slot = QVBoxLayout()
        self._build()
        self._connect()
        self._show_costs(False)
        self._show_ladder()
        self._show_readiness()
        self._show_selection()

    def set_kind_panel(self, panel: QWidget | None) -> None:
        """The editor of the selected bot's kind: one built for this selection, deleted when the
        next is shown (`BUG-242`)."""
        self._kind_panel = panel
        if panel is not None:
            panel.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        replace_in(self._panel_slot, panel)

    def _build(self) -> None:
        empty = empty_page(EMPTY_TEXT, "lblBotsEmpty")
        plan = QWidget()
        column = QVBoxLayout(plan)
        self._column = column
        column.addWidget(self.title)
        column.addWidget(self.state)
        column.addWidget(self.banner)
        self._venue_form.addRow("Venue", self.venue)
        column.addLayout(self._venue_form)
        column.addWidget(self.properties.body)
        column.addLayout(self._panel_slot)
        column.addWidget(self.checks.body)
        self._parameters_first = False
        column.addStretch(1)
        scroll = QScrollArea()
        scroll.setObjectName("scrollBotPlan")
        scroll.setWidgetResizable(True)
        scroll.setWidget(plan)
        self.addWidget(empty)
        self.addWidget(scroll)

    def _connect(self) -> None:
        model = self._model
        model.selection_changed.connect(self._show_selection)
        model.facts_changed.connect(self._show_facts)
        model.ladder_changed.connect(self._show_ladder)
        model.judgement_changed.connect(self._show_judgement)
        model.judgement_changed.connect(self._show_where_the_bot_stands)
        model.readiness_changed.connect(self._show_readiness)
        model.facts_changed.connect(self._show_venue_if_changed)
        model.venue_choices_changed.connect(self._show_venue)
        # `activated` is the user's pick only: showing the bot's own venue never
        # asks for a change.
        self.venue.activated.connect(self._on_venue_picked)

    def index_of_parameters(self) -> int:
        """Where the kind's parameters sit in the panel, top to bottom."""
        return self._column.indexOf(self._panel_slot)

    def index_of_figures(self) -> int:
        """Where the bot's figures sit, top to bottom."""
        return self._column.indexOf(self.properties.body)

    def _arrange(self) -> None:
        """A bot at rest is being designed: its parameters come right after the
        banner, then what the kind says about them and the figures, so the hint under a
        field, the field and the list of checks are in view together (`EPIC-035N`,
        `BOT-209`). A bot with a run is being watched: its figures come first, its
        parameters are read-only below them, and the checks last."""
        bot = self._model.selected
        parameters_first = bot is not None and bot.state in RUN_STARTING_STATES
        if parameters_first == self._parameters_first:
            return
        self._parameters_first = parameters_first
        column = self._column
        column.removeWidget(self.properties.body)
        column.removeWidget(self.checks.body)
        column.removeItem(self._panel_slot)
        at = column.indexOf(self.banner) + 2
        if parameters_first:
            column.insertLayout(at, self._panel_slot)
            column.insertWidget(at + 1, self.checks.body)
            column.insertWidget(at + 2, self.properties.body)
        else:
            column.insertWidget(at, self.properties.body)
            column.insertLayout(at + 1, self._panel_slot)
            column.insertWidget(at + 2, self.checks.body)

    def _show_selection(self) -> None:
        bot = self._model.selected
        self._arrange()
        self.setCurrentIndex(0 if bot is None else 1)
        self.title.setText(bot.name if bot else "")
        self._show_facts()
        self._show_venue()

    def _show_venue_if_changed(self) -> None:
        if self._venue_shown != self._venue_key():
            self._show_venue()

    def _venue_key(self) -> tuple[object, ...]:
        bot = self._model.selected
        if bot is None:
            return ()
        return (bot.bot_id, bot.venue, bot.venue_locked, self._model.venue_choices)

    def _show_venue(self) -> None:
        """The bot's venue among the venues of its own market, changeable only while the
        bot is a draft that never ran (`BOT-171`); a locked field says why."""
        bot = self._model.selected
        combo = self.venue
        self._venue_shown = self._venue_key()
        combo.clear()
        if bot is None:
            return
        profile = venue_profile_of(bot.venue)
        for choice in self._model.venue_choices:
            if venue_profile_of(choice.venue) == profile:
                add_venue_choice(combo, choice)
        index = combo.findData(bot.venue)
        if index < 0:
            combo.addItem(bot.venue.display_name, bot.venue)
            index = combo.count() - 1
        combo.setCurrentIndex(index)
        combo.setEnabled(not bot.venue_locked)
        combo.setToolTip(
            bot.venue_locked
            or f"Move this draft to another {title_word_of(bot.venue)} venue: its account is read again."
        )

    def _on_venue_picked(self, index: int) -> None:
        bot = self._model.selected
        value = self.venue.itemData(index)
        if bot is not None and value != bot.venue:
            self._model.venue_change_requested.emit(value)

    def _show_facts(self) -> None:
        self._arrange()
        facts = self._model.facts
        selected = self._model.selected
        self.state.show_state(
            (facts.state_word or facts.state) if facts else "",
            state_look(selected.state) if facts and selected else None,
        )
        self._show_where_the_bot_stands()
        self.properties.set_values(
            {key: getattr(facts, key) if facts else "" for key in _FACT_KEYS},
            facts.tones if facts else {},
        )
        self._show_costs(facts is not None and facts.shows_costs)

    def _show_ladder(self) -> None:
        """The ladder rows: the grid step, the profit a cycle earns and where the price stands."""
        ladder = ladder_facts(self._model.ladder)
        self.properties.set_values(dict(ladder.rows), ladder.tones)
        self.properties.set_rows_shown((LIQUIDATION_KEY,), ladder.shows_liquidation)

    def _show_costs(self, shown: bool) -> None:
        """The cost rows belong to a venue with funding; Spot's figures keep their rows."""
        self.properties.set_rows_shown(COST_KEYS, shown)

    def _show_readiness(self) -> None:
        """How far the bot is: the three steps as the table's first group and, in the banner, the
        first thing left (`EPIC-034H`). Only a bot at rest has a Start to wait for."""
        readiness = self._model.readiness
        shown = readiness is not None
        self.properties.set_group_shown(READINESS_GROUP, shown)
        if readiness is not None:
            self.properties.set_values(
                {step_key(step): words for step, words in step_rows(readiness)}
            )
        self._show_where_the_bot_stands()

    def _show_where_the_bot_stands(self) -> None:
        """The one sentence under the name: see `plan_status.py`."""
        bot, facts = self._model.selected, self._model.facts
        if bot is None:
            self.banner.show_status(PlanStatus())
            return
        label_of = getattr(self._kind_panel, "field_label", lambda _code: None)
        self.banner.show_status(
            plan_status(
                StatusInputs(
                    bot.state,
                    facts.note if facts else "",
                    self._model.readiness,
                    self._model.readiness_state,
                    label_of,
                )
            )
        )

    def _show_judgement(self) -> None:
        self.checks.show_checks(self._model.checks)

    def verdict_lines(self) -> tuple[str, ...]:
        """What the kind said about the plan, one whole sentence per check, as the list's tooltips hold it."""
        return self._model.verdict_lines
