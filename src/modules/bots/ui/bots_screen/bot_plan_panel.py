"""`EPIC-033K` — the Bots mode's Plan panel: the selected bot's plan.

The bot's name and state in words, its figures as a read-out, the kind's
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
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
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
            ("grid_profit", "Grid profit"),
            ("unrealised", "Unrealised PnL"),
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
        replace_in(self._panel_slot, panel)

    def _build(self) -> None:
        empty = empty_page(EMPTY_TEXT, "lblBotsEmpty")
        plan = QWidget()
        column = QVBoxLayout(plan)
        column.addWidget(self.title)
        column.addWidget(self.state)
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

    def _show_selection(self) -> None:
        bot = self._model.selected
        self.setCurrentIndex(0 if bot is None else 1)
        self.title.setText(bot.name if bot else "")
        self._show_facts()

    def _show_facts(self) -> None:
        facts = self._model.facts
        self.state.setText(facts.state if facts else "")
        self.facts.set_values(
            {spec.key: getattr(facts, spec.key) if facts else "" for spec in FACT_SPECS}
        )

    def _show_judgement(self) -> None:
        lines = list(self._model.verdict_lines)
        if self._model.refusal:
            lines.append(f"Start is blocked: {self._model.refusal}")
        self.verdicts.setText("\n".join(lines))

    def verdict_lines(self) -> tuple[str, ...]:
        """The verdicts as shown, one per line."""
        text = self.verdicts.text()
        return tuple(text.split("\n")) if text else ()
