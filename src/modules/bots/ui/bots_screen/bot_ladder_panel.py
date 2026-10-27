"""`BOT-193` — the Bots mode's Ladder panel: the selected Grid bot's grids, one row each.

Above the table, the ladder in one line and, when the saved run is not this ladder, a note
(`bot_ladder_facts.py`); the table is one row per grid with its step, what one cycle there earns and
what the saved run says it is doing (`BotLadderTableModel`). Where the last price the bot heard
stands is in the Plan panel's figures, beside the profit. The figures come
from the parameters on screen (`grid_ladder_of`; the saved record when nothing is edited, and the
summary then says "Not saved"), so a bot at rest, a halted one and a read-only copy show them too. Like the Orders and Fills panels it is the content of one dock, no card of its own.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import GridLadder
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_ladder_facts import (
    ladder_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    BotLadderTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable

NO_GRIDS_TEXT = "The selected bot has no ladder to show."


class BotLadderPanel(QWidget):
    """@brief The selected bot's ladder, summary and price position."""

    def __init__(self, model: BotsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelBotLadder")
        self._model = model
        self.grids = BotLadderTableModel(self)
        self.summary = _wrapped("lblBotLadderSummary")
        self.note = _wrapped("lblBotLadderNote")
        self._table = SpecTable(
            self.grids, object_name="tblBotLadder", empty_text=NO_GRIDS_TEXT
        )
        layout = QVBoxLayout(self)
        for label in (self.summary, self.note):
            layout.addWidget(label)
        layout.addWidget(self._table.body, 1)
        model.selection_changed.connect(self._show_grids)
        model.ladder_changed.connect(self._show_grids)
        model.precisions_changed.connect(self._show_grids)
        self._show_grids()

    def use_precisions(self, precisions: ISymbolPrecisions) -> None:
        """Quotes the prices in the selected bot's symbol filters."""
        self.grids.use_precisions(precisions)

    def _show_grids(self) -> None:
        ladder = self._model.ladder
        facts = ladder_facts(ladder)
        bot = self._model.selected
        unsaved = self._model.facts is not None and self._model.facts.unsaved
        for label, text in (
            (
                self.summary,
                f"Not saved: {facts.summary}"
                if unsaved and facts.summary
                else facts.summary,
            ),
            (self.note, facts.note),
        ):
            label.setText(text)
            label.setVisible(bool(text))
        self.summary.setToolTip(facts.detail)
        if bot is None or not isinstance(ladder, GridLadder):
            self.grids.show_rows(None, ())
            return
        self.grids.show_rows(bot.symbol, ladder.rows)


def _wrapped(object_name: str) -> QLabel:
    label = plain_label()
    label.setObjectName(object_name)
    label.setWordWrap(True)
    return label
