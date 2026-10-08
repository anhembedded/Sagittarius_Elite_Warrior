"""`EPIC-033K` — the Bots mode's Plan panel: the selected bot's plan.

The bot's name and state in words, how far it is on its three steps and what
is left before Start (`EPIC-034H`), its figures as a read-out, the kind's
parameter editor and what the kind says about those parameters (HLD §11.2.1,
"right: Plan (the kind's panel: parameters and verdicts)"). The panel names
no kind: the editor arrives from the presenter. With no bot selected it holds
the instruction to pick or create one.

The plan scrolls once, at the panel (`ui-presentation-rule.md` §3): the
read-out, a Grid's editor and its verdicts stand over 500 px, and without the
scroll they set the whole mode's minimum height (the PR #361 review measured
703 px). So the verdicts are word-wrapped text inside that one scroll area,
not a list scrolling inside it.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.readiness_words import (
    header,
    item_lines,
    step_lines,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.empty_page import empty_page
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    ReadoutForm,
)

from .widget_slot import replace_in

EMPTY_TEXT = "Select a bot in Bots, or create one with Bots → New bot…."
#: The bot's figures as a read-out (`EPIC-033N`). Most values are a
#: sentence `bot_facts.py` writes ("10.00 at 65,000.00"), its numbers by the
#: application's formatter, so those rows are text; the running time is a
#: duration the formatter writes itself.
FACT_SPECS = (
    *(
        ColumnSpec(key, title, ColumnKind.TEXT)
        for key, title in (
            ("venue", "Venue"),
            ("symbol", "Symbol"),
            ("capital", "Capital"),
            ("total_pnl", "Total PnL"),
            ("grid_profit", "of which grid profit"),
            ("unrealised", "of which unrealised"),
            ("hodl", "HODL benchmark"),
            ("inventory", "Held"),
        )
    ),
    ColumnSpec("running_time", "Running time", ColumnKind.DURATION),
)


class BotPlanPanel(QStackedWidget):
    """@brief The selected bot's name, state, figures, parameters and verdicts."""

    def __init__(self, model: BotsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelBotPlan")
        self._model = model
        self.title = plain_label()
        self.title.setObjectName("lblBotName")
        self.state = plain_label()
        self.state.setObjectName("lblBotState")
        self.state.setWordWrap(True)
        self.venue = QComboBox()
        self.venue.setObjectName("cmbBotVenue")
        self.readiness_header = plain_label()
        self.readiness_header.setObjectName("lblBotReadinessHeader")
        self.readiness_steps = plain_label()
        self.readiness_steps.setObjectName("lblBotReadinessSteps")
        self.readiness_items = plain_label()
        self.readiness_items.setObjectName("lblBotReadinessItems")
        self.readiness_items.setWordWrap(True)
        self._kind_panel: QWidget | None = None
        #: What the Venue field shows now, so a tick that changes nothing does not
        #: close a drop-down the user has open.
        self._venue_shown: tuple[object, ...] = ()
        self.facts = ReadoutForm(FACT_SPECS, APP_VALUE_FORMATTER)
        self.facts.setObjectName("roBotFacts")
        self.verdicts = plain_label()
        self.verdicts.setObjectName("lblBotVerdicts")
        self.verdicts.setWordWrap(True)
        self._panel_slot = QVBoxLayout()
        self._build()
        self._connect()
        self._show_selection()

    def set_kind_panel(self, panel: QWidget | None) -> None:
        self._kind_panel = panel
        replace_in(self._panel_slot, panel)

    def _build(self) -> None:
        empty = empty_page(EMPTY_TEXT, "lblBotsEmpty")
        plan = QWidget()
        column = QVBoxLayout(plan)
        column.addWidget(self.title)
        column.addWidget(self.state)
        venue = QFormLayout()
        venue.addRow("Venue", self.venue)
        column.addLayout(venue)
        column.addWidget(self.readiness_header)
        column.addWidget(self.readiness_steps)
        column.addWidget(self.readiness_items)
        column.addWidget(self.facts)
        column.addLayout(self._panel_slot)
        column.addWidget(plain_label("What the kind says about these parameters:"))
        column.addWidget(self.verdicts)
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
        model.judgement_changed.connect(self._show_judgement)
        model.readiness_changed.connect(self._show_readiness)
        model.facts_changed.connect(self._show_venue_if_changed)
        model.venue_choices_changed.connect(self._show_venue)
        # `activated` is the user's pick only: showing the bot's own venue never
        # asks for a change.
        self.venue.activated.connect(self._on_venue_picked)

    def _show_selection(self) -> None:
        bot = self._model.selected
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
        """The bot's venue among the Spot venues, changeable only while the bot
        is a draft that never ran (`BOT-171`); a locked field says why."""
        bot = self._model.selected
        combo = self.venue
        self._venue_shown = self._venue_key()
        combo.clear()
        if bot is None:
            return
        for choice in self._model.venue_choices:
            combo.addItem(choice.option_text, choice.venue)
        index = combo.findData(bot.venue)
        if index < 0:
            combo.addItem(bot.venue.display_name, bot.venue)
            index = combo.count() - 1
        combo.setCurrentIndex(index)
        combo.setEnabled(not bot.venue_locked)
        combo.setToolTip(
            bot.venue_locked
            or "Move this draft to another Spot venue: its account is read again."
        )

    def _on_venue_picked(self, index: int) -> None:
        bot = self._model.selected
        value = self.venue.itemData(index)
        if bot is not None and value != bot.venue:
            self._model.venue_change_requested.emit(value)

    def _show_facts(self) -> None:
        facts = self._model.facts
        self.state.setText(facts.state if facts else "")
        self.facts.set_values(
            {spec.key: getattr(facts, spec.key) if facts else "" for spec in FACT_SPECS}
        )

    def _show_readiness(self) -> None:
        """How far the bot is and what is left before Start (`EPIC-034H`): the
        count, the three steps, and each item with its reason and its fix. Only
        a bot at rest has a Start to wait for."""
        readiness = self._model.readiness
        shown = readiness is not None
        for label in (
            self.readiness_header,
            self.readiness_steps,
            self.readiness_items,
        ):
            label.setVisible(shown)
        if readiness is None:
            return
        label_of = getattr(self._kind_panel, "field_label", lambda _code: None)
        self.readiness_header.setText(
            f"Start: {header(readiness, self._model.readiness_state)}"
        )
        self.readiness_steps.setText("\n".join(step_lines(readiness)))
        self.readiness_items.setText("\n".join(item_lines(readiness, label_of)))
        self.readiness_items.setVisible(bool(readiness.items))

    def _show_judgement(self) -> None:
        self.verdicts.setText("\n".join(self._model.verdict_lines))

    def verdict_lines(self) -> tuple[str, ...]:
        """The verdicts as shown, one per line."""
        text = self.verdicts.text()
        return tuple(text.split("\n")) if text else ()
