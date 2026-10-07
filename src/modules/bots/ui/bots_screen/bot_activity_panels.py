"""`EPIC-033K` — what the selected bot is doing, as the Bots mode's bottom
panels (HLD §11.2.1, "bottom: Orders, Fills, Log (tabbed)").

Each is the content of one dock: its resting orders, its fills since the run
started, and the log lines that name it. Tables come from their models'
column specs (`EPIC-033N`); Refresh fills is a command of the Bots menu
(`bots_commands.py`), not a button here.
"""

from __future__ import annotations

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    BotFillsTableModel,
    BotOrdersTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable

NO_ORDERS_TEXT = "The selected bot has no resting orders."
NO_FILLS_TEXT = "The selected bot has no fills since its run started."


class BotOrdersPanel(QWidget):
    """@brief The selected bot's resting orders."""

    def __init__(self, model: BotsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelBotOrders")
        self._model = model
        self.orders = BotOrdersTableModel(self)
        self._table = SpecTable(
            self.orders, object_name="tblBotOrders", empty_text=NO_ORDERS_TEXT
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self._table.body)
        model.selection_changed.connect(self._show_orders)
        model.facts_changed.connect(self._show_orders)
        self._show_orders()

    def use_precisions(self, precisions: ISymbolPrecisions) -> None:
        """Quotes the orders in the selected bot's symbol filters."""
        self.orders.use_precisions(precisions)

    def _show_orders(self) -> None:
        bot = self._model.selected
        if bot is None:
            self.orders.show_rows(None, ())
            return
        self.orders.show_rows(bot.symbol, bot.progress.orders if bot.progress else ())


class BotFillsPanel(QWidget):
    """@brief The selected bot's fills, and a line on what was read."""

    def __init__(self, model: BotsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelBotFills")
        self._model = model
        self.fills = BotFillsTableModel(self)
        self.note = plain_label()
        self.note.setObjectName("lblBotFillsNote")
        self.note.setWordWrap(True)
        self._table = SpecTable(
            self.fills, object_name="tblBotFills", empty_text=NO_FILLS_TEXT
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self.note)
        layout.addWidget(self._table.body, 1)
        model.fills_changed.connect(self._show_fills)
        self._show_fills()

    def use_precisions(self, precisions: ISymbolPrecisions) -> None:
        """Quotes the fills in the selected bot's symbol filters."""
        self.fills.use_precisions(precisions)

    def _show_fills(self) -> None:
        fills, bot = self._model.fills, self._model.selected
        self.fills.show_rows(bot.symbol if bot else None, fills.fills)
        if self._model.selected is None:
            self.note.setText("")
        elif fills.problem:
            self.note.setText(f"Fills could not be read: {fills.problem}")
        elif fills.truncated:
            self.note.setText("Showing the newest fills; older ones were not read.")
        else:
            self.note.setText(f"{len(fills.fills)} fill(s) since the run started.")


class BotLogPanel(QPlainTextEdit):
    """@brief The log lines that name the selected bot, oldest first."""

    def __init__(self, model: BotsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("textBotLog")
        self.setReadOnly(True)
        self.setPlaceholderText("The selected bot has written no log line yet.")
        self._model = model
        # A new selection emits `log_changed` too (`BotsViewModel.set_selected`).
        model.log_changed.connect(self._show_log)
        self._show_log()

    def _show_log(self) -> None:
        self.setPlainText("\n".join(self._model.selected_log()))
        self.moveCursor(QTextCursor.MoveOperation.End)
