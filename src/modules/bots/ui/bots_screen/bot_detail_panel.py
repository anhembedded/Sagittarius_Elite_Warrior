"""`EPIC-029F` — the detail shell, the same for every kind.

A header (name, state in words), the figures, and the tabs: the
bot's chart, its parameters (the kind's own editor and the kind's verdicts),
its resting orders, its fills, its log, and its kind's backtest (`EPIC-029D`,
hidden for a kind without one). The shell names no kind: the editor, the
chart and the backtest page arrive from the presenter.

The bot's lifecycle actions and Refresh fills are the module's commands since
`EPIC-033D` (`bots_commands.py`), in the Bots menu and toolbar.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    BotFillsTableModel,
    BotOrdersTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    ReadoutForm,
    configure_item_view,
)

EMPTY_TEXT = "Select a bot, or create one with New bot."
NO_CHART_TEXT = "The bot's chart is not open."
#: The bot's figures as a read-out (`EPIC-033N`). Each value is a sentence
#: `bot_facts.py` writes ("10.00 at 65,000.00"), its numbers by the
#: application's formatter, so every row is text here.
_FACT_SPECS = tuple(
    ColumnSpec(key, title, ColumnKind.TEXT)
    for key, title in (
        ("venue", "Venue"),
        ("symbol", "Symbol"),
        ("capital", "Capital"),
        ("grid_profit", "Grid profit"),
        ("unrealised", "Unrealised PnL"),
        ("inventory", "Held"),
        ("running_time", "Running time"),
    )
)


class BotDetailPanel(QWidget):
    """@brief One bot's header, figures and tabs."""

    fit_levels_requested = Signal()

    def __init__(self, model: BotsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model
        self.title = QLabel()
        self.title.setObjectName("lblBotName")
        self.state = QLabel()
        self.state.setObjectName("lblBotState")
        self.state.setWordWrap(True)
        self.facts = ReadoutForm(_FACT_SPECS, APP_VALUE_FORMATTER)
        self.facts.setObjectName("roBotFacts")
        self.orders = BotOrdersTableModel(self)
        self.fills = BotFillsTableModel(self)
        self.verdicts = QListWidget()
        self.verdicts.setObjectName("listBotVerdicts")
        self.fills_note = QLabel()
        self.fills_note.setWordWrap(True)
        self.fit_levels = QPushButton("Fit levels")
        self.fit_levels.setObjectName("btnFitLevels")
        self.fit_levels.setToolTip("Scale the price axis to show every level.")
        self.log = QPlainTextEdit()
        self.log.setObjectName("textBotLog")
        self.log.setReadOnly(True)
        self._chart_slot = QVBoxLayout()
        self._panel_slot = QVBoxLayout()
        self._backtest_slot = QVBoxLayout()
        self.tabs = QTabWidget()
        self._pages = QStackedWidget()
        self._build()
        self.set_chart(None)
        self.set_backtest_page(None)
        self._connect()
        self._show_selection()

    def set_chart(self, chart: QWidget | None) -> None:
        _replace(self._chart_slot, chart or QLabel(NO_CHART_TEXT))

    def set_kind_panel(self, panel: QWidget | None) -> None:
        _replace(self._panel_slot, panel)

    def set_backtest_page(self, page: QWidget | None) -> None:
        """The kind's backtest page; `None` hides the Backtest tab."""
        _replace(self._backtest_slot, page)
        self.tabs.setTabVisible(self._backtest_tab, page is not None)

    # -- building --------------------------------------------------------- #

    def _build(self) -> None:
        header = QHBoxLayout()
        names = QVBoxLayout()
        names.addWidget(self.title)
        names.addWidget(self.state)
        header.addLayout(names, 1)
        self.tabs.addTab(self._chart_page(), "Chart")
        self.tabs.addTab(self._parameters_page(), "Parameters")
        self.tabs.addTab(_table(self.orders, "tblBotOrders"), "Orders")
        self.tabs.addTab(self._fills_page(), "Fills")
        self.tabs.addTab(self.log, "Log")
        backtest = QWidget()
        backtest.setLayout(self._backtest_slot)
        self._backtest_tab = self.tabs.addTab(backtest, "Backtest")
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.addLayout(header)
        detail_layout.addWidget(self.facts)
        detail_layout.addWidget(self.tabs, 1)
        empty = QLabel(EMPTY_TEXT)
        empty.setObjectName("lblBotsEmpty")
        self._pages.addWidget(empty)
        self._pages.addWidget(detail)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._pages)

    def _chart_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        tools = QHBoxLayout()
        tools.addStretch(1)
        tools.addWidget(self.fit_levels)
        layout.addLayout(tools)
        layout.addLayout(self._chart_slot, 1)
        return page

    def _parameters_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(self._panel_slot)
        layout.addWidget(QLabel("What the kind says about these parameters:"))
        layout.addWidget(self.verdicts, 1)
        return page

    def _fills_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        tools = QHBoxLayout()
        tools.addWidget(self.fills_note, 1)
        layout.addLayout(tools)
        layout.addWidget(_table(self.fills, "tblBotFills"), 1)
        return page

    def _connect(self) -> None:
        model = self._model
        model.selection_changed.connect(self._show_selection)
        model.facts_changed.connect(self._show_facts)
        model.judgement_changed.connect(self._show_judgement)
        model.fills_changed.connect(self._show_fills)
        model.log_changed.connect(self._show_log)
        self.fit_levels.clicked.connect(self.fit_levels_requested)

    # -- showing ---------------------------------------------------------- #

    def _show_selection(self) -> None:
        bot = self._model.selected
        self._pages.setCurrentIndex(0 if bot is None else 1)
        self.title.setText(bot.name if bot else "")
        self.orders.set_rows(bot.progress.orders if bot and bot.progress else ())
        self._show_facts()
        self._show_log()

    def _show_facts(self) -> None:
        facts = self._model.facts
        self.state.setText(facts.state if facts else "")
        self.facts.set_values(
            {
                spec.key: getattr(facts, spec.key) if facts else ""
                for spec in _FACT_SPECS
            }
        )
        bot = self._model.selected
        self.orders.set_rows(bot.progress.orders if bot and bot.progress else ())

    def _show_judgement(self) -> None:
        self.verdicts.clear()
        self.verdicts.addItems(list(self._model.verdict_lines))
        if self._model.refusal:
            self.verdicts.addItem(f"Start is blocked: {self._model.refusal}")

    def _show_fills(self) -> None:
        fills = self._model.fills
        self.fills.set_rows(fills.fills)
        if fills.problem:
            self.fills_note.setText(f"Fills could not be read: {fills.problem}")
        elif fills.truncated:
            self.fills_note.setText(
                "Showing the newest fills; older ones were not read."
            )
        else:
            self.fills_note.setText(
                f"{len(fills.fills)} fill(s) since the run started."
            )

    def _show_log(self) -> None:
        self.log.setPlainText("\n".join(self._model.selected_log()))
        self.log.moveCursor(QTextCursor.MoveOperation.End)


def _table(model: BotOrdersTableModel | BotFillsTableModel, name: str) -> QTableView:
    """Columns, sorting and selection from the model's specs (`EPIC-033N`)."""
    table = QTableView()
    table.setObjectName(name)
    configure_item_view(table, model, model.COLUMNS, formatter=APP_VALUE_FORMATTER)
    return table


def _replace(slot: QVBoxLayout, widget: QWidget | None) -> None:
    while slot.count():
        item = slot.takeAt(0)
        old = item.widget() if item is not None else None
        if old is not None:
            old.setParent(None)
    if widget is not None:
        slot.addWidget(widget)
